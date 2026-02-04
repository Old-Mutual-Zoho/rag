"""Controller for persisting Personal Accident guided flow data.

Provides CRUD operations and step-specific update helpers that map directly
to the flow steps in `src.chatbot.flows.personal_accident.PersonalAccidentFlow`.
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PersonalAccidentController:
    def __init__(self, db):
        self.db = db

    def create_application(self, user_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        app = self.db.create_pa_application(user_id, initial_data or {})
        return self._to_dict(app)

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        app = self.db.get_pa_application(app_id)
        return self._to_dict(app) if app else None

    def list_applications(self, user_id: Optional[str] = None):
        apps = self.db.list_pa_applications(user_id=user_id)
        return [self._to_dict(a) for a in apps]

    def delete_application(self, app_id: str) -> bool:
        return self.db.delete_pa_application(app_id)

    # Step helpers: each maps the form payload into the stored application
    def update_personal_details(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"personal_details": {
            "surname": payload.get("surname", ""),
            "first_name": payload.get("first_name", ""),
            "middle_name": payload.get("middle_name", ""),
            "date_of_birth": payload.get("date_of_birth", ""),
            "email": payload.get("email", ""),
            "mobile_number": payload.get("mobile_number", ""),
            "national_id_number": payload.get("national_id_number", ""),
            "nationality": payload.get("nationality", ""),
            "tax_identification_number": payload.get("tax_identification_number", ""),
            "occupation": payload.get("occupation", ""),
            "gender": payload.get("gender", ""),
            "country_of_residence": payload.get("country_of_residence", ""),
            "physical_address": payload.get("physical_address", ""),
        }}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_next_of_kin(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"next_of_kin": {
            "first_name": payload.get("nok_first_name", ""),
            "last_name": payload.get("nok_last_name", ""),
            "middle_name": payload.get("nok_middle_name", ""),
            "phone_number": payload.get("nok_phone_number", ""),
            "relationship": payload.get("nok_relationship", ""),
            "address": payload.get("nok_address", ""),
            "id_number": payload.get("nok_id_number", ""),
        }}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_previous_policy(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw = (payload.get("_raw") or "").strip().lower() if payload else ""
        had = payload.get("had_previous_pa_policy") in ("yes", "Yes", True) or raw in ("yes", "y")
        updates = {"previous_pa_policy": {"had_policy": had, "insurer_name": payload.get("previous_insurer_name", "")}}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_physical_disability(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw = (payload.get("_raw") or "").strip().lower() if payload else ""
        free = payload.get("free_from_disability") in ("yes", "Yes", True) or raw in ("yes", "y")
        updates = {"physical_disability": {"free_from_disability": free, "details": payload.get("disability_details", "")}}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_risky_activities(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        activities = payload.get("risky_activities") or []
        if isinstance(activities, str):
            activities = [a.strip() for a in activities.split(",") if a.strip()]
        updates = {"risky_activities": {"selected": activities, "other_description": payload.get("risky_activity_other", "")}}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_coverage_selection(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        plan_id = payload.get("coverage_plan") or payload.get("_raw", "").strip()
        updates = {"coverage_plan": {"id": plan_id}}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_national_id_upload(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"national_id_upload": {"file_ref": payload.get("file_ref") or payload.get("national_id_file_ref", "")}}
        app = self.db.update_pa_application(app_id, updates)
        return self._to_dict(app) if app else None

    def finalize_and_create_quote(self, app_id: str, user_id: str, pricing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # create quote using existing DB helper
        app = self.db.get_pa_application(app_id)
        if not app:
            return None
        quote = self.db.create_quote(
            user_id=user_id,
            product_id=app.coverage_plan.get("id", "personal_accident"),
            premium_amount=pricing.get("monthly"),
            sum_assured=app.coverage_plan.get("sum_assured"),
            underwriting_data={
                "personal_details": app.personal_details,
                "next_of_kin": app.next_of_kin,
                "previous_pa_policy": app.previous_pa_policy,
                "physical_disability": app.physical_disability,
                "risky_activities": app.risky_activities,
            },
            pricing_breakdown=pricing.get("breakdown"),
            product_name="Personal Accident",
        )
        updates = {"quote_id": str(quote.id), "status": "quoted"}
        self.db.update_pa_application(app_id, updates)
        app = self.db.get_pa_application(app_id)
        return self._to_dict(app) if app else None

    def _to_dict(self, app):
        if not app:
            return None
        return {
            "id": app.id,
            "user_id": app.user_id,
            "status": app.status,
            "personal_details": app.personal_details,
            "next_of_kin": app.next_of_kin,
            "previous_pa_policy": app.previous_pa_policy,
            "physical_disability": app.physical_disability,
            "risky_activities": app.risky_activities,
            "coverage_plan": app.coverage_plan,
            "national_id_upload": app.national_id_upload,
            "quote_id": app.quote_id,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
        }
