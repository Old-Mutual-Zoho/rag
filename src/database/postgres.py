"""
Lightweight in-memory PostgresDB replacement for local development.

This provides a minimal subset of the interface expected by the API and
chatbot flows so the system can run without a real database. It is NOT
intended for production use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class User:
    id: str
    phone_number: str
    kyc_completed: bool = False


@dataclass
class Conversation:
    id: str
    user_id: str
    mode: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Quote:
    id: str
    user_id: str
    product_id: str
    product_name: str
    premium_amount: float
    sum_assured: Optional[float]
    underwriting_data: Dict[str, Any]
    pricing_breakdown: Optional[Dict[str, Any]] = None
    status: str = "pending"
    generated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30)
    )


class PostgresDB:
    """
    In-memory stand‑in for a Postgres-backed data access layer.

    Methods are intentionally simple and only support what the current
    API and chatbot flows require.
    """

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        self._users_by_phone: Dict[str, str] = {}
        self._conversations: Dict[str, Conversation] = {}
        self._messages: List[Message] = []
        self._quotes: Dict[str, Quote] = {}

    # ------------------------------------------------------------------ #
    # Schema / lifecycle
    # ------------------------------------------------------------------ #
    def create_tables(self) -> None:
        """
        No-op for the in-memory implementation. Kept for compatibility
        with the startup hook in `src/api/main.py`.
        """
        return None

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #
    def get_or_create_user(self, phone_number: str) -> User:
        if phone_number in self._users_by_phone:
            return self._users[self._users_by_phone[phone_number]]

        user_id = str(uuid.uuid4())
        user = User(id=user_id, phone_number=phone_number, kyc_completed=False)
        self._users[user_id] = user
        self._users_by_phone[phone_number] = user_id
        return user

    def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        user_id = self._users_by_phone.get(phone_number)
        if not user_id:
            return None
        return self._users.get(user_id)

    # ------------------------------------------------------------------ #
    # Conversations & messages
    # ------------------------------------------------------------------ #
    def create_conversation(self, user_id: str, mode: str) -> Conversation:
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id=user_id, mode=mode)
        self._conversations[conv_id] = conv
        return conv

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._messages.append(msg)
        return msg

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> List[Message]:
        msgs = [m for m in self._messages if m.conversation_id == conversation_id]
        # Return newest first, API reverses again where needed
        msgs.sort(key=lambda m: m.timestamp, reverse=True)
        return msgs[:limit]

    # ------------------------------------------------------------------ #
    # Quotes
    # ------------------------------------------------------------------ #
    def create_quote(
        self,
        *,
        user_id: str,
        product_id: str,
        premium_amount: Any,
        sum_assured: Any = None,
        underwriting_data: Optional[Dict[str, Any]] = None,
        pricing_breakdown: Optional[Dict[str, Any]] = None,
        product_name: Optional[str] = None,
    ) -> Quote:
        quote_id = str(uuid.uuid4())
        quote = Quote(
            id=quote_id,
            user_id=user_id,
            product_id=product_id,
            product_name=product_name or product_id,
            premium_amount=float(premium_amount or 0.0),
            sum_assured=float(sum_assured) if sum_assured is not None else None,
            underwriting_data=underwriting_data or {},
            pricing_breakdown=pricing_breakdown,
        )
        self._quotes[quote_id] = quote
        return quote

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        return self._quotes.get(str(quote_id))

