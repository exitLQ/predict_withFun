import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from models import AnalysisHistoryItem, AnalysisResult

DEFAULT_DATABASE_URL = "sqlite:///./predict_withfun.db"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _is_postgres() -> bool:
    return _database_url().startswith(("postgres://", "postgresql://"))


@contextmanager
def _connection() -> Iterator[Any]:
    if _is_postgres():
        import psycopg

        with psycopg.connect(_database_url()) as connection:
            yield connection
        return

    path = _database_url().removeprefix("sqlite:///")
    database_path = Path(path)
    if database_path.parent != Path("."):
        database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _placeholder() -> str:
    return "%s" if _is_postgres() else "?"


def initialize_database() -> None:
    id_type = "TEXT"
    timestamp_type = "TIMESTAMPTZ" if _is_postgres() else "TEXT"
    with _connection() as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id {id_type} PRIMARY KEY,
                created_at {timestamp_type} NOT NULL,
                category TEXT NOT NULL,
                provider TEXT NOT NULL,
                requested_provider TEXT NOT NULL,
                market_count INTEGER NOT NULL,
                estimated_cost_usd DOUBLE PRECISION NOT NULL,
                result_json TEXT NOT NULL,
                resolved_outcome DOUBLE PRECISION,
                brier_score DOUBLE PRECISION
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS analysis_history_created_at_idx
            ON analysis_history (created_at DESC)
            """
        )


def save_analysis(result: AnalysisResult) -> str | None:
    if result.demo or result.cached:
        return None
    initialize_database()
    record_id = str(uuid.uuid4())
    values = (
        record_id,
        datetime.now(UTC).isoformat(),
        result.category,
        result.research_provider,
        result.requested_provider,
        len(result.markets),
        result.usage.estimated_cost_usd,
        result.model_dump_json(),
    )
    placeholders = ", ".join([_placeholder()] * len(values))
    with _connection() as connection:
        connection.execute(
            f"""
            INSERT INTO analysis_history (
                id, created_at, category, provider, requested_provider,
                market_count, estimated_cost_usd, result_json
            ) VALUES ({placeholders})
            """,
            values,
        )
    return record_id


def list_analyses(limit: int = 50) -> list[AnalysisHistoryItem]:
    initialize_database()
    placeholder = _placeholder()
    with _connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, created_at, category, provider, requested_provider,
                   market_count, estimated_cost_usd, resolved_outcome, brier_score
            FROM analysis_history
            ORDER BY created_at DESC
            LIMIT {placeholder}
            """,
            (limit,),
        ).fetchall()
    return [
        AnalysisHistoryItem(
            id=str(row[0]),
            created_at=row[1],
            category=str(row[2]),
            provider=row[3],
            requested_provider=row[4],
            market_count=int(row[5]),
            estimated_cost_usd=float(row[6]),
            resolved_outcome=row[7],
            brier_score=row[8],
        )
        for row in rows
    ]


def get_analysis(record_id: str) -> AnalysisResult | None:
    initialize_database()
    with _connection() as connection:
        row = connection.execute(
            f"SELECT result_json FROM analysis_history WHERE id = {_placeholder()}",
            (record_id,),
        ).fetchone()
    if not row:
        return None
    return AnalysisResult.model_validate(json.loads(row[0]))
