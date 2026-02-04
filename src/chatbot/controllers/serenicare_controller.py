"""Controller for Serenicare flow persistence."""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SerenicareController:
    def __init__(self, db):
        self.db = db

    def create_application(self, user_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        app = self.db.create_serenicare_application(user_id, initial_data or {})
        return self._to_dict(app)

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        app = self.db.get_serenicare_application(app_id)
        return self._to_dict(app) if app else None

    def list_applications(
        self,
        user_id: Optional[str] = None,
        order_by: str = "created_at",
        descending: bool = True,
    ):
        apps = self.db.list_serenicare_applications(user_id=user_id, order_by=order_by, descending=descending)
        return [self._to_dict(a) for a in apps]

    def delete_application(self, app_id: str) -> bool:
        return self.db.delete_serenicare_application(app_id)

    # Step helpers
    def update_cover_personalization(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"cover_personalization": {
            "date_of_birth": payload.get("date_of_birth", ""),
            "include_spouse": payload.get("include_spouse", False),
            "include_children": payload.get("include_children", False),
            "add_another_main_member": payload.get("add_another_main_member", False),
        }}
        app = self.db.update_serenicare_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_optional_benefits(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        selected = payload.get("optional_benefits") or []
        if isinstance(selected, str):
            selected = [s.strip() for s in selected.split(",") if s.strip()]
        updates = {"optional_benefits": selected}
        app = self.db.update_serenicare_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_medical_conditions(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"medical_conditions": {"has_condition": payload.get("has_condition", False)}}
        app = self.db.update_serenicare_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_plan_selection(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        plan_id = payload.get("plan_option") or payload.get("_raw", "").strip()
        updates = {"plan_option": {"id": plan_id}}
        app = self.db.update_serenicare_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_about_you(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"about_you": {
            "first_name": payload.get("first_name", ""),
            "middle_name": payload.get("middle_name", ""),
            "surname": payload.get("surname", ""),
            "phone_number": payload.get("phone_number", ""),
            "email": payload.get("email", ""),
        }}
        app = self.db.update_serenicare_application(app_id, updates)
        return self._to_dict(app) if app else None

    def finalize_and_create_quote(self, app_id: str, user_id: str, pricing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        app = self.db.get_serenicare_application(app_id)
        if not app:
            return None
        quote = self.db.create_quote(
            user_id=user_id,
            product_id=app.plan_option.get("id", "serenicare"),
            premium_amount=pricing.get("monthly"),
            sum_assured=None,
            underwriting_data={
                "cover_personalization": app.cover_personalization,
                "optional_benefits": app.optional_benefits,
                "medical_conditions": app.medical_conditions,
                "about_you": app.about_you,
            },
            pricing_breakdown=pricing.get("breakdown"),
            product_name="Serenicare",
        )
        updates = {"quote_id": str(quote.id), "status": "quoted"}
        self.db.update_serenicare_application(app_id, updates)
        app = self.db.get_serenicare_application(app_id)
        return self._to_dict(app) if app else None

    def _to_dict(self, app):
        if not app:
            return None
        return {
            "id": app.id,
            "user_id": app.user_id,
            "status": app.status,
            "cover_personalization": app.cover_personalization,
            "optional_benefits": app.optional_benefits,
            "medical_conditions": app.medical_conditions,
            "plan_option": app.plan_option,
            "about_you": app.about_you,
            "quote_id": app.quote_id,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
        }
