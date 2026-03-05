"""
Underwriting helper functions for quote preview and submission.

This module provides high-level functions for:
- Preview quotations (non-persistent mocks for display purposes)
- Full underwriting submissions
- Integration with mock or real underwriting services
"""

import os
from typing import Any, Dict, Optional

from src.integrations.clients.mocks.underwriting import mock_underwriting_client
from src.integrations.policy.quotation_service import QuotationService
from src.integrations.policy.response_wrappers import (
    normalize_quotation_response,
    normalize_underwriting_response,
)
from src.integrations.policy.underwriting_service import UnderwritingService


def _should_use_real_integrations() -> bool:
    """Determine if real integrations should be used based on environment config."""
    mode = os.getenv("INTEGRATIONS_MODE", "").strip().lower()
    if mode in {"real", "live"}:
        return True
    if mode in {"mock", "test"}:
        return False
    return bool(
        os.getenv("PARTNER_UNDERWRITING_API_URL")
        or os.getenv("PARTNER_QUOTATION_API_URL")
        or os.getenv("PARTNER_POLICY_API_URL")
    )


async def run_quote_preview(
    *,
    user_id: str,
    product_id: str,
    underwriting_data: Dict[str, Any],
    currency: str = "UGX",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a preview quotation for display in the chatbot flow.
    
    This is a lightweight version of the full underwriting-quote-policy flow.
    It provides a preview of what the quotation would look like without
    persisting it or initiating payment.
    
    Args:
        user_id: Unique identifier for the user
        product_id: Product identifier (e.g., "personal_accident", "serenicare")
        underwriting_data: KYC and risk assessment data
        currency: Currency code (default: "UGX")
        metadata: Additional metadata to include in requests
        
    Returns:
        Dictionary containing:
        - underwriting: Normalized underwriting response
        - quotation: Normalized quotation response (if successful)
        - declined: Boolean indicating if underwriting was declined
        - decision_status: Status from underwriting decision
    """
    metadata = metadata or {}

    # Step 1: Submit to underwriting
    underwriting_payload = {
        "user_id": user_id,
        "product_id": product_id,
        "underwriting_data": underwriting_data,
        "currency": currency,
        **metadata,
    }

    if _should_use_real_integrations() and os.getenv("PARTNER_UNDERWRITING_API_URL"):
        underwriting_raw = await UnderwritingService().submit_underwriting(underwriting_payload)
    else:
        # Use mock client for preview
        mock_payload = {
            **(underwriting_data or {}),
            "user_id": user_id,
            "product_id": product_id,
            "currency": currency,
            "underwriting_data": underwriting_data,
            **metadata,
        }
        underwriting_raw = await mock_underwriting_client.submit_underwriting(mock_payload)

    underwriting = normalize_underwriting_response(underwriting_raw)
    decision = (underwriting.decision_status or "").strip().upper()

    # Step 2: Check if declined
    if decision in {"DECLINED", "REJECTED"}:
        return {
            "declined": True,
            "decision_status": decision,
            "underwriting": underwriting.model_dump(),
        }

    # Step 3: Generate quotation
    quotation_payload: Dict[str, Any] = {
        "user_id": user_id,
        "product_id": product_id,
        "underwriting": underwriting.model_dump(),
        "currency": currency,
        **metadata,
    }

    if _should_use_real_integrations() and os.getenv("PARTNER_QUOTATION_API_URL"):
        quotation_raw = await QuotationService(
            base_url=os.getenv("PARTNER_QUOTATION_API_URL", ""),
            api_key=os.getenv("PARTNER_QUOTATION_API_KEY"),
        ).get_quote(quotation_payload)
    else:
        # Mock quotation for preview
        quotation_raw = {
            "quote_id": underwriting.quote_id,
            "premium": underwriting.premium,
            "currency": underwriting.currency or currency,
            "status": "quoted",
            "amount": underwriting.premium,
        }

    quotation = normalize_quotation_response(
        quotation_raw,
        fallback_quote_id=underwriting.quote_id,
        fallback_currency=currency,
    )

    return {
        "declined": False,
        "decision_status": decision or "APPROVED",
        "underwriting": underwriting.model_dump(),
        "quotation": quotation.model_dump(),
    }


__all__ = ["run_quote_preview"]
