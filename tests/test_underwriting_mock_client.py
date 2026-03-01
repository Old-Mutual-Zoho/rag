import json

import pytest

from src.integrations.clients.mocks.underwriting_mocks.underwriting import MockUnderwritingClient


@pytest.mark.asyncio
async def test_serenicare_mock_is_product_specific_and_persisted(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "serenicare",
        "plan_option": {"id": "premium"},
        "medical_conditions": ["hypertension"],
        "optional_benefits": ["Dental"],
    }

    result = await client.create_quote(payload)

    assert result["decision_status"] == "pending_review"
    assert result["product_mock"] == "serenicare"
    assert result["premium"] == 185000.0

    written_files = list((tmp_path / "serenicare").glob("*.json"))
    assert len(written_files) == 1

    body = json.loads(written_files[0].read_text(encoding="utf-8"))
    assert body["product_id"] == "serenicare"
    assert body["output"]["decision_status"] == "pending_review"


@pytest.mark.asyncio
async def test_personal_accident_mock_applies_risk_loading_and_requirements(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "personal_accident",
        "coverLimitAmountUgx": 50_000_000,
        "dob": "1995-06-10",
        "riskyActivities": ["bungee_jumping"],
    }

    result = await client.submit_underwriting(payload)

    assert result["product_mock"] == "personal_accident"
    assert result["decision_status"] == "REFERRED"
    assert pytest.approx(result["premium"], rel=1e-6) == 6468.75
    assert any(
        item["type"] == "underwriting" and item["field"] == "riskyActivities"
        for item in result["requirements"]
    )
    assert all(set(item.keys()) == {"type", "field", "message"} for item in result["requirements"])

    written_files = list((tmp_path / "personal_accident").glob("*.json"))
    assert len(written_files) == 1


@pytest.mark.asyncio
async def test_personal_accident_declines_when_cover_missing_or_invalid(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "personal_accident",
        "dob": "1992-01-01",
        "riskyActivities": [],
    }

    result = await client.create_quote(payload)

    assert result["decision_status"] == "DECLINED"
    assert result["premium"] == 0.0
    assert any(
        req["type"] == "validation" and req["field"] == "coverLimitAmountUgx"
        for req in result["requirements"]
    )


@pytest.mark.asyncio
async def test_personal_accident_declines_for_underage_applicant(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "personal_accident",
        "coverLimitAmountUgx": 10_000_000,
        "dob": "2010-05-01",
        "riskyActivities": [],
    }

    result = await client.create_quote(payload)

    assert result["decision_status"] == "DECLINED"
    assert any(
        req["type"] == "eligibility" and req["field"] == "dob"
        for req in result["requirements"]
    )


@pytest.mark.asyncio
async def test_personal_accident_refers_for_high_cover_manual_review(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "personal_accident",
        "coverLimitAmountUgx": 250_000_000,
        "dob": "1990-01-01",
        "riskyActivities": [],
    }

    result = await client.create_quote(payload)

    assert result["decision_status"] == "REFERRED"
    assert any(
        req["type"] == "underwriting" and req["field"] == "coverLimitAmountUgx"
        for req in result["requirements"]
    )


@pytest.mark.asyncio
async def test_personal_accident_approved_uses_age_modifier_and_decimal_rounding(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    payload = {
        "product_id": "personal_accident",
        "coverLimitAmountUgx": 50_000_000,
        "dob": "1993-08-15",
        "riskyActivities": [],
    }

    result = await client.create_quote(payload)

    assert result["decision_status"] == "APPROVED"
    assert pytest.approx(result["premium"], rel=1e-6) == 5625.0
    assert result["breakdown"]["annual_base"] == 75000.0
    assert result["breakdown"]["age_modifier_pct"] == -0.1
    assert result["breakdown"]["annual_total"] == 67500.0
    assert result["breakdown"]["monthly_total"] == 5625.0


@pytest.mark.asyncio
async def test_unknown_product_uses_general_mock_and_folder(tmp_path):
    client = MockUnderwritingClient(output_root=tmp_path)

    result = await client.create_quote({"foo": "bar"})

    assert result["product_mock"] == "general"
    assert result["decision_status"] == "approved"

    written_files = list((tmp_path / "general").glob("*.json"))
    assert len(written_files) == 1
