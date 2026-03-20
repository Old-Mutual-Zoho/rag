"""add user phone hash for encrypted lookup

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-03-20 00:00:00.000000

"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_hash", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, phone_number FROM users")).fetchall()
    for row in rows:
        phone = str(row.phone_number or "").strip()
        normalized = "".join(ch for ch in phone if ch.isdigit())
        phone_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None
        connection.execute(
            sa.text("UPDATE users SET phone_hash = :phone_hash WHERE id = :user_id"),
            {"phone_hash": phone_hash, "user_id": row.id},
        )

    op.create_index(
        op.f("ix_users_phone_hash"),
        "users",
        ["phone_hash"],
        unique=True,
        postgresql_where=sa.text("phone_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_phone_hash"), table_name="users")
    op.drop_column("users", "phone_hash")
