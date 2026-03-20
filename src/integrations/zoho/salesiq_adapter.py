from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional


def verify_salesiq_signature(body: bytes, signature: Optional[str]) -> bool:
    secret = (os.getenv("ZOHO_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def extract_salesiq_message(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    visitor = payload.get("visitor") or {}
    message = payload.get("message") or {}
    session = payload.get("session") or {}
    return {
        "visitor_id": str(visitor.get("id") or payload.get("visitor_id") or payload.get("user_id") or "").strip() or None,
        "session_id": str(session.get("id") or payload.get("chat_id") or payload.get("session_id") or "").strip() or None,
        "message_text": str(message.get("text") or payload.get("message") or "").strip() or None,
    }


def _extract_suggestions(internal_response: Dict[str, Any]) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []
    suggested_action = internal_response.get("suggested_action") or {}
    for button in suggested_action.get("buttons") or []:
        label = str(button.get("label") or "").strip()
        if label:
            suggestions.append({"text": label})
    return suggestions[:5]


def transform_internal_to_salesiq(internal_response: Dict[str, Any]) -> Dict[str, Any]:
    if internal_response.get("mode") == "escalated" or internal_response.get("show_handover_button"):
        text = str(internal_response.get("response") or "I'm connecting you to a human agent.")
        return {"action": "forward", "replies": [text]}

    text = str(internal_response.get("response") or "")
    reply: Dict[str, Any] = {"text": text}

    suggestions = _extract_suggestions(internal_response)
    if suggestions:
        reply["suggestions"] = suggestions

    products = internal_response.get("products_matched") or []
    if not suggestions and products:
        reply["suggestions"] = [{"text": str(name)} for name in products[:4]]

    return {"action": "reply", "replies": [reply]}


def build_salesiq_context_note(context: Dict[str, Any]) -> str:
    safe_context = json.dumps(context or {}, default=str)
    return f"SalesIQ context: {safe_context}"
