"""Tests for quotation flow logic."""

import pytest

from src.chatbot.flows.quotation import QuotationFlow


@pytest.fixture
def quotation_flow(db):
    return QuotationFlow(product_catalog={}, db=db)


@pytest.mark.asyncio
async def test_quotation_calculate_premium_minimal(quotation_flow):
    """Premium with minimal underwriting data."""
    data = {"sum_assured": 10_000_000, "policy_term": 20}
    result = await quotation_flow._calculate_premium(data)
    assert result["product_name"] == "Family Life Protection"
    assert result["sum_assured"] == 10_000_000
    assert result["policy_term"] == 20
    assert result["monthly_premium"] > 0
    assert result["annual_premium"] > 0
    assert "breakdown" in result
    assert "base_premium" in result["breakdown"]


@pytest.mark.asyncio
async def test_quotation_calculate_premium_with_dob(quotation_flow):
    """Premium with date of birth applies age factor."""
    from datetime import datetime, timedelta

    dob = (datetime.now() - timedelta(days=40 * 365)).date().isoformat()
    data = {"sum_assured": 20_000_000, "policy_term": 20, "date_of_birth": dob}
    result = await quotation_flow._calculate_premium(data)
    assert result["monthly_premium"] > 0
    assert "age_adjustment" in result["breakdown"]


@pytest.mark.asyncio
async def test_quotation_calculate_premium_health_loading(quotation_flow):
    """Chronic conditions add health loading."""
    data = {
        "sum_assured": 10_000_000,
        "policy_term": 20,
        "health_info": {"chronic_conditions": {"answer": "yes"}},
    }
    result = await quotation_flow._calculate_premium(data)
    assert result["monthly_premium"] > 0
    assert result["breakdown"].get("health_loading") != "None"


@pytest.mark.asyncio
async def test_quotation_calculate_premium_lifestyle_loading(quotation_flow):
    """Smoker adds lifestyle loading."""
    data = {
        "sum_assured": 10_000_000,
        "policy_term": 20,
        "lifestyle_info": {"smoker": "Yes - regularly"},
    }
    result = await quotation_flow._calculate_premium(data)
    assert result["monthly_premium"] > 0
    assert result["breakdown"].get("lifestyle_loading") == "30%"


@pytest.mark.asyncio
async def test_quotation_process_step_present_quote(quotation_flow):
    """Step 0 presents quote from underwriting data."""
    data = {"sum_assured": 15_000_000, "policy_term": 25}
    result = await quotation_flow.process_step("", 0, data, "user-1")
    assert result.get("next_step") == 1
    resp = result.get("response", {})
    assert "quote_details" in resp
    assert resp["quote_details"]["sum_assured"] == 15_000_000


@pytest.mark.asyncio
async def test_quotation_process_step_accept_saves_quote(quotation_flow, db):
    """Accept action creates quote and returns complete."""
    data = {"sum_assured": 10_000_000, "policy_term": 20, "monthly_premium": 50_000}
    result = await quotation_flow.process_step("accept", 1, data, "user-1")
    assert result.get("complete") is True
    assert result.get("next_flow") == "payment"
    resp = result.get("response", {})
    assert "quote_id" in resp
    quote = db.get_quote(resp["quote_id"])
    assert quote is not None
    assert quote.premium_amount == 50_000
