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
async def test_travel_party_ignores_non_travel_payload(flow):
    payload = {"product_id": "worldwide_essential", "action": "select_cover"}

    result = await flow._step_travel_party_and_trip(payload, {}, "user-1")

    assert result.get("response", {}).get("type") == "form"
    field_names = [field["name"] for field in result.get("response", {}).get("fields", [])]
    assert "travel_party" in field_names
    assert "departure_date" in field_names
    assert result.get("next_step") == 3


@pytest.mark.asyncio
async def test_travel_party_country_select_options_use_value_label(flow):
    result = await flow._step_travel_party_and_trip({}, {}, "user-1")
    fields = result.get("response", {}).get("fields", [])

    departure_field = next(field for field in fields if field.get("name") == "departure_country")
    destination_field = next(field for field in fields if field.get("name") == "destination_country")

    departure_options = departure_field.get("options", [])
    destination_options = destination_field.get("options", [])

    assert departure_options and isinstance(departure_options[0], dict)
    assert "value" in departure_options[0]
    assert "label" in departure_options[0]

    assert destination_options and isinstance(destination_options[0], dict)
    assert "value" in destination_options[0]
    assert "label" in destination_options[0]


@pytest.mark.asyncio
async def test_travel_party_myself_only_requires_primary_dob(flow):
    payload = {
        "travel_party": "myself_only",
        "departure_country": "Uganda",
        "destination_country": "Portugal",
        "departure_date": "2026-03-08",
        "return_date": "2026-03-10",
    }

    with pytest.raises(FormValidationError) as exc:
        await flow._step_travel_party_and_trip(payload, {}, "user-1")

    err = exc.value.field_errors
    assert "traveller_1_date_of_birth" in err


@pytest.mark.asyncio
async def test_travel_party_myself_and_someone_else_requires_second_dob(flow):
    payload = {
        "travel_party": "myself_and_someone_else",
        "traveller_1_date_of_birth": "1990-01-01",
        "departure_country": "Uganda",
        "destination_country": "Portugal",
        "departure_date": "2026-03-08",
        "return_date": "2026-03-10",
    }

    with pytest.raises(FormValidationError) as exc:
        await flow._step_travel_party_and_trip(payload, {}, "user-1")

    err = exc.value.field_errors
    assert "traveller_2_date_of_birth" in err


@pytest.mark.asyncio
async def test_travel_party_group_total_must_match_age_ranges(flow):
    payload = {
        "travel_party": "group",
        "total_travellers": 4,
        "num_travellers_18_69": 1,
        "num_travellers_0_17": 1,
        "num_travellers_70_75": 0,
        "num_travellers_76_80": 0,
        "num_travellers_81_85": 0,
        "departure_country": "Uganda",
        "destination_country": "Portugal",
        "departure_date": "2026-03-08",
        "return_date": "2026-03-10",
    }

    with pytest.raises(FormValidationError) as exc:
        await flow._step_travel_party_and_trip(payload, {}, "user-1")

    err = exc.value.field_errors
    assert "total_travellers" in err


@pytest.mark.asyncio
async def test_passport_upload_missing_file_ref_raises(flow):
    # Provide an empty field to enter the validation branch
    payload = {"passport_file_ref": ""}
    with pytest.raises(FormValidationError) as exc:
        await flow._step_upload_passport(payload, {}, "user-1")
    err = exc.value.field_errors
    # Field expected by require_str in upload step
    assert "passport_file_ref" in err
