"""
Payment flow - Handle premium payments
"""

from typing import Dict
from datetime import datetime
import uuid


class PaymentFlow:
    # Payment threshold for auto-processing vs agent assistance
    AUTO_PAYMENT_THRESHOLD = 500000  # UGX

    def __init__(self, db):
        self.db = db

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        """Start payment flow"""
        quote_id = initial_data.get("quote_id")

        if not quote_id:
            return {"error": "No quote ID provided"}

        # Get quote details
        quote = self.db.get_quote(quote_id)

        if not quote:
            return {"error": "Quote not found"}

        return await self.process_step("", 0, {"quote": quote, "user_id": user_id}, user_id)

    async def process_step(self, user_input: str, current_step: int, collected_data: Dict, user_id: str) -> Dict:
        """Process payment flow"""

        quote = collected_data.get("quote")
        premium_amount = float(quote.premium_amount) if quote else 0

        if current_step == 0:  # Payment method selection
            # Check if amount requires agent assistance
            requires_agent = premium_amount >= self.AUTO_PAYMENT_THRESHOLD

            if requires_agent:
                return {
                    "response": {
                        "type": "agent_required",
                        "message": (
                            f"💼 For premiums above UGX {self.AUTO_PAYMENT_THRESHOLD:,}, "
                            "we'll connect you with an agent to guide you through the payment process."
                        ),
                        "agent_info": {"name": "Old Mutual Support", "phone": "+256 753 888232", "email": "support@oldmutual.co.ug"},
                        "actions": [{"type": "call_agent", "label": "📞 Call Agent"}, {"type": "schedule_callback", "label": "📅 Schedule Callback"}],
                    },
                    "complete": True,
                    "data": {"requires_agent": True},
                }

            return {
                "response": {
                    "type": "payment_method",
                    "message": "💳 Choose your payment method",
                    "amount": premium_amount,
                    "options": [
                        {"id": "mobile_money", "label": "📱 Mobile Money", "providers": ["MTN", "Airtel"], "icon": "📲"},
                        {"id": "bank_transfer", "label": "🏦 Bank Transfer", "icon": "🏛️"},
                        {"id": "card", "label": "💳 Credit/Debit Card", "icon": "💳"},
                    ],
                },
                "next_step": 1,
                "collected_data": collected_data,
            }

        elif current_step == 1:  # Payment details
            payment_method = user_input
            collected_data["payment_method"] = payment_method

            if payment_method == "mobile_money":
                return {
                    "response": {
                        "type": "form",
                        "message": "📱 Enter your mobile money details",
                        "fields": [
                            {"name": "provider", "label": "Provider", "type": "select", "options": ["MTN Mobile Money", "Airtel Money"], "required": True},
                            {"name": "phone_number", "label": "Phone Number", "type": "tel", "placeholder": "07XX XXX XXX", "required": True},
                        ],
                    },
                    "next_step": 2,
                    "collected_data": collected_data,
                }

            elif payment_method == "bank_transfer":
                return {
                    "response": {
                        "type": "bank_details",
                        "message": "🏦 Bank Transfer Details",
                        "bank_info": {
                            "bank_name": "Stanbic Bank Uganda",
                            "account_name": "Old Mutual Uganda Limited",
                            "account_number": "9030008765432",
                            "swift_code": "SBICUGKX",
                            "branch": "Kampala Main Branch",
                        },
                        "instructions": [
                            "Transfer the exact amount shown",
                            "Use your policy/quote number as reference",
                            "Send proof of payment to payments@oldmutual.co.ug",
                        ],
                        "reference": f"QUOTE-{quote.id}",
                    },
                    "next_step": 3,
                    "collected_data": collected_data,
                }

            elif payment_method == "card":
                return {
                    "response": {
                        "type": "card_payment",
                        "message": "💳 You will be redirected to our secure payment gateway",
                        "payment_url": f"https://payments.oldmutual.co.ug/pay/{quote.id}",
                        "amount": premium_amount,
                        "currency": "UGX",
                    },
                    "next_step": 2,
                    "collected_data": collected_data,
                }

        elif current_step == 2:  # Process payment
            payment_details = user_input
            collected_data["payment_details"] = payment_details

            # Create payment record
            payment = self._create_payment_record(
                quote=quote, payment_method=collected_data["payment_method"], payment_details=payment_details, user_id=user_id
            )

            # For mobile money, initiate payment
            if collected_data["payment_method"] == "mobile_money":
                payment_result = await self._initiate_mobile_money_payment(payment_details, premium_amount)

                return {
                    "response": {
                        "type": "payment_initiated",
                        "message": "✅ Payment request sent to your phone",
                        "instructions": "Please enter your PIN to complete the payment",
                        "transaction_ref": payment_result["transaction_ref"],
                        "status": "pending",
                    },
                    "next_step": 3,
                    "collected_data": collected_data,
                    "data": {"payment_id": payment.id},
                }

            return {
                "response": {"type": "payment_pending", "message": "Payment processing...", "payment_id": str(payment.id)},
                "next_step": 3,
                "collected_data": collected_data,
            }

        elif current_step == 3:  # Payment confirmation
            # Check payment status
            payment_status = await self._check_payment_status(collected_data.get("payment_id"))

            if payment_status == "completed":
                # Create application
                application = self.db.create_application(
                    user_id=user_id, quote_id=quote.id, product_id=quote.product_id, application_data=collected_data, status="submitted"
                )

                return {
                    "response": {
                        "type": "payment_success",
                        "message": "🎉 Payment successful! Your policy is being processed.",
                        "policy_number": self._generate_policy_number(),
                        "next_steps": [
                            "You will receive your policy document via email within 24 hours",
                            "Your coverage starts immediately",
                            "Welcome to the Old Mutual family! 🏦",
                        ],
                        "support": {"email": "support@oldmutual.co.ug", "phone": "+256 753 888232"},
                    },
                    "complete": True,
                    "data": {"application_id": str(application.id), "payment_status": "completed"},
                }
            elif payment_status == "failed":
                return {
                    "response": {
                        "type": "payment_failed",
                        "message": "❌ Payment failed. Please try again.",
                        "actions": [
                            {"type": "retry", "label": "Try Again"},
                            {"type": "change_method", "label": "Use Different Payment Method"},
                            {"type": "contact_support", "label": "Contact Support"},
                        ],
                    },
                    "next_step": 0,  # Back to payment method selection
                    "collected_data": collected_data,
                }
            else:
                return {
                    "response": {"type": "payment_pending", "message": "⏳ Payment is being processed. Please wait...", "status": payment_status},
                    "next_step": 3,  # Stay on this step
                    "collected_data": collected_data,
                }

    def _create_payment_record(self, quote, payment_method, payment_details, user_id):
        """Create payment record in database"""
        # This would create actual payment record
        # For now, return mock
        from types import SimpleNamespace

        return SimpleNamespace(id=uuid.uuid4(), amount=quote.premium_amount, status="pending")

    async def _initiate_mobile_money_payment(self, payment_details, amount):
        """Initiate mobile money payment"""
        # This would integrate with MTN/Airtel API
        # For now, return mock
        return {"transaction_ref": f"MM{uuid.uuid4().hex[:10].upper()}", "status": "pending"}

    async def _check_payment_status(self, payment_id):
        """Check payment status"""
        # This would check with payment provider
        # For now, return mock success
        return "completed"

    def _generate_policy_number(self):
        """Generate policy number"""
        import random

        return f"POL{datetime.now().year}{random.randint(100000, 999999)}"
