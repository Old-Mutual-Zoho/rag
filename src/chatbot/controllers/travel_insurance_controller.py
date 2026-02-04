"""Controller for Travel Insurance flow persistence."""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TravelInsuranceController:
    def __init__(self, db):
        self.db = db

    def create_application(self, user_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        app = self.db.create_travel_application(user_id, initial_data or {})
        return self._to_dict(app)

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        app = self.db.get_travel_application(app_id)
        return self._to_dict(app) if app else None

    def list_applications(self, user_id: Optional[str] = None):
        apps = self.db.list_travel_applications(user_id=user_id)
        return [self._to_dict(a) for a in apps]

    def delete_application(self, app_id: str) -> bool:
        return self.db.delete_travel_application(app_id)

    # Step helpers
    def update_product_selection(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        product_id = payload.get("product_id") or payload.get("coverage_product") or payload.get("selected_product")
        selected = None
        if product_id:
            # Lookup from available products is up to caller; store minimal
            selected = {"id": product_id}
        updates = {"selected_product": selected} if selected else {}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_about_you(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"about_you": {
            "first_name": payload.get("first_name", ""),
            "middle_name": payload.get("middle_name", ""),
            "surname": payload.get("surname", ""),
            "phone_number": payload.get("phone_number", ""),
            "email": payload.get("email", ""),
        }}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_travel_party_and_trip(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"travel_party_and_trip": {
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
        }}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_data_consent(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"data_consent": {
            "terms_and_conditions_agreed": payload.get("terms_and_conditions_agreed") in (True, "yes", "true", "1"),
            "consent_data_outside_uganda": payload.get("consent_data_outside_uganda") in (True, "yes", "true", "1"),
            "consent_child_data": payload.get("consent_child_data") in (True, "yes", "true", "1"),
            "consent_marketing": payload.get("consent_marketing") in (True, "yes", "true", "1"),
        }}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_traveller_details(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        app = self.db.get_travel_application(app_id)
        travellers = app.travellers if app and app.travellers else []
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
        updates = {"travellers": travellers}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_emergency_contact(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"emergency_contact": {
            "surname": payload.get("ec_surname", ""),
            "relationship": payload.get("ec_relationship", ""),
            "phone_number": payload.get("ec_phone_number", ""),
            "email": payload.get("ec_email", ""),
            "home_address": payload.get("ec_home_address", ""),
        }}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_bank_details(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"bank_details": {
            "bank_name": payload.get("bank_name", ""),
            "account_holder_name": payload.get("account_holder_name", ""),
            "account_number": payload.get("account_number", ""),
            "bank_branch": payload.get("bank_branch", ""),
            "account_currency": payload.get("account_currency", ""),
        }}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def update_passport_upload(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        updates = {"passport_upload": {"file_ref": payload.get("passport_file_ref", "")}}
        app = self.db.update_travel_application(app_id, updates)
        return self._to_dict(app) if app else None

    def finalize_and_create_quote(self, app_id: str, user_id: str, pricing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        app = self.db.get_travel_application(app_id)
        if not app:
            return None
        quote = self.db.create_quote(
            user_id=user_id,
            product_id=app.selected_product.get("id", "travel_insurance"),
            premium_amount=pricing.get("total_ugx"),
            sum_assured=None,
            underwriting_data={
                "selected_product": app.selected_product,
                "about_you": app.about_you,
                "travel_party_and_trip": app.travel_party_and_trip,
                "travellers": app.travellers,
                "emergency_contact": app.emergency_contact,
            },
            pricing_breakdown=pricing.get("breakdown"),
            product_name=app.selected_product.get("label", "Travel Insurance"),
        )
        updates = {"quote_id": str(quote.id), "status": "quoted"}
        self.db.update_travel_application(app_id, updates)
        app = self.db.get_travel_application(app_id)
        return self._to_dict(app) if app else None

    def _to_dict(self, app):
        if not app:
            return None
        return {
            "id": app.id,
            "user_id": app.user_id,
            "status": app.status,
            "selected_product": app.selected_product,
            "about_you": app.about_you,
            "travel_party_and_trip": app.travel_party_and_trip,
            "data_consent": app.data_consent,
            "travellers": app.travellers,
            "emergency_contact": app.emergency_contact,
            "bank_details": app.bank_details,
            "passport_upload": app.passport_upload,
            "quote_id": app.quote_id,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
        }
