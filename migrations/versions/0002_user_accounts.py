"""Add user accounts and server-side sessions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("email", sa.Text(), nullable=False, unique=True),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("user_sessions"):
        op.create_table(
            "user_sessions",
            sa.Column("token_hash", sa.Text(), primary_key=True),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("csrf_hash", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "user_sessions_expires_at_idx",
            "user_sessions",
            ["expires_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("user_sessions"):
        op.drop_index(
            "user_sessions_expires_at_idx",
            table_name="user_sessions",
        )
        op.drop_table("user_sessions")
    if inspector.has_table("users"):
        op.drop_table("users")
