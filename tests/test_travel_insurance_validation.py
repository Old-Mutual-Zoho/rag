"""
Validation-centric tests for Travel Insurance flow using validators from validation.py.

Run:
    pytest tests/test_travel_insurance_validation.py -q
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import os
import sys
import pytest

# Ensure project root is on sys.path so `src` imports resolve
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.chatbot.validation import FormValidationError  # noqa: E402
from src.chatbot.flows.travel_insurance import TravelInsuranceFlow  # noqa: E402


def _make_mock_db():
    quotes = []

    def create_quote(**kwargs):
        q = SimpleNamespace(
            id="mock-quote-ti-1",
            premium_amount=kwargs.get("premium_amount", 0),
            product_id=kwargs.get("product_id", "travel_insurance"),
            product_name=kwargs.get("product_name", "Travel Insurance"),
        )
        quotes.append(q)
        return q

    def get_quote(quote_id):
        return next((q for q in quotes if str(q.id) == str(quote_id)), None)

    db = MagicMock()
    db.create_quote = create_quote
    db.get_quote = get_quote
    return db


@pytest.fixture
def flow():
    db = _make_mock_db()
    return TravelInsuranceFlow(product_catalog=MagicMock(), db=db)


@pytest.mark.asyncio
async def test_about_you_invalid_email_and_phone_raises(flow):
    payload = {
        "first_name": "Jane",
        "surname": "Doe",
        "email": "not-an-email",
        "phone_number": "abcd",
    }
    with pytest.raises(FormValidationError) as exc:
        await flow._step_about_you(payload, {}, "user-1")
    err = exc.value.field_errors
    assert "email" in err
    assert "phone_number" in err


@pytest.mark.asyncio
async def test_travel_party_return_before_departure_raises(flow):
    payload = {
        "travel_party": "myself_only",
        "num_travellers_18_69": 1,
        "departure_country": "Uganda",
        "destination_country": "Portugal",
        "departure_date": "2026-03-08",
        "return_date": "2026-03-03",
    }
    with pytest.raises(FormValidationError) as exc:
        await flow._step_travel_party_and_trip(payload, {}, "user-1")
    err = exc.value.field_errors
    assert "return_date" in err


@pytest.mark.asyncio
async def test_passport_upload_missing_file_ref_raises(flow):
    # Provide an empty field to enter the validation branch
    payload = {"passport_file_ref": ""}
    with pytest.raises(FormValidationError) as exc:
        await flow._step_upload_passport(payload, {}, "user-1")
    err = exc.value.field_errors
    # Field expected by require_str in upload step
    assert "passport_file_ref" in err
