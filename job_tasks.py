import os
from concurrent.futures import ThreadPoolExecutor

from database import (
    accuracy_summaries,
    resolve_market_forecasts,
    save_analysis,
    unresolved_market_slugs,
)
from models import AnalysisResult, ProviderComparison, ResolutionSyncResult
from openai_analyzer import AIUnavailableError, analyze_markets
from polymarket_client import (
    PolymarketError,
    fetch_categories,
    fetch_market_resolution,
    get_top_markets_for_category,
)
from synthesis import synthesize_comparison


def run_comparison_task(
    category_id: str,
    limit: int,
    user_id: str | None = None,
) -> dict:
    category = next(
        (item for item in fetch_categories() if item.id == category_id),
        None,
    )
    if category is None:
        raise ValueError("Category not found.")
    markets = get_top_markets_for_category(
        category_id,
        category.name,
        limit,
    )
    providers = [
        provider
        for provider, key in (
            ("openai", "OPENAI_API_KEY"),
            ("grok", "XAI_API_KEY"),
            ("claude", "ANTHROPIC_API_KEY"),
        )
        if os.getenv(key)
    ]
    if not providers and os.getenv("DEMO_MODE", "true").casefold() == "true":
        providers = ["openai", "grok", "claude"]
    if not providers:
        raise AIUnavailableError("No AI provider is configured.")

    def run_provider(provider: str):
        try:
            return provider, analyze_markets(
                markets,
                category.name,
                provider,
                False,
            )
        except AIUnavailableError as exc:
            return provider, exc

    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        outcomes = list(executor.map(run_provider, providers))
    successful = [
        result for _, result in outcomes if isinstance(result, AnalysisResult)
    ]
    for result in successful:
        save_analysis(result, user_id)
    comparison = ProviderComparison(
        results=successful,
        errors={
            provider: str(result)
            for provider, result in outcomes
            if isinstance(result, Exception)
        },
        synthesis=synthesize_comparison(successful, accuracy_summaries()),
    )
    return comparison.model_dump(mode="json")


def run_accuracy_sync_task(limit: int = 100) -> dict:
    slugs = unresolved_market_slugs(limit)
    resolved_markets = 0
    scored_forecasts = 0
    for slug in slugs:
        try:
            outcome = fetch_market_resolution(slug)
        except PolymarketError:
            continue
        if outcome is None:
            continue
        resolved_markets += 1
        scored_forecasts += resolve_market_forecasts(slug, outcome)
    return ResolutionSyncResult(
        checked_markets=len(slugs),
        newly_resolved_markets=resolved_markets,
        scored_forecasts=scored_forecasts,
    ).model_dump(mode="json")
