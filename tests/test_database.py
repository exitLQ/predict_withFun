from pathlib import Path

import database
from models import AnalysisResult, MarketAnalysis


def test_analysis_history_round_trip(monkeypatch):
    database_path = "test-history-round-trip.db"
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
