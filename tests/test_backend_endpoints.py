import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.chatbot.dependencies import api_key_protection


client = TestClient(app)


def _auth_bypass():
    return None


def test_salesiq_webhook_returns_salesiq_reply(monkeypatch):
    monkeypatch.setenv("ZOHO_WEBHOOK_SECRET", "test-secret")

    async def _fake_handle_chat_message(request, router, db):
        return SimpleNamespace(
            response={
                "mode": "conversational",
                "response": "Hey! I'm MIA, your Old Mutual assistant.",
                "suggested_action": None,
                "products_matched": [],
            }
        )

    monkeypatch.setattr(main_module, "_handle_chat_message", _fake_handle_chat_message)
    payload = {
        "visitor": {"id": "visitor-123"},
        "session": {"id": "session-123"},
        "message": {"text": "Hello"},
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test-secret", msg=raw, digestmod=hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/webhook/salesiq",
        content=raw,
        headers={"X-ZOHO-SIGNATURE": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "reply"
    assert body["replies"]
    assert "MIA" in body["replies"][0]["text"] or "Old Mutual" in body["replies"][0]["text"]


def test_salesiq_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("ZOHO_WEBHOOK_SECRET", "test-secret")
    payload = {
        "visitor": {"id": "visitor-123"},
        "session": {"id": "session-123"},
        "message": {"text": "Hello"},
    }

    response = client.post(
        "/api/v1/webhook/salesiq",
        json=payload,
        headers={"X-ZOHO-SIGNATURE": "bad-signature"},
    )

    assert response.status_code == 403


def test_admin_kb_upload_accepts_raw_body():
    app.dependency_overrides[api_key_protection] = _auth_bypass
    try:
        filename = "endpoint_upload_test.txt"
        response = client.post(
            f"/api/v1/admin/knowledge-base/upload?filename={filename}&trigger_ingest=false",
            content=b"Travel insurance protects trips and baggage.",
            headers={"Content-Type": "application/octet-stream"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filename"] == filename
        assert body["ingest_status"] == "stored_only"
        assert Path(body["saved_path"]).exists()
    finally:
        app.dependency_overrides.pop(api_key_protection, None)
