"""Personal Accident-specific underwriting mock builder."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List


def build_personal_accident_mock(payload: Dict[str, Any], quote_id: str) -> Dict[str, Any]:
    money_step = Decimal("0.01")

    def q(amount: Decimal) -> Decimal:
        return amount.quantize(money_step, rounding=ROUND_HALF_UP)

    def to_decimal(value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            return Decimal(str(value).replace(",", "").strip())
        raise InvalidOperation

    requirements: List[Dict[str, Any]] = []

    # Flow-aligned input key for Personal Accident cover amount.
    cover_raw = payload.get("coverLimitAmountUgx")
    sum_assured = Decimal("0")
    cover_valid = True
    try:
        if cover_raw in (None, ""):
            raise InvalidOperation
        sum_assured = q(to_decimal(cover_raw))
    except (InvalidOperation, ValueError, TypeError):
        cover_valid = False
        requirements.append(
            {
                "type": "validation",
                "field": "coverLimitAmountUgx",
                "message": "Cover amount is required and must be a valid number.",
            }
        )

    # Flow-aligned input key for date of birth; used for eligibility checks and pricing modifiers.
    dob_raw = payload.get("dob")
    age_years: int | None = None
    if dob_raw not in (None, ""):
        try:
            dob_value = datetime.fromisoformat(str(dob_raw)).date()
            today = date.today()
            age_years = today.year - dob_value.year - ((today.month, today.day) < (dob_value.month, dob_value.day))
        except (ValueError, TypeError):
            requirements.append(
                {
                    "type": "validation",
                    "field": "dob",
                    "message": "Date of birth must be a valid ISO date (YYYY-MM-DD).",
                }
            )
    else:
        requirements.append(
            {
                "type": "validation",
                "field": "dob",
                "message": "Date of birth is required for underwriting eligibility.",
            }
        )

    # Flow-aligned input key for risky activities.
    risky_input = payload.get("riskyActivities", [])
    if isinstance(risky_input, list):
        has_risky_activities = len(risky_input) > 0
    elif isinstance(risky_input, str):
        has_risky_activities = risky_input.strip().lower() not in {"", "none", "no"}
    else:
        has_risky_activities = False

    # Eligibility rule: minors are declined (hard eligibility fail, not manually reviewable).
    if age_years is not None and age_years < 18:
        requirements.append(
            {
                "type": "eligibility",
                "field": "dob",
                "message": "Applicant must be at least 18 years old for Personal Accident cover.",
            }
        )

    # Validation/eligibility rule: non-positive cover is invalid and declined.
    if cover_valid and sum_assured <= Decimal("0"):
        requirements.append(
            {
                "type": "eligibility",
                "field": "coverLimitAmountUgx",
                "message": "Cover amount must be greater than zero.",
            }
        )

    # Underwriting rule: very high cover is referred for manual review (not auto-declined).
    if cover_valid and sum_assured > Decimal("200000000"):
        requirements.append(
            {
                "type": "underwriting",
                "field": "coverLimitAmountUgx",
                "message": "Cover amount exceeds auto-approval threshold and requires manual underwriting review.",
            }
        )

    # Underwriting rule: any risky activity is referred for manual underwriter assessment.
    if has_risky_activities:
        requirements.append(
            {
                "type": "underwriting",
                "field": "riskyActivities",
                "message": "Risky activities declared; application requires manual underwriting review.",
            }
        )

    decline_reasons = {
        "Cover amount is required and must be a valid number.",
        "Cover amount must be greater than zero.",
        "Applicant must be at least 18 years old for Personal Accident cover.",
        "Date of birth must be a valid ISO date (YYYY-MM-DD).",
        "Date of birth is required for underwriting eligibility.",
    }
    has_decline_reason = any(req.get("message") in decline_reasons for req in requirements)
    has_referral_reason = any(req.get("type") == "underwriting" for req in requirements)

    # Decision precedence:
    # 1) DECLINED for hard validation/eligibility failures.
    # 2) REFERRED for cases needing human underwriter judgment.
    # 3) APPROVED when no blocking conditions exist.
    if has_decline_reason:
        decision_status = "DECLINED"
    elif has_referral_reason:
        decision_status = "REFERRED"
    else:
        decision_status = "APPROVED"

    annual_base = Decimal("0")
    age_modifier_pct = Decimal("0")
    age_modifier_amount = Decimal("0")
    annual_after_age = Decimal("0")
    risk_loading = Decimal("0")
    annual_total = Decimal("0")
    monthly_total = Decimal("0")

    if decision_status != "DECLINED" and cover_valid:
        # Pricing rule: annual base rate is 0.15% of sum assured.
        annual_base = q(sum_assured * Decimal("0.0015"))

        # Pricing rule: age-based modifiers adjust annual premium before risk loading.
        if age_years is not None and age_years < 25:
            age_modifier_pct = Decimal("0.25")
        elif age_years is not None and 25 <= age_years <= 45:
            age_modifier_pct = Decimal("-0.10")
        elif age_years is not None and age_years > 60:
            age_modifier_pct = Decimal("0.40")

        age_modifier_amount = q(annual_base * age_modifier_pct)
        annual_after_age = q(annual_base + age_modifier_amount)

        # Pricing rule: risky activities add a +15% risk loading to annual premium.
        risk_loading = q(annual_after_age * Decimal("0.15")) if has_risky_activities else Decimal("0")

        annual_total = q(annual_after_age + risk_loading)
        monthly_total = q(annual_total / Decimal("12"))

    return {
        "quote_id": quote_id,
        "premium": float(monthly_total),
        "currency": "UGX",
        "decision_status": decision_status,
        "requirements": requirements,
        "product_mock": "personal_accident",
        "sum_assured": float(q(sum_assured)),
        "breakdown": {
            "annual_base": float(annual_base),
            "age_modifier_pct": float(age_modifier_pct),
            "age_modifier_amount": float(age_modifier_amount),
            "annual_after_age": float(annual_after_age),
            "risk_loading": float(risk_loading),
            "annual_total": float(annual_total),
            "monthly_total": float(monthly_total),
        },
    }
