import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from models import (
    AccuracySummary,
    AnalysisHistoryItem,
    AnalysisResult,
    ForecastScore,
)

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
            f"""
            CREATE TABLE IF NOT EXISTS forecast_scores (
                id {id_type} PRIMARY KEY,
                analysis_id {id_type} NOT NULL,
                provider TEXT NOT NULL,
                created_at {timestamp_type} NOT NULL,
                market_slug TEXT NOT NULL,
                market_title TEXT NOT NULL,
                predicted_probability DOUBLE PRECISION NOT NULL,
                market_probability DOUBLE PRECISION NOT NULL,
                outcome DOUBLE PRECISION,
                brier_score DOUBLE PRECISION,
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS forecast_scores_market_slug_idx
            ON forecast_scores (market_slug)
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
    created_at = datetime.now(UTC).isoformat()
    values = (
        record_id,
        created_at,
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
        for market in result.markets:
            if market.fair_probability is None:
                continue
            score_values = (
                str(uuid.uuid4()),
                record_id,
                result.research_provider,
                created_at,
                market.market_slug,
                market.market_title,
                market.fair_probability,
                market.market_probability,
            )
            score_placeholders = ", ".join(
                [_placeholder()] * len(score_values)
            )
            connection.execute(
                f"""
                INSERT INTO forecast_scores (
                    id, analysis_id, provider, created_at, market_slug,
                    market_title, predicted_probability, market_probability
                ) VALUES ({score_placeholders})
                """,
                score_values,
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


def unresolved_market_slugs(limit: int = 100) -> list[str]:
    initialize_database()
    with _connection() as connection:
        rows = connection.execute(
            f"""
            SELECT DISTINCT market_slug
            FROM forecast_scores
            WHERE outcome IS NULL
            LIMIT {_placeholder()}
            """,
            (limit,),
        ).fetchall()
    return [str(row[0]) for row in rows]


def resolve_market_forecasts(slug: str, outcome: float) -> int:
    initialize_database()
    placeholder = _placeholder()
    with _connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE forecast_scores
            SET outcome = {placeholder},
                brier_score = (
                    predicted_probability - {placeholder}
                ) * (
                    predicted_probability - {placeholder}
                )
            WHERE market_slug = {placeholder} AND outcome IS NULL
            """,
            (outcome, outcome, outcome, slug),
        )
        return max(0, cursor.rowcount)


def list_forecast_scores(limit: int = 100) -> list[ForecastScore]:
    initialize_database()
    with _connection() as connection:
        rows = connection.execute(
            f"""
            SELECT analysis_id, provider, created_at, market_slug, market_title,
                   predicted_probability, market_probability, outcome, brier_score
            FROM forecast_scores
            ORDER BY created_at DESC
            LIMIT {_placeholder()}
            """,
            (limit,),
        ).fetchall()
    return [
        ForecastScore(
            analysis_id=str(row[0]),
            provider=row[1],
            created_at=row[2],
            market_slug=str(row[3]),
            market_title=str(row[4]),
            predicted_probability=float(row[5]),
            market_probability=float(row[6]),
            outcome=row[7],
            brier_score=row[8],
        )
        for row in rows
    ]


def accuracy_summaries() -> list[AccuracySummary]:
    scores = [
        score
        for score in list_forecast_scores(10_000)
        if score.outcome is not None
    ]
    grouped: dict[str, list[ForecastScore]] = {}
    for score in scores:
        grouped.setdefault(score.provider, []).append(score)
    return [
        AccuracySummary(
            provider=provider,
            resolved_forecasts=len(items),
            mean_brier_score=round(
                sum(item.brier_score or 0 for item in items) / len(items), 6
            ),
            mean_market_brier_score=round(
                sum(
                    (item.market_probability - (item.outcome or 0)) ** 2
                    for item in items
                )
                / len(items),
                6,
            ),
            mean_absolute_error=round(
                sum(
                    abs(item.predicted_probability - (item.outcome or 0))
                    for item in items
                )
                / len(items),
                6,
            ),
        )
        for provider, items in sorted(grouped.items())
    ]
