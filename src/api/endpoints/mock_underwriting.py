"""
Temporary endpoints to test underwriting mocks from Swagger.
Remove or disable in production.
"""

from fastapi import APIRouter
from typing import Dict, Any
from uuid import uuid4

from src.integrations.clients.mocks.underwriting_mocks.personal_accident import build_personal_accident_mock

router = APIRouter(prefix="/api/v1/mock", tags=["Mock Underwriting"])


@router.post("/personal-accident")
async def test_pa_underwriting(payload: Dict[str, Any]):
    """
    Test Personal Accident underwriting mock.

    Example payload:
    {
        "dob": "1990-01-01",
        "coverLimitAmountUgx": 10000000,
        "riskyActivities": []
    }
    """
    quote_id = f"test-pa-{uuid4()}"
    result = build_personal_accident_mock(payload, quote_id)
    return result
