"""Create analysis history and forecast scoring tables.

Revision ID: 0001
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        str(index["name"])
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("analysis_history"):
        op.create_table(
            "analysis_history",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("category", sa.Text(), nullable=False),
            sa.Column("provider", sa.Text(), nullable=False),
            sa.Column("requested_provider", sa.Text(), nullable=False),
            sa.Column("market_count", sa.Integer(), nullable=False),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=False),
            sa.Column("resolved_outcome", sa.Float(), nullable=True),
            sa.Column("brier_score", sa.Float(), nullable=True),
        )
    if "analysis_history_created_at_idx" not in _index_names(
        "analysis_history"
    ):
        op.create_index(
            "analysis_history_created_at_idx",
            "analysis_history",
            [sa.text("created_at DESC")],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("forecast_scores"):
        op.create_table(
            "forecast_scores",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("analysis_id", sa.Text(), nullable=False),
            sa.Column("provider", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("market_slug", sa.Text(), nullable=False),
            sa.Column("market_title", sa.Text(), nullable=False),
            sa.Column("predicted_probability", sa.Float(), nullable=False),
            sa.Column("market_probability", sa.Float(), nullable=False),
            sa.Column("outcome", sa.Float(), nullable=True),
            sa.Column("brier_score", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(
                ["analysis_id"],
                ["analysis_history.id"],
            ),
        )
    if "forecast_scores_market_slug_idx" not in _index_names(
        "forecast_scores"
    ):
        op.create_index(
            "forecast_scores_market_slug_idx",
            "forecast_scores",
            ["market_slug"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("forecast_scores"):
        if "forecast_scores_market_slug_idx" in _index_names("forecast_scores"):
            op.drop_index(
                "forecast_scores_market_slug_idx",
                table_name="forecast_scores",
            )
        op.drop_table("forecast_scores")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("analysis_history"):
        if "analysis_history_created_at_idx" in _index_names(
            "analysis_history"
        ):
            op.drop_index(
                "analysis_history_created_at_idx",
                table_name="analysis_history",
            )
        op.drop_table("analysis_history")
