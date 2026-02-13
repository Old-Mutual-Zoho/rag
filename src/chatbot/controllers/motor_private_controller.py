"""Controller for Motor Private full-form submissions.

This controller wraps MotorPrivateFlow.complete_flow so that motor-specific
validations and quote creation are encapsulated outside the FastAPI layer.
"""

from typing import Any, Dict

from src.chatbot.flows.motor_private import MotorPrivateFlow


class MotorPrivateController:
    def __init__(self, db, product_catalog: Any):
        self.db = db
        self.product_catalog = product_catalog

    async def submit_full_form(self, external_user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the full Motor Private form and create a quote.

        external_user_id is typically the phone number used by the client.
        """

        # Resolve external identifier (e.g. phone) to internal user UUID
        user = self.db.get_or_create_user(phone_number=external_user_id)
        internal_user_id = str(user.id)

        # Reuse the existing MotorPrivateFlow business logic and validations.
        flow = MotorPrivateFlow(self.product_catalog, self.db)
        result = await flow.complete_flow(dict(data or {}), internal_user_id)

        quote_id = (result.get("data") or {}).get("quote_id")
        if not quote_id:
            raise RuntimeError("Failed to create Motor Private quote")

        quote = self.db.get_quote(quote_id)
        if not quote:
            raise RuntimeError("Motor Private quote not found after creation")

        breakdown = quote.pricing_breakdown or {}
        return {
            "quote_id": str(quote.id),
            "product_name": quote.product_name or "Motor Private",
            "total_premium": float(quote.premium_amount),
            "breakdown": breakdown,
        }
