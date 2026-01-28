"""
Real Postgres-backed DB for production when USE_POSTGRES_CONVERSATIONS and DATABASE_URL are set.
Implements the same interface as src.database.postgres (in-memory stub).
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Conversation, Message, Quote, User


def _normalize_connection_string(s: str) -> str:
    """Strip common mistakes: 'psql \'...\'', extra quotes, whitespace."""
    s = s.strip()
    if re.match(r"^psql\s+", s, re.IGNORECASE):
        s = re.sub(r"^psql\s+", "", s, flags=re.IGNORECASE).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    return s


class PostgresDB:
    """
    Postgres data access using SQLAlchemy. Use when DATABASE_URL is set and
    USE_POSTGRES_CONVERSATIONS=true.
    """

    def __init__(self, connection_string: str) -> None:
        connection_string = _normalize_connection_string(connection_string)
        self.engine = create_engine(connection_string, pool_pre_ping=True, pool_size=5, max_overflow=10)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def _session(self) -> Session:
        s = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def get_or_create_user(self, phone_number: str) -> User:
        with self._session() as s:
            stmt = select(User).where(User.phone_number == phone_number)
            u = s.execute(stmt).scalar_one_or_none()
            if u:
                return u
            u = User(id=str(uuid4()), phone_number=phone_number, kyc_completed=False)
            s.add(u)
            s.flush()
            s.refresh(u)
            return u

    def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        with self._session() as s:
            stmt = select(User).where(User.phone_number == phone_number)
            return s.execute(stmt).scalar_one_or_none()

    def create_conversation(self, user_id: str, mode: str) -> Conversation:
        with self._session() as s:
            c = Conversation(id=str(uuid4()), user_id=user_id, mode=mode)
            s.add(c)
            s.flush()
            s.refresh(c)
            return c

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        with self._session() as s:
            m = Message(
                id=str(uuid4()),
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata or {},
            )
            s.add(m)
            s.flush()
            s.refresh(m)
            return m

    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Message]:
        with self._session() as s:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp.desc())
                .limit(limit)
            )
            return list(s.execute(stmt).scalars().all())

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
        with self._session() as s:
            q = Quote(
                id=str(uuid4()),
                user_id=user_id,
                product_id=product_id,
                product_name=product_name or product_id,
                premium_amount=float(premium_amount or 0.0),
                sum_assured=float(sum_assured) if sum_assured is not None else None,
                underwriting_data=underwriting_data or {},
                pricing_breakdown=pricing_breakdown,
            )
            s.add(q)
            s.flush()
            s.refresh(q)
            return q

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        with self._session() as s:
            stmt = select(Quote).where(Quote.id == str(quote_id))
            return s.execute(stmt).scalar_one_or_none()
