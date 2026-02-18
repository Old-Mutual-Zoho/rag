"""
Motor Private flow - Collect vehicle details, excess parameters, additional benefits,
premium calculation, user details, then proceed to payment.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict

from datetime import date

from src.chatbot.validation import (
    raise_if_errors,
    require_str,
    parse_int,
    parse_decimal_str,
    validate_email,
    validate_in,
    validate_phone_ug,
    validate_enum,
    validate_length_range,
    validate_uganda_mobile_frontend,
    validate_motor_email_frontend,
    validate_cover_start_date_range,
    validate_positive_number_field,
)

MOTOR_PRIVATE_EXCESS_PARAMETERS = [
    {
        "id": "excess_1",
        "label": "10% of claim, UGX 1,000,000 to UGX 3,000,000\n10% of total premium"
    },
    {
        "id": "excess_2",
        "label": "10% of claim, UGX 3,000,001 to UGX 4,000,000\n15% of total premium"
    },
    {
        "id": "excess_3",
        "label": "10% of claim, UGX 4,000,001 to UGX 5,000,000\n25% of total premium"
    }
]

MOTOR_PRIVATE_ADDITIONAL_BENEFITS = [
    {
        "id": "political_violence",
        "label": "Political violence and terrorism\n0.25% of Total Premium"
    },
    {
        "id": "alternative_accommodation",
        "label": "Alternative accommodation\nUGX 300,000 x days x 10%"
    },
    {
        "id": "car_hire",
        "label": "Car hire\nUGX 100,000 x days x 10%"
    }
]

MOTOR_PRIVATE_BENEFITS = [
    {"label": "Limit of liability: third party bodily injury per occurrence", "value": "UGX 20M"},
    {"label": "Limit of liability: third party bodily injury in aggregate", "value": "UGX 50M"},
    {"label": "Limit of liability: third party property damage per occurrence", "value": "UGX 20M"},
    {"label": "Limit of liability: third party property damage in aggregate", "value": "UGX 50M"},
    {"label": "Section 2: passenger liability per occurrence", "value": "UGX 20M"},
    {"label": "Section 2: passenger liability in aggregate per policy period", "value": "UGX 50M"},
    {"label": "Windscreen extension", "value": "UGX 2M"},
    {"label": "Authorized repair limit", "value": "UGX 2M"},
    {"label": "Towing/wreckage removal charges", "value": "UGX 2M"},
    {"label": "Locks and keys extension", "value": "UGX 2M"},
    {"label": "Fire extinguishing charges", "value": "UGX 2M"},
    {"label": "Protection and removal", "value": "UGX 2M"},
    {"label": "Claims preparation costs", "value": "UGX 1M"},
    {"label": "Personal effects excluding cash", "value": "UGX 500,000/="},
    {"label": "Personal accident to driver", "value": "UGX 1M"},
    {"label": "Unobtainable parts extension", "value": "UGX 2M"},
    {"label": "Limit of liability; section 111 – medical expenses", "value": "UGX 2M"},
    {"label": "Free Cleaning and Fumigation of Vehicles after Repair following an accident", "value": "UGX 1M"},
    {"label": "Modification of motor vehicle in case of Permanent Incapacitation of the driver following an accident", "value": "N/A"},
    {"label": "Rim Damage following a motor accident", "value": "UGX 1M"},
    {"label": "Alternative accommodation", "value": "N/A"},
    {"label": "Hire of replacement vehicle", "value": "N/A"},
]


class MotorPrivateFlow:
    """
    Guided flow for Motor Private: vehicle details, excess parameters, additional benefits,
    premium calculation, user details, then payment.
    """

    STEPS = [
        "vehicle_details",
        "excess_parameters",
        "additional_benefits",
        "benefits_summary",
        "premium_calculation",
        "about_you",
        "premium_and_download",
        "choose_plan_and_pay",
    ]

    def __init__(self, product_catalog, db):
        self.catalog = product_catalog
        self.db = db

    async def complete_flow(self, collected_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Finalize the flow from already-collected data.

        Convenience helper for tests/integrations that want to skip the step-by-step UI.
        """
        data = dict(collected_data or {})

        # Support frontend single-form submission using MotorPrivate.ts field names.
        # If frontend fields are present, validate and map them into the internal
        # guided-flow structure expected by the rest of this class.
        payload = data.copy()
        errors: Dict[str, str] = {}

        # Step 2: Personal Details
        first_name = None
        surname = None
        middle_name = None
        mobile_original = None
        mobile_normalized = None
        email = None
        if "firstName" in payload or "surname" in payload or "mobile" in payload or "email" in payload:
            first_name = validate_length_range(
                payload.get("firstName", ""),
                field="firstName",
                errors=errors,
                label="First name",
                min_len=2,
                max_len=50,
                required=True,
                message="First name must be 2–50 characters.",
            )
            middle_name = validate_length_range(
                payload.get("middleName", ""),
                field="middleName",
                errors=errors,
                label="Middle name",
                min_len=0,
                max_len=50,
                required=False,
                message="Middle name must be up to 50 characters.",
            )
            surname = validate_length_range(
                payload.get("surname", ""),
                field="surname",
                errors=errors,
                label="Surname",
                min_len=2,
                max_len=50,
                required=True,
                message="Surname must be 2–50 characters.",
            )
            mobile_original, mobile_normalized = validate_uganda_mobile_frontend(
                payload.get("mobile", ""), errors, field="mobile"
            )
            email = validate_motor_email_frontend(payload.get("email", ""), errors, field="email")

        # Step 1: coverType
        cover_type = None
        if "coverType" in payload:
            cover_type = validate_enum(
                payload.get("coverType", ""),
                field="coverType",
                errors=errors,
                allowed=["comprehensive", "third_party"],
                required=True,
                message="Please select a cover type.",
            )
        # Step 3: Premium Calculation
        vehicle_make_frontend = None
        year_frontend = None
        cover_start_frontend = None
        rare_model_frontend = None
        valuation_frontend = None
        vehicle_value_frontend = None
        if "vehicleMake" in payload or "yearOfManufacture" in payload or "coverStartDate" in payload:
            vehicle_make_frontend = require_str(payload, "vehicleMake", errors, label="Vehicle make")
            # 1980 -> current year + 1
            current_year_plus_one = date.today().year + 1
            year_frontend = parse_int(
                {"yearOfManufacture": payload.get("yearOfManufacture")},
                "yearOfManufacture",
                errors,
                min_value=1980,
                max_value=current_year_plus_one,
                required=True,
            )
            cover_start_frontend = validate_cover_start_date_range(
                payload.get("coverStartDate", ""), errors, field="coverStartDate"
            )
            rare_model_frontend = validate_enum(
                payload.get("isRareModel", ""),
                field="isRareModel",
                errors=errors,
                allowed=["yes", "no"],
                required=True,
                message="Please select if the vehicle is a rare model.",
            )
            valuation_frontend = validate_enum(
                payload.get("hasUndergoneValuation", ""),
                field="hasUndergoneValuation",
                errors=errors,
                allowed=["yes", "no"],
                required=True,
                message="Please indicate if the vehicle has undergone valuation.",
            )
            vehicle_value_frontend = validate_positive_number_field(
                payload.get("vehicleValueUgx", ""),
                field="vehicleValueUgx",
                errors=errors,
                message="Vehicle value must be a positive number.",
            )

        raise_if_errors(errors)  # If any of the above validations ran and failed

        # Map validated frontend fields into the internal structure the rest of
        # the flow expects, but only when present to avoid breaking callers
        # that already send the internal guided-flow shape.
        internal = data.setdefault("motor_frontend", {})
        if cover_type is not None:
            internal["cover_type"] = cover_type
        if first_name is not None:
            internal["first_name"] = first_name
        if middle_name is not None:
            internal["middle_name"] = middle_name
        if surname is not None:
            internal["surname"] = surname
        if mobile_original is not None:
            internal["mobile"] = mobile_original
        if mobile_normalized:
            internal["mobile_normalized"] = mobile_normalized  # e.g. 2567XXXXXXXX
        if email is not None:
            internal["email"] = email
        if vehicle_make_frontend is not None:
            internal["vehicle_make"] = vehicle_make_frontend
        if year_frontend is not None:
            internal["year_of_manufacture"] = year_frontend
        if cover_start_frontend is not None:
            internal["cover_start_date"] = cover_start_frontend
        if rare_model_frontend is not None:
            internal["rare_model"] = rare_model_frontend
        if valuation_frontend is not None:
            internal["valuation_done"] = valuation_frontend
        if vehicle_value_frontend is not None:
            internal["vehicle_value"] = vehicle_value_frontend

        data.setdefault("user_id", user_id)
        data.setdefault("product_id", "motor_private")

        result = await self._step_choose_plan_and_pay({"action": "proceed_to_pay"}, data, user_id)
        result.setdefault("status", "success")
        return result

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        data = dict(initial_data or {})
        data.setdefault("user_id", user_id)
        data.setdefault("product_id", "motor_private")
        return await self.process_step("", 0, data, user_id)

    async def process_step(
        self,
        user_input: str,
        current_step: int,
        collected_data: Dict[str, Any],
        user_id: str,
    ) -> Dict:
        try:
            if user_input and isinstance(user_input, str) and user_input.strip().startswith("{"):
                payload = json.loads(user_input)
            elif user_input and isinstance(user_input, dict):
                payload = user_input
            else:
                payload = {"_raw": user_input} if user_input else {}
        except (json.JSONDecodeError, TypeError):
            payload = {"_raw": user_input} if user_input else {}

        if current_step == 0:
            return await self._step_vehicle_details(payload, collected_data, user_id)
        if current_step == 1:
            return await self._step_excess_parameters(payload, collected_data, user_id)
        if current_step == 2:
            return await self._step_additional_benefits(payload, collected_data, user_id)
        if current_step == 3:
            return await self._step_benefits_summary(payload, collected_data, user_id)
        if current_step == 4:
            return await self._step_premium_calculation(payload, collected_data, user_id)
        if current_step == 5:
            return await self._step_about_you(payload, collected_data, user_id)
        if current_step == 6:
            return await self._step_premium_and_download(payload, collected_data, user_id)
        if current_step == 7:
            return await self._step_choose_plan_and_pay(payload, collected_data, user_id)
        return {"error": "Invalid step"}

    async def _step_vehicle_details(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            errors: Dict[str, str] = {}
            vehicle_make = require_str(payload, "vehicle_make", errors, label="Vehicle make")
            year = parse_int(
                payload,
                "year_of_manufacture",
                errors,
                min_value=1980,
                max_value=date.today().year + 1,
                required=True,
            )
            cover_start_date = validate_cover_start_date_range(
                payload.get("cover_start_date", ""), errors, field="cover_start_date"
            )
            rare_model = validate_in(
                payload.get("rare_model", ""),
                {"Yes", "No"},
                errors,
                "rare_model",
                required=True,
            )
            valuation_done = validate_in(
                payload.get("valuation_done", ""),
                {"Yes", "No"},
                errors,
                "valuation_done",
                required=True,
            )
            vehicle_value = parse_decimal_str(payload, "vehicle_value", errors, min_value=1, required=True)
            first_time_registration = validate_in(
                payload.get("first_time_registration", ""),
                {"Yes", "No"},
                errors,
                "first_time_registration",
                required=True,
            )
            car_alarm_installed = validate_in(
                payload.get("car_alarm_installed", ""),
                {"Yes", "No"},
                errors,
                "car_alarm_installed",
                required=True,
            )
            tracking_system_installed = validate_in(
                payload.get("tracking_system_installed", ""),
                {"Yes", "No"},
                errors,
                "tracking_system_installed",
                required=True,
            )
            car_usage_region = validate_in(
                payload.get("car_usage_region", ""),
                {"Within Uganda", "Within East Africa", "Outside East Africa"},
                errors,
                "car_usage_region",
                required=True,
            )
            raise_if_errors(errors)

            data["vehicle_details"] = {
                "vehicle_make": vehicle_make,
                "year_of_manufacture": str(year),
                "cover_start_date": cover_start_date,
                "rare_model": rare_model,
                "valuation_done": valuation_done,
                "vehicle_value": vehicle_value,
                "first_time_registration": first_time_registration,
                "car_alarm_installed": car_alarm_installed,
                "tracking_system_installed": tracking_system_installed,
                "car_usage_region": car_usage_region,
            }
        return {
            "response": {
                "type": "form",
                "message": "Premium Calculation - Vehicle Details",
                "fields": [
                    {"name": "vehicle_make", "label": "Choose vehicle make", "type": "select", "required": True},
                    {"name": "year_of_manufacture", "label": "Year of manufacture", "type": "text", "required": True},
                    {"name": "cover_start_date", "label": "Cover start date", "type": "date", "required": True},
                    {"name": "rare_model", "label": "Is the car a rare model?", "type": "radio", "options": ["Yes", "No"], "required": True},
                    {"name": "valuation_done", "label": "Has the vehicle undergone valuation?", "type": "radio", "options": ["Yes", "No"], "required": True},
                    {"name": "vehicle_value", "label": "Value of Vehicle (UGX)", "type": "number", "required": True},
                    {"name": "first_time_registration", "label": "First time this vehicle is registered for this type of insurance?", "type": "radio",
                     "options": ["Yes", "No"], "required": True},
                    {"name": "car_alarm_installed", "label": "Do you have a car alarm installed?", "type": "radio",
                     "options": ["Yes", "No"], "required": True},
                    {"name": "tracking_system_installed", "label": "Do you have a tracking system installed?", "type": "radio",
                     "options": ["Yes", "No"], "required": True},
                    {"name": "car_usage_region", "label": "Car usage: within Uganda, East Africa, or outside East Africa?", "type": "radio",
                     "options": ["Within Uganda", "Within East Africa", "Outside East Africa"], "required": True},
                ],
            },
            "next_step": 1,
            "collected_data": data,
        }

    async def _step_excess_parameters(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            selected = payload.get("excess_parameters") or []
            if isinstance(selected, str):
                selected = [s.strip() for s in selected.split(",") if s.strip()]
            data["excess_parameters"] = selected
        return {
            "response": {
                "type": "checkbox",
                "message": "Excess Parameters",
                "options": MOTOR_PRIVATE_EXCESS_PARAMETERS,
            },
            "next_step": 2,
            "collected_data": data,
        }

    async def _step_additional_benefits(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            selected = payload.get("additional_benefits") or []
            if isinstance(selected, str):
                selected = [s.strip() for s in selected.split(",") if s.strip()]
            data["additional_benefits"] = selected
        return {
            "response": {
                "type": "checkbox",
                "message": "Additional Benefits",
                "options": MOTOR_PRIVATE_ADDITIONAL_BENEFITS,
            },
            "next_step": 3,
            "collected_data": data,
        }

    async def _step_benefits_summary(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        return {
            "response": {
                "type": "benefits_summary",
                "message": "Benefits",
                "benefits": MOTOR_PRIVATE_BENEFITS,
            },
            "next_step": 4,
            "collected_data": data,
        }

    async def _step_premium_calculation(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        # Accept vehicle details and calculate base premium
        if payload and "_raw" not in payload:
            data["premium_calculation"] = {
                "base_premium": payload.get("base_premium", ""),
                "training_levy": payload.get("training_levy", ""),
                "sticker_fees": payload.get("sticker_fees", ""),
                "vat": payload.get("vat", ""),
                "stamp_duty": payload.get("stamp_duty", ""),
            }
        # For demo, calculate a sample premium
        premium = self._calculate_motor_private_premium(data)
        return {
            "response": {
                "type": "premium_summary",
                "message": "Premium Calculation",
                "quote_summary": premium,
                "actions": [
                    {"type": "edit", "label": "Edit"},
                    {"type": "download_quote", "label": "Download Quote"},
                ],
            },
            "next_step": 5,
            "collected_data": data,
        }

    async def _step_about_you(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            errors: Dict[str, str] = {}
            first_name = validate_length_range(
                payload.get("first_name", ""),
                field="first_name",
                errors=errors,
                label="First name",
                min_len=2,
                max_len=50,
                required=True,
                message="First name must be 2–50 characters.",
            )
            middle_name = validate_length_range(
                payload.get("middle_name", ""),
                field="middle_name",
                errors=errors,
                label="Middle name",
                min_len=0,
                max_len=50,
                required=False,
                message="Middle name must be up to 50 characters.",
            )
            surname = validate_length_range(
                payload.get("surname", ""),
                field="surname",
                errors=errors,
                label="Surname",
                min_len=2,
                max_len=50,
                required=True,
                message="Surname must be 2–50 characters.",
            )
            # Keep existing guided-flow phone/email validators for compatibility
            phone_number = validate_phone_ug(payload.get("phone_number", ""), errors, field="phone_number")
            email = validate_email(payload.get("email", ""), errors, field="email")
            raise_if_errors(errors)
            data["about_you"] = {
                "first_name": first_name,
                "middle_name": middle_name,
                "surname": surname,
                "phone_number": phone_number,
                "email": email,
            }
        return {
            "response": {
                "type": "form",
                "message": "About You",
                "fields": [
                    {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                    {"name": "middle_name", "label": "Middle Name (Optional)", "type": "text", "required": False},
                    {"name": "surname", "label": "Surname", "type": "text", "required": True},
                    {"name": "phone_number", "label": "Phone Number", "type": "text", "required": True},
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                ],
            },
            "next_step": 6,
            "collected_data": data,
        }

    async def _step_premium_and_download(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        premium = self._calculate_motor_private_premium(data)
        return {
            "response": {
                "type": "premium_summary",
                "message": "Premium Calculation",
                "quote_summary": premium,
                "actions": [
                    {"type": "edit", "label": "Edit"},
                    {"type": "download_quote", "label": "Download Quote"},
                    {"type": "proceed_to_pay", "label": "Proceed to Pay"},
                ],
            },
            "next_step": 7,
            "collected_data": data,
        }

    async def _step_choose_plan_and_pay(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        action = (payload.get("action") or payload.get("_raw") or "").strip().lower()
        if "edit" in action:
            out = await self._step_vehicle_details(payload, data, user_id)
            out["next_step"] = 0
            return out
        # Proceed to pay: create quote and hand off to payment flow
        premium = self._calculate_motor_private_premium(data)
        quote = self.db.create_quote(
            user_id=user_id,
            product_id=data.get("product_id", "motor_private"),
            premium_amount=premium["total"],
            sum_assured=None,
            underwriting_data=data,
            pricing_breakdown=premium,
            product_name="Motor Private",
        )
        data["quote_id"] = str(quote.id)
        return {
            "response": {
                "type": "proceed_to_payment",
                "message": "Proceeding to payment. Choose your payment method.",
                "quote_id": str(quote.id),
            },
            "complete": True,
            "next_flow": "payment",
            "collected_data": data,
            "data": {"quote_id": str(quote.id)},
        }

    def _calculate_motor_private_premium(self, data: Dict) -> Dict:
        """Sample premium calculation for Motor Private."""
        # These are illustrative values, replace with actual logic as needed
        base_premium = Decimal("1280000")
        training_levy = Decimal("6400")
        sticker_fees = Decimal("6000")
        vat = Decimal("232632")
        stamp_duty = Decimal("35000")
        total = base_premium + training_levy + sticker_fees + vat + stamp_duty
        return {
            "base_premium": float(base_premium),
            "training_levy": float(training_levy),
            "sticker_fees": float(sticker_fees),
            "vat": float(vat),
            "stamp_duty": float(stamp_duty),
            "total": float(total),
        }
