"""Controller for Motor Private full-form submissions.

This controller wraps MotorPrivateFlow.complete_flow so that motor-specific
validations and quote creation are encapsulated outside the FastAPI layer.
"""

from typing import Any, Dict, Optional

from src.chatbot.validation import (
    validate_length_range,
    validate_enum,
    validate_motor_email_frontend,
    validate_uganda_mobile_frontend,
    raise_if_errors,
)


class MotorPrivateController:

    def __init__(self, db):
        self.db = db

    def create_application(self, user_id: str, initial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        app = self.db.create_motor_private_application(user_id, initial_data or {})
        return self._to_dict(app)

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        app = self.db.get_motor_private_application(app_id)
        return self._to_dict(app) if app else None

    def list_applications(self, user_id: Optional[str] = None, order_by: str = "created_at", descending: bool = True):
        apps = self.db.list_motor_private_applications(user_id=user_id, order_by=order_by, descending=descending)
        return [self._to_dict(a) for a in apps]

    def delete_application(self, app_id: str) -> bool:
        return self.db.delete_motor_private_application(app_id)

    def update_motor_private_form(self, app_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update Motor Private application with full form payload and validate all fields.
        """
        errors: Dict[str, str] = {}
        # Step 1: Get A Quote
        cover_type = validate_enum(
            payload.get("coverType", ""),
            field="coverType",
            errors=errors,
            allowed=["comprehensive", "third_party"],
            required=True,
            message="Please select a cover type."
        )
        # Step 2: Personal Details
        first_name = validate_length_range(
            payload.get("firstName", ""),
            field="firstName",
            errors=errors,
            label="First Name",
            min_len=2,
            max_len=50,
            required=True
        )
        middle_name = validate_length_range(
            payload.get("middleName", ""),
            field="middleName",
            errors=errors,
            label="Middle Name",
            min_len=0,
            max_len=50,
            required=False
        )
        surname = validate_length_range(
            payload.get("surname", ""),
            field="surname",
            errors=errors,
            label="Surname",
            min_len=2,
            max_len=50,
            required=True
        )
        _, mobile = validate_uganda_mobile_frontend(payload.get("mobile", ""), errors, field="mobile")
        email = validate_motor_email_frontend(payload.get("email", ""), errors, field="email")
        # Step 3: Premium Calculation
        vehicle_make = validate_enum(
            payload.get("vehicleMake", ""),
            field="vehicleMake",
            errors=errors,
            allowed=self.db.get_vehicle_make_options(),
            required=True,
            message="Please select a valid vehicle make."
        )
        # yearOfManufacture
        year_of_manufacture = payload.get("yearOfManufacture")
        try:
            year_of_manufacture = int(year_of_manufacture)
            from datetime import date
            current_year = date.today().year
            if not (1980 <= year_of_manufacture <= current_year + 1):
                errors["yearOfManufacture"] = "Year of manufacture must be between 1980 and next year."
        except Exception:
            errors["yearOfManufacture"] = "Year of manufacture must be a valid integer."
        # coverStartDate
        cover_start_date = payload.get("coverStartDate", "")
        try:
            from datetime import datetime, timedelta
            cover_date = datetime.fromisoformat(cover_start_date)
            today = datetime.now().date()
            if not (today <= cover_date.date() <= today + timedelta(days=90)):
                errors["coverStartDate"] = "Cover start date must be within the next 90 days."
        except Exception:
            errors["coverStartDate"] = "Cover start date must be a valid date (YYYY-MM-DD)."
        # isRareModel
        is_rare_model = validate_enum(
            payload.get("isRareModel", ""),
            field="isRareModel",
            errors=errors,
            allowed=["yes", "no"],
            required=True,
            message="Please select if the vehicle is a rare model."
        )
        # hasUndergoneValuation
        has_undergone_valuation = validate_enum(
            payload.get("hasUndergoneValuation", ""),
            field="hasUndergoneValuation",
            errors=errors,
            allowed=["yes", "no"],
            required=True,
            message="Please indicate if the vehicle has undergone valuation."
        )
        # vehicleValueUgx
        vehicle_value_ugx = payload.get("vehicleValueUgx")
        try:
            vehicle_value_ugx = float(vehicle_value_ugx)
            if vehicle_value_ugx <= 0:
                errors["vehicleValueUgx"] = "Vehicle value must be a positive number."
        except Exception:
            errors["vehicleValueUgx"] = "Vehicle value must be a positive number."
        raise_if_errors(errors)
        updates = {
            "cover_type": cover_type,
            "first_name": first_name,
            "middle_name": middle_name,
            "surname": surname,
            "mobile": mobile,
            "email": email,
            "vehicle_make": vehicle_make,
            "year_of_manufacture": year_of_manufacture,
            "cover_start_date": cover_start_date,
            "is_rare_model": is_rare_model,
            "has_undergone_valuation": has_undergone_valuation,
            "vehicle_value_ugx": vehicle_value_ugx,
        }
        app = self.db.update_motor_private_application(app_id, updates)
        return self._to_dict(app) if app else None

    def _to_dict(self, app):
        if not app:
            return None
        return {
            "id": app.id,
            "user_id": app.user_id,
            "status": app.status,
            "cover_type": app.cover_type,
            "first_name": app.first_name,
            "middle_name": app.middle_name,
            "surname": app.surname,
            "mobile": app.mobile,
            "email": app.email,
            "vehicle_make": app.vehicle_make,
            "year_of_manufacture": app.year_of_manufacture,
            "cover_start_date": app.cover_start_date,
            "is_rare_model": app.is_rare_model,
            "has_undergone_valuation": app.has_undergone_valuation,
            "vehicle_value_ugx": app.vehicle_value_ugx,
            "quote_id": app.quote_id,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
        }
