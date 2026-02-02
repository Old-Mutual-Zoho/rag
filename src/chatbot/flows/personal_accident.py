"""
Personal Accident flow - Collect personal details, next of kin, underwriting questions,
coverage selection, ID upload, premium calculation, then proceed to payment.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict

from datetime import datetime


# Risky activities for the checkbox step (per product requirements)
PERSONAL_ACCIDENT_RISKY_ACTIVITIES = [
    {"id": "manufacture_wire_works", "label": "Manufacture of wire works"},
    {"id": "mining", "label": "Mining / Quarrying"},
    {"id": "explosives", "label": "Handling explosives or flammable materials"},
    {"id": "construction_heights", "label": "Construction work at heights"},
    {"id": "diving", "label": "Underwater diving"},
    {"id": "racing", "label": "Motor or speed racing"},
    {"id": "other_risky", "label": "Other risky activity (please specify in next step)"},
]

# Placeholder coverage tiers for "choose coverage" step
PERSONAL_ACCIDENT_COVERAGE_PLANS = [
    {"id": "basic", "label": "Basic", "sum_assured": 10_000_000, "description": "Essential accident cover"},
    {"id": "standard", "label": "Standard", "sum_assured": 25_000_000, "description": "Broader benefits"},
    {"id": "premium", "label": "Premium", "sum_assured": 50_000_000, "description": "Highest cover and benefits"},
]


class PersonalAccidentFlow:
    """
    Guided flow for Personal Accident: personal details, next of kin,
    underwriting questions, coverage, ID upload, premium, then payment.
    """

    STEPS = [
        "personal_details",
        "next_of_kin",
        "previous_pa_policy",
        "physical_disability",
        "risky_activities",
        "coverage_selection",
        "upload_national_id",
        "premium_and_download",
        "choose_plan_and_pay",
    ]

    def __init__(self, product_catalog, db):
        self.catalog = product_catalog
        self.db = db

    async def complete_flow(self, collected_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Finalize the flow from already-collected data.

        This is primarily a convenience helper for tests and integrations that already
        have all required data and simply need a quote/payment handoff.
        """
        data = dict(collected_data or {})
        data.setdefault("user_id", user_id)
        data.setdefault("product_id", "personal_accident")

        result = await self._step_choose_plan_and_pay({"action": "proceed_to_pay"}, data, user_id)
        result.setdefault("status", "success")
        return result

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        """Start Personal Accident flow"""
        data = dict(initial_data or {})
        data.setdefault("user_id", user_id)
        data.setdefault("product_id", "personal_accident")
        return await self.process_step("", 0, data, user_id)

    async def process_step(
        self,
        user_input: str,
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

        if current_step == 0:
            return await self._step_personal_details(payload, collected_data, user_id)
        if current_step == 1:
            return await self._step_next_of_kin(payload, collected_data, user_id)
        if current_step == 2:
            return await self._step_previous_pa_policy(payload, collected_data, user_id)
        if current_step == 3:
            return await self._step_physical_disability(payload, collected_data, user_id)
        if current_step == 4:
            return await self._step_risky_activities(payload, collected_data, user_id)
        if current_step == 5:
            return await self._step_coverage_selection(payload, collected_data, user_id)
        if current_step == 6:
            return await self._step_upload_national_id(payload, collected_data, user_id)
        if current_step == 7:
            return await self._step_premium_and_download(payload, collected_data, user_id)
        if current_step == 8:
            return await self._step_choose_plan_and_pay(payload, collected_data, user_id)

        return {"error": "Invalid step"}

    async def _step_personal_details(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["personal_details"] = {
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
            }

        return {
            "response": {
                "type": "form",
                "message": "📋 Personal details for Personal Accident cover",
                "fields": [
                    {"name": "surname", "label": "Surname", "type": "text", "required": True},
                    {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                    {"name": "middle_name", "label": "Middle Name", "type": "text", "required": False},
                    {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                    {"name": "email", "label": "Email Address", "type": "email", "required": True},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "tel", "required": True, "placeholder": "07XX XXX XXX"},
                    {"name": "national_id_number", "label": "National ID Number", "type": "text", "required": True},
                    {"name": "nationality", "label": "Nationality", "type": "text", "required": True},
                    {"name": "tax_identification_number", "label": "Tax Identification Number", "type": "text", "required": False},
                    {"name": "occupation", "label": "Occupation", "type": "text", "required": True},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["Male", "Female", "Other"], "required": True},
                    {"name": "country_of_residence", "label": "Country of Residence", "type": "text", "required": True},
                    {"name": "physical_address", "label": "Physical Address", "type": "text", "required": True},
                ],
            },
            "next_step": 1,
            "collected_data": data,
        }

    async def _step_next_of_kin(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["next_of_kin"] = {
                "first_name": payload.get("nok_first_name", ""),
                "last_name": payload.get("nok_last_name", ""),
                "middle_name": payload.get("nok_middle_name", ""),
                "phone_number": payload.get("nok_phone_number", ""),
                "relationship": payload.get("nok_relationship", ""),
                "address": payload.get("nok_address", ""),
                "id_number": payload.get("nok_id_number", ""),
            }

        return {
            "response": {
                "type": "form",
                "message": "👥 Next of kin details",
                "fields": [
                    {"name": "nok_first_name", "label": "First Name", "type": "text", "required": True},
                    {"name": "nok_last_name", "label": "Last Name", "type": "text", "required": True},
                    {"name": "nok_middle_name", "label": "Middle Name", "type": "text", "required": False},
                    {"name": "nok_phone_number", "label": "Phone Number", "type": "tel", "required": True},
                    {"name": "nok_relationship", "label": "Relationship", "type": "text", "required": True},
                    {"name": "nok_address", "label": "Address", "type": "text", "required": True},
                    {"name": "nok_id_number", "label": "ID Number", "type": "text", "required": False},
                ],
            },
            "next_step": 2,
            "collected_data": data,
        }

    async def _step_previous_pa_policy(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        raw = (payload.get("_raw") or "").strip().lower() if payload else ""
        if payload:
            had = payload.get("had_previous_pa_policy") in ("yes", "Yes", True) or raw in ("yes", "y")
            data["previous_pa_policy"] = {
                "had_policy": had,
                "insurer_name": payload.get("previous_insurer_name", ""),
            }

        return {
            "response": {
                "type": "yes_no_details",
                "message": "Have you previously had a Personal Accident policy?",
                "question_id": "previous_pa_policy",
                "options": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
                "details_field": {
                    "name": "previous_insurer_name",
                    "label": "Name of insurer",
                    "show_when": "yes",
                },
            },
            "next_step": 3,
            "collected_data": data,
        }

    async def _step_physical_disability(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        raw = (payload.get("_raw") or "").strip().lower() if payload else ""
        if payload:
            free = payload.get("free_from_disability") in ("yes", "Yes", True) or raw in ("yes", "y")
            data["physical_disability"] = {
                "free_from_disability": free,
                "details": payload.get("disability_details", ""),
            }

        return {
            "response": {
                "type": "yes_no_details",
                "message": "Are you free from any physical disability?",
                "question_id": "physical_disability",
                "options": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
                "details_field": {
                    "name": "disability_details",
                    "label": "Please give details",
                    "show_when": "no",
                },
            },
            "next_step": 4,
            "collected_data": data,
        }

    async def _step_risky_activities(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            activities = payload.get("risky_activities") or []
            if isinstance(activities, str):
                activities = [a.strip() for a in activities.split(",") if a.strip()]
            data["risky_activities"] = {
                "selected": activities,
                "other_description": payload.get("risky_activity_other", ""),
            }

        return {
            "response": {
                "type": "checkbox",
                "message": "Are you engaged in any of these activities? (Select all that apply)",
                "options": PERSONAL_ACCIDENT_RISKY_ACTIVITIES,
                "allow_other": True,
                "other_field": {"name": "risky_activity_other", "label": "Other (please specify)"},
            },
            "next_step": 5,
            "collected_data": data,
        }

    async def _step_coverage_selection(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            plan_id = payload.get("coverage_plan") or payload.get("_raw", "").strip()
            if plan_id:
                plan = next((p for p in PERSONAL_ACCIDENT_COVERAGE_PLANS if p["id"] == plan_id), None)
                if plan:
                    data["coverage_plan"] = plan

        return {
            "response": {
                "type": "options",
                "message": "Choose your coverage",
                "options": [
                    {
                        "id": p["id"],
                        "label": f"{p['label']} – UGX {p['sum_assured']:,}",
                        "description": p["description"],
                    }
                    for p in PERSONAL_ACCIDENT_COVERAGE_PLANS
                ],
            },
            "next_step": 6,
            "collected_data": data,
        }

    async def _step_upload_national_id(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        if payload and "_raw" not in payload:
            data["national_id_upload"] = {
                "file_ref": payload.get("file_ref") or payload.get("national_id_file_ref", ""),
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        return {
            "response": {
                "type": "file_upload",
                "message": "📄 Upload your National ID (PDF)",
                "accept": "application/pdf",
                "field_name": "national_id_file_ref",
                "max_size_mb": 5,
                "help": "Upload a clear PDF of your National ID.",
            },
            "next_step": 7,
            "collected_data": data,
        }

    async def _step_premium_and_download(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        # Accept file_ref from previous step if not yet stored
        if payload and payload.get("national_id_file_ref") and not data.get("national_id_upload"):
            data["national_id_upload"] = {
                "file_ref": payload.get("national_id_file_ref", ""),
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        plan = data.get("coverage_plan") or PERSONAL_ACCIDENT_COVERAGE_PLANS[0]
        sum_assured = plan.get("sum_assured", 10_000_000)
        premium = self._calculate_pa_premium(data, sum_assured)

        return {
            "response": {
                "type": "premium_summary",
                "message": "💰 Your Personal Accident premium",
                "product_name": "Personal Accident",
                "sum_assured": sum_assured,
                "monthly_premium": premium["monthly"],
                "annual_premium": premium["annual"],
                "breakdown": premium.get("breakdown", {}),
                "download_option": True,
                "download_label": "Download summary (PDF)",
                "actions": [
                    {"type": "view_all_plans", "label": "View all plans"},
                    {"type": "proceed_to_pay", "label": "Choose this plan and proceed to pay"},
                ],
            },
            "next_step": 8,
            "collected_data": data,
        }

    async def _step_choose_plan_and_pay(self, payload: Dict, data: Dict, user_id: str) -> Dict:
        action = (payload.get("action") or payload.get("_raw") or "").strip().lower()

        if "view" in action or "plan" in action:
            # Back to coverage selection (step 5)
            out = await self._step_coverage_selection(payload, data, user_id)
            out["next_step"] = 5
            return out

        # Proceed to pay: create quote and hand off to payment flow
        plan = data.get("coverage_plan") or PERSONAL_ACCIDENT_COVERAGE_PLANS[0]
        sum_assured = plan.get("sum_assured", 10_000_000)
        premium = self._calculate_pa_premium(data, sum_assured)

        quote = self.db.create_quote(
            user_id=user_id,
            product_id=data.get("product_id", "personal_accident"),
            premium_amount=premium["monthly"],
            sum_assured=sum_assured,
            underwriting_data=data,
            pricing_breakdown=premium.get("breakdown"),
            product_name="Personal Accident",
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

    def _calculate_pa_premium(self, data: Dict, sum_assured: int) -> Dict:
        """Simple premium calculation for Personal Accident."""
        base_rate = Decimal("0.15")  # 15% of sum assured per year (illustrative)
        annual = (Decimal(sum_assured) * base_rate) / 100
        monthly = annual / 12

        # Loadings
        breakdown = {"base": float(annual)}
        if data.get("risky_activities", {}).get("selected"):
            loading = Decimal("0.10") * annual
            annual += loading
            monthly = annual / 12
            breakdown["risky_activities_loading"] = float(loading)

        return {
            "annual": float(annual.quantize(Decimal("0.01"))),
            "monthly": float(monthly.quantize(Decimal("0.01"))),
            "breakdown": breakdown,
        }
