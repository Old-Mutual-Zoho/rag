"""add user phone hash for encrypted lookup

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-03-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.database.security import _decrypt_text, hash_phone_number


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_hash", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, phone_number, created_at FROM users ORDER BY created_at ASC, id ASC")).fetchall()
    seen_hashes: set[str] = set()
    for row in rows:
        raw_phone = str(row.phone_number or "").strip()
        decrypted_phone = _decrypt_text(raw_phone).strip()
        phone_hash = hash_phone_number(decrypted_phone)
        if phone_hash in seen_hashes:
            phone_hash = None
        elif phone_hash:
            seen_hashes.add(phone_hash)
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
