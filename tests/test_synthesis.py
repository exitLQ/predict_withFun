import pytest

from models import AccuracySummary, AnalysisResult, MarketAnalysis
from synthesis import synthesize_comparison


def _analysis(provider, probability, risks=None):
    return AnalysisResult(
        category="Test",
        summary="Test",
        research_provider=provider,
        requested_provider=provider,
        markets=[
            MarketAnalysis(
                market_slug="market",
                market_title="Market",
                market_probability=0.5,
                fair_probability=probability,
                assessment="fair",
                risks=risks or [],
                reasoning="Test",
            )
        ],
    )


def test_synthesis_uses_accuracy_weights_and_classifies_disagreement():
    results = [
        _analysis("openai", 0.7, ["Timing"]),
        _analysis("grok", 0.4, ["Timing", "Liquidity"]),
        _analysis("claude", 0.6),
    ]
    accuracy = [
        AccuracySummary(
            provider="openai",
            resolved_forecasts=10,
            mean_brier_score=0.1,
            mean_market_brier_score=0.2,
            mean_absolute_error=0.2,
        ),
        AccuracySummary(
            provider="grok",
            resolved_forecasts=10,
            mean_brier_score=0.2,
            mean_market_brier_score=0.2,
            mean_absolute_error=0.3,
        ),
    ]

    synthesis = synthesize_comparison(results, accuracy)

    assert synthesis is not None
    market = synthesis.markets[0]
    assert sum(synthesis.provider_weights.values()) == pytest.approx(1)
    assert synthesis.provider_weights["openai"] > synthesis.provider_weights["grok"]
    assert market.median_probability == 0.6
    assert market.spread == pytest.approx(0.3)
    assert market.disagreement == "high"
    assert market.assessment == "undervalued"
    assert market.shared_risks == ["Timing", "Liquidity"]


def test_empty_comparison_has_no_synthesis():
    assert synthesize_comparison([], []) is None
