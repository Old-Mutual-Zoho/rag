"""
Lightweight in-memory RedisCache replacement for local development.

This implements just enough of the interface used by the chatbot
`StateManager` so that the FastAPI app can run without a real Redis
instance.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class RedisCache:
    def __init__(self) -> None:
        # Simple in-memory store: session_id -> data
        self._sessions: Dict[str, Dict[str, Any]] = {}

    # --- Session helpers used by StateManager ---------------------------------

    def set_session(self, session_id: str, data: Dict[str, Any], ttl: int = 1800) -> None:
        # TTL is ignored in this in-memory implementation.
        self._sessions[session_id] = dict(data)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        if session_id not in self._sessions:
            return
        self._sessions[session_id].update(updates)

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # --- Misc -----------------------------------------------------------------

    def ping(self) -> bool:
        """
        FastAPI health check calls this; always return True so the API reports
        Redis as "connected" in local/dev mode.
        """
        return True

