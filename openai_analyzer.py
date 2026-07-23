import os

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from models import AnalysisResult, Market, MarketAnalysis

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-sol"
SYSTEM_INSTRUCTIONS = """
Analyze prediction markets objectively and transparently. Separate observed
market prices from your own estimate. Never claim knowledge of future events.
Consider base rates, recency, liquidity, resolution rules, and known information
gaps. Use only the supplied market data and respond in English. The output is
not financial advice.
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
        "",
    ]
    for index, market in enumerate(markets, 1):
        outcomes = ", ".join(
            f"{outcome.title}: {outcome.probability:.1%}"
            for outcome in market.outcomes
        ) or "keine Preisdaten"
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


def analyze_markets(markets: list[Market], category: str) -> AnalysisResult:
    if not markets:
        return AnalysisResult(
            category=category,
            summary="No active markets were found in this category.",
            overall_insights=(
                "Choose another category or try again later."
            ),
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIUnavailableError("OPENAI_API_KEY is not configured.")

    try:
        response = OpenAI(api_key=api_key).responses.parse(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=SYSTEM_INSTRUCTIONS,
            input=_build_input(markets, category),
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
    )
