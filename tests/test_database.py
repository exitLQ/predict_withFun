import sqlite3
from contextlib import closing
from pathlib import Path

import database
from models import AnalysisResult, MarketAnalysis


def test_analysis_history_round_trip(monkeypatch):
    database_path = "test-history-round-trip-v3.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    result = AnalysisResult(
        category="Politics",
        summary="Saved analysis",
        markets=[
            MarketAnalysis(
                market_slug="saved-market",
                market_title="Saved market",
                market_probability=0.4,
                fair_probability=0.5,
                assessment="undervalued",
                reasoning="Test",
            )
        ],
        research_provider="claude",
        requested_provider="claude",
    )

    try:
        record_id = database.save_analysis(result)
        history = database.list_analyses()
        restored = database.get_analysis(record_id)

        assert record_id is not None
        assert history[0].provider == "claude"
        assert restored is not None
        assert restored.summary == "Saved analysis"
        assert database.unresolved_market_slugs() == ["saved-market"]
        assert database.resolve_market_forecasts("saved-market", 1.0) == 1
        score = database.list_forecast_scores()[0]
        assert score.brier_score == 0.25
        summary = database.accuracy_summaries()[0]
        assert summary.mean_brier_score == 0.25
        assert summary.mean_market_brier_score == 0.36
        calibration = database.calibration_series()[0]
        assert calibration.resolved_forecasts == 1
        assert calibration.expected_calibration_error == 0.5
        assert calibration.bins[0].observed_frequency == 1.0
        with closing(sqlite3.connect(database_path)) as connection:
            revision = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list('forecast_scores')"
                )
            }
        assert revision == ("0001",)
        assert "forecast_scores_market_slug_idx" in indexes
    finally:
        Path(database_path).unlink(missing_ok=True)


def test_demo_and_cached_results_are_not_stored(monkeypatch):
    database_path = "test-history-skipped.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    try:
        assert database.save_analysis(
            AnalysisResult(category="Demo", summary="Demo", demo=True)
        ) is None
        assert database.save_analysis(
            AnalysisResult(category="Cached", summary="Cached", cached=True)
        ) is None
        assert database.list_analyses() == []
    finally:
        Path(database_path).unlink(missing_ok=True)
