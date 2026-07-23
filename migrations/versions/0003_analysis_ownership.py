"""Associate stored analyses with their creating user.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("analysis_history")}
    if "user_id" not in columns:
        with op.batch_alter_table("analysis_history") as batch:
            batch.add_column(sa.Column("user_id", sa.Text(), nullable=True))
            batch.create_foreign_key(
                "analysis_history_user_id_fk",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index("analysis_history_user_id_idx", ["user_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("analysis_history")}
    if "user_id" in columns:
        with op.batch_alter_table("analysis_history") as batch:
            batch.drop_index("analysis_history_user_id_idx")
            batch.drop_constraint("analysis_history_user_id_fk", type_="foreignkey")
            batch.drop_column("user_id")
