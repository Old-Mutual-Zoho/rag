"""Tests for underwriting flow logic."""

import pytest
from datetime import datetime, timedelta

from src.chatbot.flows.underwriting import UnderwritingFlow


@pytest.fixture
def underwriting_flow(db):
    return UnderwritingFlow(db)


@pytest.mark.asyncio
async def test_underwriting_process_step_personal_info(underwriting_flow):
    """Step 0 returns personal_info form."""
    result = await underwriting_flow.process_step("", 0, {"user_id": "u1"}, "u1")
    assert result.get("next_step") == 1
    resp = result.get("response", {})
    assert resp.get("type") == "form"
    assert "fields" in resp
    names = [f["name"] for f in resp["fields"]]
    assert "full_name" in names
    assert "date_of_birth" in names
    assert "occupation" in names


@pytest.mark.asyncio
async def test_underwriting_process_step_coverage_details(underwriting_flow):
    """Step 1 returns coverage_details form."""
    result = await underwriting_flow.process_step("", 1, {"user_id": "u1"}, "u1")
    assert result.get("next_step") == 2
    resp = result.get("response", {})
    assert resp.get("type") == "form"
    assert any(f["name"] == "sum_assured" for f in resp["fields"])
    assert any(f["name"] == "policy_term" for f in resp["fields"])


@pytest.mark.asyncio
async def test_underwriting_process_step_review_and_submit(underwriting_flow):
    """Step 4 returns review and assess_risk."""
    data = {
        "user_id": "u1",
        "full_name": "Test User",
        "date_of_birth": "1990-01-15",
        "occupation": "Engineer",
        "sum_assured": 20_000_000,
        "policy_term": 20,
        "beneficiaries": "Jane Doe",
        "health_info": {"chronic_conditions": {"answer": "no"}, "hospitalizations": {"answer": "no"}},
        "lifestyle_info": {"smoker": "No", "alcohol": "Occasional", "exercise": "3-4 times/week"},
    }
    result = await underwriting_flow.process_step("", 4, data, "u1")
    assert result.get("complete") is True
    resp = result.get("response", {})
    assert resp.get("type") == "review"
    assert "summary" in resp
    assert "requires_human_review" in resp


def test_underwriting_assess_risk_chronic_conditions(underwriting_flow):
    """Chronic conditions yes -> requires review."""
    data = {"health_info": {"chronic_conditions": {"answer": "yes"}}}
    assert underwriting_flow._assess_risk(data) is True


def test_underwriting_assess_risk_hospitalizations(underwriting_flow):
    """Hospitalizations yes -> requires review."""
    data = {"health_info": {"hospitalizations": {"answer": "yes"}}}
    assert underwriting_flow._assess_risk(data) is True


def test_underwriting_assess_risk_high_sum_assured(underwriting_flow):
    """Sum assured over 100M -> requires review."""
    data = {"sum_assured": 101_000_000}
    assert underwriting_flow._assess_risk(data) is True


def test_underwriting_assess_risk_age_over_60(underwriting_flow):
    """Age over 60 -> requires review."""
    old_dob = (datetime.now() - timedelta(days=65 * 365)).date().isoformat()
    data = {"date_of_birth": old_dob}
    assert underwriting_flow._assess_risk(data) is True


def test_underwriting_assess_risk_low_risk(underwriting_flow):
    """No flags -> no review."""
    data = {
        "date_of_birth": "1990-01-01",
        "sum_assured": 10_000_000,
        "health_info": {"chronic_conditions": {"answer": "no"}, "hospitalizations": {"answer": "no"}},
    }
    assert underwriting_flow._assess_risk(data) is False


def test_underwriting_calculate_risk_score(underwriting_flow):
    """Risk score is clamped 0-100."""
    data = {"date_of_birth": "1990-01-01", "health_info": {}, "lifestyle_info": {}}
    score = underwriting_flow._calculate_risk_score(data)
    assert 0 <= score <= 100


def test_underwriting_calculate_risk_score_smoker(underwriting_flow):
    """Smoker adds to risk score."""
    data = {"date_of_birth": "1990-01-01", "health_info": {}, "lifestyle_info": {"smoker": "Yes - regularly"}}
    score = underwriting_flow._calculate_risk_score(data)
    assert score >= 50


def test_underwriting_calculate_age(underwriting_flow):
    """Age from DOB."""
    dob = (datetime.now() - timedelta(days=30 * 365)).date().isoformat()
    assert underwriting_flow._calculate_age(dob) == 30


def test_underwriting_generate_summary(underwriting_flow):
    """Summary contains personal, coverage, health, lifestyle."""
    data = {
        "full_name": "Jane Doe",
        "date_of_birth": "1985-06-01",
        "occupation": "Teacher",
        "sum_assured": 25_000_000,
        "policy_term": 15,
        "beneficiaries": "John Doe",
        "health_info": {},
        "lifestyle_info": {},
    }
    summary = underwriting_flow._generate_summary(data)
    assert "personal" in summary
    assert summary["personal"]["name"] == "Jane Doe"
    assert "coverage" in summary
    assert "UGX" in summary["coverage"]["sum_assured"]
    assert "health_summary" in summary
    assert "lifestyle_summary" in summary
