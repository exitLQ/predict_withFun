from statistics import mean, median

from models import (
    AccuracySummary,
    AnalysisResult,
    ComparisonSynthesis,
    ConsensusMarket,
)


def _provider_weights(
    results: list[AnalysisResult],
    accuracy: list[AccuracySummary],
) -> dict[str, float]:
    scores = {item.provider: item.mean_brier_score for item in accuracy}
    raw = {
        result.research_provider: 1 / max(
            scores.get(result.research_provider, 0.25),
            0.05,
        )
        for result in results
    }
    total = sum(raw.values()) or 1
    return {provider: round(value / total, 6) for provider, value in raw.items()}


def synthesize_comparison(
    results: list[AnalysisResult],
    accuracy: list[AccuracySummary],
) -> ComparisonSynthesis | None:
    if not results:
        return None
    weights = _provider_weights(results, accuracy)
    slugs = list(dict.fromkeys(market.market_slug for market in results[0].markets))
    synthesized = []
    for slug in slugs:
        entries = [
            (result, market)
            for result in results
            for market in result.markets
            if market.market_slug == slug and market.fair_probability is not None
        ]
        if not entries:
            continue
        probabilities = [market.fair_probability for _, market in entries]
        minimum = min(probabilities)
        maximum = max(probabilities)
        spread = maximum - minimum
        weighted_total = sum(
            market.fair_probability * weights[result.research_provider]
            for result, market in entries
        )
        included_weight = sum(
            weights[result.research_provider] for result, _ in entries
        )
        weighted = weighted_total / included_weight
        market_probability = entries[0][1].market_probability
        delta = weighted - market_probability
        risks = list(
            dict.fromkeys(
                risk
                for _, market in entries
                for risk in market.risks
            )
        )[:6]
        disagreement = (
            "low"
            if spread <= 0.05
            else "moderate"
            if spread <= 0.15
            else "high"
        )
        synthesized.append(
            ConsensusMarket(
                market_slug=slug,
                market_title=entries[0][1].market_title,
                market_probability=market_probability,
                mean_probability=round(mean(probabilities), 6),
                median_probability=round(median(probabilities), 6),
                weighted_probability=round(weighted, 6),
                minimum_probability=minimum,
                maximum_probability=maximum,
                spread=round(spread, 6),
                disagreement=disagreement,
                assessment=(
                    "undervalued"
                    if delta >= 0.05
                    else "overvalued"
                    if delta <= -0.05
                    else "fair"
                ),
                providers=[result.research_provider for result, _ in entries],
                shared_risks=risks,
            )
        )
    return ComparisonSynthesis(
        method=(
            "Accuracy-weighted consensus using inverse mean Brier score; "
            "providers without resolved forecasts use a neutral 0.25 score."
        ),
        provider_weights=weights,
        markets=synthesized,
    )
