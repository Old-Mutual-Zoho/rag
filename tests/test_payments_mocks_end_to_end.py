from fastapi.testclient import TestClient

from src.api.main import app
from src.chatbot.dependencies import api_key_protection


client = TestClient(app)


def _auth_bypass():
    return None


def _initiate_payload(quote_id: str, simulate_outcome: str = "success"):
    return {
        "quote_id": quote_id,
        "provider": "mtn",
        "phone_number": "256771234567",
        "amount": 15000,
        "currency": "UGX",
        "payee_name": "Old Mutual",
        "metadata": {"simulate_outcome": simulate_outcome},
    }


def test_initiate_returns_pending():
    app.dependency_overrides[api_key_protection] = _auth_bypass
    try:
        quote_id = "q-pay-init-pending"
        response = client.post("/api/v1/payments/initiate", json=_initiate_payload(quote_id, "success"))
        assert response.status_code == 200

        body = response.json()
        assert body["reference"] == quote_id
        assert body["status"] == "PENDING"
        assert body["message"]
        assert body["provider_reference"]
        assert body["amount"] == 15000
        assert body["currency"] == "UGX"
        assert body["metadata"]["simulate_outcome"] == "success"
    finally:
        app.dependency_overrides.pop(api_key_protection, None)


def test_trigger_mock_callback_sets_success():
    app.dependency_overrides[api_key_protection] = _auth_bypass
    try:
        quote_id = "q-pay-callback-success"
        init_response = client.post("/api/v1/payments/initiate", json=_initiate_payload(quote_id, "success"))
        assert init_response.status_code == 200
        assert init_response.json()["status"] == "PENDING"

        trigger_response = client.post(
            f"/api/v1/payments/mock/trigger-callback/{quote_id}",
            json={},
        )
        assert trigger_response.status_code == 200

        status_response = client.get(f"/api/v1/payments/status/{quote_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "SUCCESS"
    finally:
        app.dependency_overrides.pop(api_key_protection, None)


def test_trigger_mock_callback_sets_failed():
    app.dependency_overrides[api_key_protection] = _auth_bypass
    try:
        quote_id = "q-pay-callback-failed"
        init_response = client.post("/api/v1/payments/initiate", json=_initiate_payload(quote_id, "failed"))
        assert init_response.status_code == 200
        assert init_response.json()["status"] == "PENDING"

        trigger_response = client.post(
            f"/api/v1/payments/mock/trigger-callback/{quote_id}",
            json={},
        )
        assert trigger_response.status_code == 200

        status_response = client.get(f"/api/v1/payments/status/{quote_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "FAILED"
    finally:
        app.dependency_overrides.pop(api_key_protection, None)


def test_webhook_rejects_bad_signature():
    app.dependency_overrides[api_key_protection] = _auth_bypass
    try:
        quote_id = "q-pay-bad-signature"
        init_response = client.post("/api/v1/payments/initiate", json=_initiate_payload(quote_id, "success"))
        assert init_response.status_code == 200

        webhook_payload = {
            "reference": quote_id,
            "status": "SUCCESS",
            "provider_reference": "MTN-q-pay-bad-signature",
        }
        callback_response = client.post(
            "/api/v1/payments/webhook/callback",
            json=webhook_payload,
            headers={"X-Signature": "bad-signature"},
        )
        assert callback_response.status_code == 401
    finally:
        app.dependency_overrides.pop(api_key_protection, None)
