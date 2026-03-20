from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Optional

from sqlalchemy.types import JSON, String, TypeDecorator

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - optional at import time
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]


def _resolve_cipher() -> Optional[Any]:
    key = (os.getenv("DB_ENCRYPTION_KEY") or "").strip()
    if not key or Fernet is None:
        return None

    try:
        return Fernet(key.encode())
    except Exception:
        padded = key.encode()
        if len(padded) < 32:
            padded = padded.ljust(32, b"0")
        digest = hashlib.sha256(padded).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_text(value: str) -> str:
    cipher = _resolve_cipher()
    if cipher is None:
        return value
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_text(value: str) -> str:
    cipher = _resolve_cipher()
    if cipher is None:
        return value
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return value


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return _encrypt_text(str(value))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return _decrypt_text(str(value))


class EncryptedJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        raw = json.dumps(value)
        return _encrypt_text(raw)

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        raw = _decrypt_text(str(value))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}


def normalize_phone_number(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    return "".join(ch for ch in raw if ch.isdigit())


def hash_phone_number(value: Optional[str]) -> Optional[str]:
    normalized = normalize_phone_number(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None
