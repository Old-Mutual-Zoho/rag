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


def _nested_get(payload: Dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def extract_salesiq_message(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    visitor = payload.get("visitor") or {}
    message = payload.get("message") or {}
    session = payload.get("session") or {}
    data = payload.get("data") or {}
    event = payload.get("event") or {}

    return {
        "visitor_id": _first_non_empty(
            visitor.get("id"),
            visitor.get("visitor_id"),
            visitor.get("email"),
            _nested_get(visitor, "email_info", "email"),
            _nested_get(visitor, "name"),
            payload.get("visitor_id"),
            payload.get("user_id"),
            payload.get("sender_id"),
            data.get("visitor_id"),
            _nested_get(data, "visitor", "id"),
            _nested_get(event, "visitor", "id"),
        ),
        "session_id": _first_non_empty(
            session.get("id"),
            session.get("session_id"),
            payload.get("chat_id"),
            payload.get("session_id"),
            payload.get("conversation_id"),
            data.get("session_id"),
            data.get("chat_id"),
            _nested_get(data, "session", "id"),
            _nested_get(event, "session", "id"),
        ),
        "message_text": _first_non_empty(
            message.get("text"),
            message.get("message"),
            message.get("content"),
            payload.get("message") if not isinstance(payload.get("message"), dict) else None,
            payload.get("text"),
            payload.get("question"),
            data.get("message") if not isinstance(data.get("message"), dict) else None,
            data.get("text"),
            _nested_get(data, "message", "text"),
            _nested_get(data, "message", "content"),
            _nested_get(event, "message", "text"),
            _nested_get(event, "message", "content"),
        ),
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
