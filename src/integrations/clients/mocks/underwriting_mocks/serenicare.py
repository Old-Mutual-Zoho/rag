"""Serenicare-specific underwriting mock builder."""

from __future__ import annotations

from typing import Any, Dict, List


def build_serenicare_mock(payload: Dict[str, Any], quote_id: str) -> Dict[str, Any]:
    plan_option = payload.get("plan_option") or payload.get("plan") or {}
    if not isinstance(plan_option, dict):
        plan_option = {}

    plan_id = str(plan_option.get("id") or payload.get("plan_id") or "essential").strip().lower()
    base_by_plan = {
        "essential": 90000.0,
        "enhanced": 130000.0,
        "premium": 180000.0,
    }
    base_monthly = float(base_by_plan.get(plan_id, base_by_plan["essential"]))

    optional_benefits = payload.get("optional_benefits") or payload.get("selected_optional_benefits") or []
    if not isinstance(optional_benefits, list):
        optional_benefits = []

    optional_loading = float(len(optional_benefits) * 5000)
    monthly_premium = base_monthly + optional_loading

    medical_conditions = payload.get("medical_conditions") or payload.get("pre_existing_conditions") or []
    has_medical_conditions = False
    if isinstance(medical_conditions, list):
        has_medical_conditions = len(medical_conditions) > 0
    elif isinstance(medical_conditions, str):
        has_medical_conditions = medical_conditions.strip().lower() not in {"", "none", "no"}
    elif isinstance(medical_conditions, bool):
        has_medical_conditions = medical_conditions

    requirements: List[Dict[str, Any]] = []
    decision_status = "approved"
    if has_medical_conditions:
        decision_status = "pending_review"
        requirements.append(
            {
                "code": "medical_report",
                "message": "Please provide a recent medical report for final underwriting review.",
            }
        )

    return {
        "quote_id": quote_id,
        "premium": monthly_premium,
        "currency": "UGX",
        "decision_status": decision_status,
        "requirements": requirements,
        "product_mock": "serenicare",
        "plan_id": plan_id,
        "breakdown": {
            "base_monthly": base_monthly,
            "optional_benefits_loading": optional_loading,
            "monthly_total": monthly_premium,
            "annual_total": monthly_premium * 12,
        },
    }
