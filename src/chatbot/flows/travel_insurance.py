"""
Travel Insurance flow - Customer buying journey for Old Mutual Travel products.

Flow: Product selection → About you → Travel party & trip details → Data consent →
Traveller details → Emergency contact → Bank details (optional) → Passport upload →
Premium calculation → Payment.

Based on the Travel Sure Plus / Travel Insurance customer journey screens.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict
from datetime import datetime


# Travel insurance product cards (from product selection screen)
TRAVEL_INSURANCE_PRODUCTS = [
    {"id": "worldwide_essential", "label": "Worldwide Essential", "description": "Simple insurance for worry-free international travel"},
    {"id": "worldwide_elite", "label": "Worldwide Elite", "description": "Comprehensive cover for confident world travel"},
    {"id": "schengen_essential", "label": "Schengen Essential", "description": "Core cover for travel to the Schengen-area"},
    {"id": "schengen_elite", "label": "Schengen Elite", "description": "Enhanced benefits for travel to the Schengen-area"},
    {"id": "student_cover", "label": "Student Cover", "description": "Flexible travel cover designed for students abroad"},
    {"id": "africa_asia", "label": "Africa & Asia", "description": "Tailored protection for trips across Africa and Asia"},
    {"id": "inbound_karibu", "label": "Inbound Karibu", "description": "Travel insurance for visitors coming to Uganda"},
]

# Sample benefits for premium summary (Worldwide Essential tier)
TRAVEL_INSURANCE_BENEFITS = [
    {"benefit": "Emergency medical expenses (Including epidemics and pandemics)", "amount": "Up to $40,000"},
    {"benefit": "Compulsory quarantine expenses (epidemics/pandemics)", "amount": "$85 per night up to 14 nights"},
    {"benefit": "Emergency medical evacuation and repatriation", "amount": "Actual Expenses"},
    {"benefit": "Emergency dental care", "amount": "Up to $250"},
    {"benefit": "Optical expenses", "amount": "Up to $100"},
    {"benefit": "Baggage delay", "amount": "$50 per hour up to $250"},
    {"benefit": "Replacement of passport and driving license", "amount": "Up to $300"},
    {"benefit": "Personal Liability", "amount": "Up to $100,000"},
]

# Relationship options for emergency contact
EMERGENCY_CONTACT_RELATIONSHIPS = [
    "Spouse", "Parent", "Child", "Sibling", "Sister-in-law", "Brother-in-law",
    "Friend", "Other",
]


class TravelInsuranceFlow:
    """
    Guided flow for Travel Insurance: product selection, about you, travel details,
    data consent, traveller details, emergency contact, bank (optional), passport upload,
    premium calculation, then payment.
    """

    STEPS = [
        "product_selection",
        "about_you",
        "travel_party_and_trip",
        "data_consent",
        "traveller_details",
        "emergency_contact",
        "bank_details_optional",
        "upload_passport",
        "premium_summary",
        "choose_plan_and_pay",
    ]

    def __init__(self, product_catalog, db):
        self.catalog = product_catalog
        self.db = db
        # Controller for persistence
        try:
            from src.chatbot.controllers.travel_insurance_controller import TravelInsuranceController

            self.controller = TravelInsuranceController(db)
        except Exception:
            self.controller = None

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        """Start Travel Insurance flow"""
        data = dict(initial_data or {})
        data.setdefault("user_id", user_id)
        data.setdefault("product_id", "travel_insurance")
        # Create persistent application record if controller available
        if self.controller:
            app = self.controller.create_application(user_id, data)
            data["application_id"] = app.get("id")
        return await self.process_step("", 0, data, user_id)

    async def process_step(
        self,
        user_input,
        current_step: int,
        collected_data: Dict[str, Any],
        user_id: str,
    ) -> Dict:
        """Process one step of the flow."""
        try:
            if user_input and isinstance(user_input, str) and user_input.strip().startswith("{"):
                payload = json.loads(user_input)
            elif user_input and isinstance(user_input, dict):
                payload = user_input
            else:
                payload = {"_raw": user_input} if user_input else {}
        except (json.JSONDecodeError, TypeError):
            payload = {"_raw": user_input} if user_input else {}

        step_handlers = [
            self._step_product_selection,
            self._step_about_you,
            self._step_travel_party_and_trip,
            self._step_data_consent,
            self._step_traveller_details,
            self._step_emergency_contact,
            self._step_bank_details_optional,
            self._step_upload_passport,
            self._step_premium_summary,
            self._step_choose_plan_and_pay,
        ]
        if 0 <= current_step < len(step_handlers):
            return await step_handlers[current_step](payload, collected_data, user_id)
        return {"error": "Invalid step"}

    async def _step_product_selection(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            product_id = payload.get("product_id") or payload.get("coverage_product", "").strip()
            if product_id:
                product = next((p for p in TRAVEL_INSURANCE_PRODUCTS if p["id"] == product_id), None)
                if product:
                    data["selected_product"] = product
                    # Persist
                    app_id = data.get("application_id")
                    if self.controller and app_id:
                        self.controller.update_product_selection(app_id, {"product_id": product_id})

        return {
            "response": {
                "type": "product_cards",
                "message": "✈️ Select your travel insurance cover",
                "products": [
                    {
                        "id": p["id"],
                        "label": p["label"],
                        "description": p["description"],
                        "action": "select_cover",
                    }
                    for p in TRAVEL_INSURANCE_PRODUCTS
                ],
            },
            "next_step": 1,
            "collected_data": data,
        }

    async def _step_about_you(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["about_you"] = {
                "first_name": payload.get("first_name", ""),
                "middle_name": payload.get("middle_name", ""),
                "surname": payload.get("surname", ""),
                "phone_number": payload.get("phone_number", ""),
                "email": payload.get("email", ""),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_about_you(app_id, payload)

        return {
            "response": {
                "type": "form",
                "message": "👤 About you – Get your travel insurance quote in minutes",
                "fields": [
                    {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                    {"name": "middle_name", "label": "Middle Name (Optional)", "type": "text", "required": False},
                    {"name": "surname", "label": "Surname", "type": "text", "required": True},
                    {"name": "phone_number", "label": "Phone Number", "type": "tel", "required": True, "placeholder": "07XX XXX XXX"},
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                ],
            },
            "next_step": 2,
            "collected_data": data,
        }

    async def _step_travel_party_and_trip(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["travel_party_and_trip"] = {
                "travel_party": payload.get("travel_party", ""),
                "num_travellers_18_69": int(payload.get("num_travellers_18_69") or 0),
                "num_travellers_0_17": int(payload.get("num_travellers_0_17") or 0),
                "num_travellers_70_75": int(payload.get("num_travellers_70_75") or 0),
                "num_travellers_76_80": int(payload.get("num_travellers_76_80") or 0),
                "num_travellers_81_85": int(payload.get("num_travellers_81_85") or 0),
                "departure_country": payload.get("departure_country", ""),
                "destination_country": payload.get("destination_country", ""),
                "departure_date": payload.get("departure_date", ""),
                "return_date": payload.get("return_date", ""),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_travel_party_and_trip(app_id, payload)

        return {
            "response": {
                "type": "form",
                "message": "✈️ Travel details",
                "fields": [
                    {
                        "name": "travel_party",
                        "label": "Travel party",
                        "type": "radio",
                        "options": [
                            {"id": "myself_only", "label": "Myself only"},
                            {"id": "myself_and_someone_else", "label": "Myself and someone else"},
                            {"id": "group", "label": "Group"},
                        ],
                        "required": True,
                    },
                    {"name": "num_travellers_18_69", "label": "Number of travellers (18–69 years)", "type": "number", "min": 0, "required": True},
                    {"name": "num_travellers_0_17", "label": "Number of travellers (0–17 years)", "type": "number", "min": 0, "required": False},
                    {"name": "num_travellers_70_75", "label": "Number of travellers (70–75 years)", "type": "number", "min": 0, "required": False},
                    {"name": "num_travellers_76_80", "label": "Number of travellers (76–80 years)", "type": "number", "min": 0, "required": False},
                    {"name": "num_travellers_81_85", "label": "Number of travellers (81–85 years)", "type": "number", "min": 0, "required": False},
                    {"name": "departure_country", "label": "Departure Country", "type": "text", "required": True, "placeholder": "e.g. Uganda"},
                    {"name": "destination_country", "label": "Destination Country", "type": "text", "required": True, "placeholder": "e.g. Portugal"},
                    {"name": "departure_date", "label": "Departure Date", "type": "date", "required": True},
                    {"name": "return_date", "label": "Return Date", "type": "date", "required": True},
                ],
                "info": "A change in number of travellers will result in a premium adjustment.",
            },
            "next_step": 3,
            "collected_data": data,
        }

    async def _step_data_consent(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["data_consent"] = {
                "terms_and_conditions_agreed": payload.get("terms_and_conditions_agreed") in (True, "yes", "true", "1"),
                "consent_data_outside_uganda": payload.get("consent_data_outside_uganda") in (True, "yes", "true", "1"),
                "consent_child_data": payload.get("consent_child_data") in (True, "yes", "true", "1"),
                "consent_marketing": payload.get("consent_marketing") in (True, "yes", "true", "1"),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_data_consent(app_id, payload)

        return {
            "response": {
                "type": "consent",
                "message": "📋 Before we begin – Data consent",
                "consents": [
                    {
                        "id": "terms_and_conditions_agreed",
                        "label": "I have read and understand the Terms and Conditions.",
                        "required": True,
                        "link": "https://www.oldmutual.co.ug/terms",
                    },
                    {
                        "id": "consent_data_outside_uganda",
                        "label": "I consent to processing of my personal data outside Uganda (as per Privacy Notice and Privacy Policy).",
                        "required": True,
                    },
                    {
                        "id": "consent_child_data",
                        "label": "I am the parent/legal guardian and consent to processing of my child's personal data (if children are travelling).",
                        "required": False,
                    },
                    {
                        "id": "consent_marketing",
                        "label": "I consent to receive information about insurance/financial products and special offers. (You can opt-out anytime.)",
                        "required": False,
                    },
                ],
            },
            "next_step": 4,
            "collected_data": data,
        }

    async def _step_traveller_details(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            travellers = data.get("travellers") or []
            primary = {
                "first_name": payload.get("first_name", ""),
                "middle_name": payload.get("middle_name", ""),
                "surname": payload.get("surname", ""),
                "nationality_type": payload.get("nationality_type", ""),
                "passport_number": payload.get("passport_number", ""),
                "date_of_birth": payload.get("date_of_birth", ""),
                "occupation": payload.get("occupation", ""),
                "phone_number": payload.get("phone_number", ""),
                "office_number": payload.get("office_number", ""),
                "email": payload.get("email", ""),
                "postal_address": payload.get("postal_address", ""),
                "town_city": payload.get("town_city", ""),
            }
            if not travellers:
                travellers.append(primary)
            else:
                travellers[0] = primary
            data["travellers"] = travellers
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_traveller_details(app_id, payload)

        return {
            "response": {
                "type": "form",
                "message": "👤 Traveller details – Please provide your details and those of any accompanying travelers",
                "fields": [
                    {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                    {"name": "middle_name", "label": "Middle Name (Optional)", "type": "text", "required": False},
                    {"name": "surname", "label": "Surname", "type": "text", "required": True},
                    {
                        "name": "nationality_type",
                        "label": "Nationality Type",
                        "type": "radio",
                        "options": [{"id": "ugandan", "label": "Ugandan"}, {"id": "non_ugandan", "label": "Non-Ugandan"}],
                        "required": True,
                    },
                    {"name": "passport_number", "label": "Passport Number", "type": "text", "required": True},
                    {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"name": "occupation", "label": "Profession/Occupation", "type": "text", "required": True},
                    {"name": "phone_number", "label": "Phone Number", "type": "tel", "required": True},
                    {"name": "office_number", "label": "Office Number (Optional)", "type": "tel", "required": False},
                    {"name": "email", "label": "Email Address", "type": "email", "required": True},
                    {"name": "postal_address", "label": "Postal/Home Address", "type": "text", "required": True},
                    {"name": "town_city", "label": "Town/City", "type": "text", "required": True},
                ],
                "add_another": {"label": "Add another traveller", "action": "add_traveller"},
            },
            "next_step": 5,
            "collected_data": data,
        }

    async def _step_emergency_contact(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["emergency_contact"] = {
                "surname": payload.get("ec_surname", ""),
                "relationship": payload.get("ec_relationship", ""),
                "phone_number": payload.get("ec_phone_number", ""),
                "email": payload.get("ec_email", ""),
                "home_address": payload.get("ec_home_address", ""),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_emergency_contact(app_id, payload)

        return {
            "response": {
                "type": "form",
                "message": "📞 Emergency contact / beneficiary",
                "fields": [
                    {"name": "ec_surname", "label": "Surname", "type": "text", "required": True},
                    {
                        "name": "ec_relationship",
                        "label": "Relationship",
                        "type": "select",
                        "options": EMERGENCY_CONTACT_RELATIONSHIPS,
                        "required": True,
                    },
                    {"name": "ec_phone_number", "label": "Phone Number", "type": "tel", "required": True},
                    {"name": "ec_email", "label": "Email Address", "type": "email", "required": True},
                    {"name": "ec_home_address", "label": "Home/Postal Address", "type": "text", "required": False},
                ],
            },
            "next_step": 6,
            "collected_data": data,
        }

    async def _step_bank_details_optional(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["bank_details"] = {
                "bank_name": payload.get("bank_name", ""),
                "account_holder_name": payload.get("account_holder_name", ""),
                "account_number": payload.get("account_number", ""),
                "bank_branch": payload.get("bank_branch", ""),
                "account_currency": payload.get("account_currency", ""),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_bank_details(app_id, payload)

        return {
            "response": {
                "type": "form",
                "message": "🏦 Bank details (optional) – For refunds or payouts",
                "optional": True,
                "fields": [
                    {"name": "bank_name", "label": "Bank Name", "type": "text", "required": False},
                    {"name": "account_holder_name", "label": "Bank Account Holder Name", "type": "text", "required": False},
                    {"name": "account_number", "label": "Bank Account Number", "type": "text", "required": False},
                    {"name": "bank_branch", "label": "Bank Branch", "type": "text", "required": False},
                    {"name": "account_currency", "label": "Bank Account Currency", "type": "select", "options": ["UGX", "USD", "EUR"], "required": False},
                ],
            },
            "next_step": 7,
            "collected_data": data,
        }

    async def _step_upload_passport(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["passport_upload"] = {
                "file_ref": payload.get("passport_file_ref", ""),
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_passport_upload(app_id, payload)

        return {
            "response": {
                "type": "file_upload",
                "message": "📄 Upload copy of Passport Bio Data Page",
                "accept": "application/pdf,image/jpeg,image/jpg",
                "field_name": "passport_file_ref",
                "max_size_mb": 1,
                "help": "PDF, JPEG or JPG. Max 1 MB",
            },
            "next_step": 8,
            "collected_data": data,
        }

    async def _step_premium_summary(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and payload.get("passport_file_ref") and not data.get("passport_upload"):
            data["passport_upload"] = {
                "file_ref": payload.get("passport_file_ref", ""),
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            app_id = data.get("application_id")
            if self.controller and app_id:
                self.controller.update_passport_upload(app_id, payload)

        trip = data.get("travel_party_and_trip") or {}
        total_premium = self._calculate_travel_premium(data)
        # Persist pricing summary into application
        app_id = data.get("application_id")
        if self.controller and app_id:
            # store pricing breakdown as part of the travel application
            self.controller.update_travel_party_and_trip(app_id, data.get("travel_party_and_trip", {}))

        return {
            "response": {
                "type": "premium_summary",
                "message": "💰 Premium calculation",
                "product_name": data.get("selected_product", {}).get("label", "Travel Insurance"),
                "total_premium_usd": total_premium["total_usd"],
                "total_premium_ugx": total_premium["total_ugx"],
                "covering": trip.get("travel_party", "Myself"),
                "period_of_coverage": self._get_period_text(trip),
                "departure_country": trip.get("departure_country", ""),
                "destination_country": trip.get("destination_country", ""),
                "departure_date": trip.get("departure_date", ""),
                "return_date": trip.get("return_date", ""),
                "benefits": TRAVEL_INSURANCE_BENEFITS,
                "breakdown": total_premium.get("breakdown", {}),
                "download_option": True,
                "download_label": "Download Quote",
                "actions": [
                    {"type": "edit", "label": "Edit"},
                    {"type": "call_me_back", "label": "Call Me Back"},
                    {"type": "proceed_to_pay", "label": "Proceed"},
                ],
            },
            "next_step": 9,
            "collected_data": data,
        }

    async def _step_choose_plan_and_pay(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        action = (payload.get("action") or payload.get("_raw") or "").strip().lower()

        if "edit" in action:
            out = await self._step_travel_party_and_trip(payload, data, user_id)
            out["next_step"] = 2
            return out
        if "call" in action or "back" in action:
            return {
                "response": {
                    "type": "call_me_back",
                    "message": "We'll call you back shortly. Our team will reach out at your provided number.",
                },
                "next_step": 9,
                "collected_data": data,
            }

        # Proceed to pay
        total_premium = self._calculate_travel_premium(data)
        product = data.get("selected_product") or TRAVEL_INSURANCE_PRODUCTS[0]
        # Persist quote through controller so the application is updated
        app_id = data.get("application_id")
        if self.controller and app_id:
            app = self.controller.finalize_and_create_quote(app_id, user_id, total_premium)
            data["quote_id"] = app.get("quote_id") if app else None
        else:
            quote = self.db.create_quote(
                user_id=user_id,
                product_id=data.get("product_id", "travel_insurance"),
                premium_amount=total_premium["total_ugx"],
                sum_assured=None,
                underwriting_data=data,
                pricing_breakdown=total_premium.get("breakdown"),
                product_name=product.get("label", "Travel Insurance"),
            )
            data["quote_id"] = str(quote.id)

        return {
            "response": {
                "type": "proceed_to_payment",
                "message": "Proceeding to payment. Choose Mobile Money (MTN/Airtel) or Bank Transfer.",
                "quote_id": str(data["quote_id"]),
                "total_due_ugx": total_premium["total_ugx"],
                "payment_options": [
                    {"id": "mobile_money", "label": "Mobile Money", "providers": ["MTN", "Airtel"]},
                    {"id": "bank_transfer", "label": "Bank Transfer"},
                ],
            },
            "complete": True,
            "next_flow": "payment",
            "collected_data": data,
            "data": {"quote_id": str(data["quote_id"])},
        }

    def _calculate_travel_premium(self, data: Dict) -> Dict:
        """
        Calculate travel insurance premium.

        Test expectations:
        - returns total_usd, total_ugx, breakdown
        - breakdown includes "days"
        - for 2026-03-03 to 2026-03-08 => days == 6
        """
        trip = data.get("travel_party_and_trip") or {}

        departure_date = trip.get("departure_date")
        return_date = trip.get("return_date")

        # Default to 1 day if missing/invalid
        days = 1
        try:
            if departure_date and return_date:
                d1 = datetime.fromisoformat(departure_date).date()
                d2 = datetime.fromisoformat(return_date).date()
                # Inclusive days (03 to 08 => 6 days)
                days = max(1, (d2 - d1).days + 1)
        except Exception:
            days = 1

        # Number of travellers by age band
        travellers_18_69 = int(trip.get("num_travellers_18_69") or 0)
        travellers_0_17 = int(trip.get("num_travellers_0_17") or 0)
        travellers_70_75 = int(trip.get("num_travellers_70_75") or 0)
        travellers_76_80 = int(trip.get("num_travellers_76_80") or 0)
        travellers_81_85 = int(trip.get("num_travellers_81_85") or 0)

        # Product multiplier (simple tier pricing)
        product = data.get("selected_product") or {}
        product_id = product.get("id", "worldwide_essential")
        product_multiplier = {
            "worldwide_essential": Decimal("1.0"),
            "worldwide_elite": Decimal("1.5"),
            "schengen_essential": Decimal("1.2"),
            "schengen_elite": Decimal("1.7"),
            "student_cover": Decimal("0.9"),
            "africa_asia": Decimal("0.8"),
            "inbound_karibu": Decimal("0.6"),
        }.get(product_id, Decimal("1.0"))

        # Base daily rates (USD)
        rate_18_69 = Decimal("2.0")
        rate_0_17 = Decimal("1.0")
        rate_70_75 = Decimal("3.0")
        rate_76_80 = Decimal("4.0")
        rate_81_85 = Decimal("5.0")

        base_usd = (
            Decimal(days) * (
                Decimal(travellers_18_69) * rate_18_69
                + Decimal(travellers_0_17) * rate_0_17
                + Decimal(travellers_70_75) * rate_70_75
                + Decimal(travellers_76_80) * rate_76_80
                + Decimal(travellers_81_85) * rate_81_85
            )
        )

        total_usd = (base_usd * product_multiplier).quantize(Decimal("0.01"))

        # Simple FX rate (can be replaced later with live rates)
        usd_to_ugx = Decimal("3900")
        total_ugx = (total_usd * usd_to_ugx).quantize(Decimal("1."))

        return {
            "total_usd": float(total_usd),
            "total_ugx": float(total_ugx),
            "breakdown": {
                "days": days,
                "product_id": product_id,
                "product_multiplier": float(product_multiplier),
                "travellers": {
                    "18_69": travellers_18_69,
                    "0_17": travellers_0_17,
                    "70_75": travellers_70_75,
                    "76_80": travellers_76_80,
                    "81_85": travellers_81_85,
                },
                "base_usd": float(base_usd),
                "usd_to_ugx": float(usd_to_ugx),
            },
        }
