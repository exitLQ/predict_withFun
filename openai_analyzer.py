import os
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from models import AnalysisResult, Market, MarketAnalysis, Source

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-sol"
SYSTEM_INSTRUCTIONS = """
Analyze prediction markets objectively and transparently. Separate observed
market prices from your own estimate. Use web search for current, reliable
evidence before estimating probabilities. Prefer primary sources and recent
reporting. Never claim knowledge of future events. Consider base rates, recency,
liquidity, resolution rules, and information gaps. Respond in English. The
output is not financial advice.
""".strip()


class AIUnavailableError(RuntimeError):
    pass


class GeneratedMarketAnalysis(BaseModel):
    market_title: str
    fair_probability: float = Field(ge=0, le=1)
    assessment: str
    risks: list[str]
    reasoning: str


class GeneratedAnalysis(BaseModel):
    summary: str
    overall_insights: str
    markets: list[GeneratedMarketAnalysis]


def _build_input(markets: list[Market], category: str) -> str:
    lines = [
        f'Analyze the following markets in the "{category}" category.',
        "For each market, assess the probability of the first outcome.",
        "Search for current evidence and use it in your reasoning.",
        "",
    ]
    for index, market in enumerate(markets, 1):
        outcomes = ", ".join(
            f"{outcome.title}: {outcome.probability:.1%}"
            for outcome in market.outcomes
        ) or "no price data"
        lines.extend(
            [
                f"{index}. {market.title}",
                (
                    f"Volume: ${market.volume:,.0f}; "
                    f"Liquidity: ${market.liquidity or 0:,.0f}"
                ),
                f"Outcomes: {outcomes}",
                f"Description: {market.description or 'not provided'}",
                "",
            ]
        )
    return "\n".join(lines)


def _normalize_assessment(value: str) -> str:
    normalized = value.casefold()
    if "under" in normalized:
        return "undervalued"
    if "over" in normalized:
        return "overvalued"
    return "fair"


def _extract_sources(value: Any) -> list[Source]:
    found: dict[str, Source] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            url = item.get("url")
            title = item.get("title")
            if isinstance(url, str) and url.startswith("http"):
                found[url] = Source(
                    title=str(title or item.get("name") or "Source"),
                    url=url,
                )
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return list(found.values())[:12]


def _demo_analysis(markets: list[Market], category: str) -> AnalysisResult:
    analyses = []
    for market in markets:
        probability = market.outcomes[0].probability if market.outcomes else 0.5
        analyses.append(
            MarketAnalysis(
                market_slug=market.slug,
                market_title=market.title,
                market_probability=probability,
                fair_probability=probability,
                assessment="fair",
                risks=[
                    "Demo mode does not use live news",
                    "Resolution criteria may affect the outcome",
                ],
                reasoning=(
                    "Demo mode mirrors the current market probability. "
                    "Configure OPENAI_API_KEY for a live, source-backed estimate."
                ),
            )
        )
    return AnalysisResult(
        category=category,
        summary="Demo analysis based on current market prices.",
        overall_insights=(
            "Live web research is disabled until an OpenAI API key is configured."
        ),
        markets=analyses,
        demo=True,
    )


def analyze_markets(markets: list[Market], category: str) -> AnalysisResult:
    if not markets:
        return AnalysisResult(
            category=category,
            summary="No active markets were found in this category.",
            overall_insights="Choose another category or try again later.",
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        if os.getenv("DEMO_MODE", "true").casefold() == "true":
            return _demo_analysis(markets, category)
        raise AIUnavailableError("OPENAI_API_KEY is not configured.")

    try:
        response = OpenAI(api_key=api_key).responses.parse(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=SYSTEM_INSTRUCTIONS,
            input=_build_input(markets, category),
            tools=[{"type": "web_search"}],
            include=["web_search_call.action.sources"],
            reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")},
            text_format=GeneratedAnalysis,
        )
        generated = response.output_parsed
        if generated is None:
            raise AIUnavailableError(
                "The AI response did not contain usable data."
            )
    except RateLimitError as exc:
        raise AIUnavailableError(
            "The OpenAI rate limit was reached. Please try again later."
        ) from exc
    except (APIConnectionError, APIStatusError) as exc:
        raise AIUnavailableError("OpenAI is currently unavailable.") from exc

    generated_by_title = {
        item.market_title.casefold(): item for item in generated.markets
    }
    analyses: list[MarketAnalysis] = []
    for market in markets:
        item = generated_by_title.get(market.title.casefold())
        market_probability = market.outcomes[0].probability if market.outcomes else 0.5
        if item is None:
            analyses.append(
                MarketAnalysis(
                    market_slug=market.slug,
                    market_title=market.title,
                    market_probability=market_probability,
                    assessment="fair",
                    reasoning="No individual analysis was generated for this market.",
                )
            )
            continue
        analyses.append(
            MarketAnalysis(
                market_slug=market.slug,
                market_title=market.title,
                market_probability=market_probability,
                fair_probability=item.fair_probability,
                assessment=_normalize_assessment(item.assessment),
                risks=item.risks[:5],
                reasoning=item.reasoning,
            )
        )

    return AnalysisResult(
        category=category,
        summary=generated.summary,
        overall_insights=generated.overall_insights,
        markets=analyses,
        sources=_extract_sources(response.model_dump()),
    )
