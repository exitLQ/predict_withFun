import os
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from models import AnalysisResult, Market, MarketAnalysis, Source

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_XAI_MODEL = "grok-4.5"
XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
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
                if not title or str(title).isdigit():
                    title = (
                        "X post"
                        if urlparse(url).netloc in {"x.com", "www.x.com"}
                        else urlparse(url).netloc
                    )
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


def _demo_analysis(
    markets: list[Market], category: str, provider: str
) -> AnalysisResult:
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
                    "Configure the selected provider for a live, "
                    "source-backed estimate."
                ),
            )
        )
    return AnalysisResult(
        category=category,
        summary="Demo analysis based on current market prices.",
        overall_insights=(
            "Live research is disabled until the selected provider is configured."
        ),
        markets=analyses,
        demo=True,
        research_provider=provider,
    )


def _analyze_with_claude(
    markets: list[Market], category: str, api_key: str
) -> tuple[GeneratedAnalysis, dict[str, Any]]:
    import anthropic

    try:
        client = anthropic.Anthropic(api_key=api_key)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": _build_input(markets, category)}
        ]
        options: dict[str, Any] = {
            "model": os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
            "max_tokens": 4096,
            "system": SYSTEM_INSTRUCTIONS,
            "messages": messages,
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3,
                }
            ],
            "output_format": GeneratedAnalysis,
        }
        response = client.messages.parse(**options)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            response = client.messages.parse(**{**options, "messages": messages})
        generated = response.parsed_output
        if generated is None:
            raise AIUnavailableError(
                "The Claude response did not contain usable data."
            )
        return generated, response.to_dict()
    except anthropic.RateLimitError as exc:
        raise AIUnavailableError(
            "The Anthropic rate limit was reached. Please try again later."
        ) from exc
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        raise AIUnavailableError("Anthropic is currently unavailable.") from exc


def analyze_markets(
    markets: list[Market],
    category: str,
    provider: str = "openai",
) -> AnalysisResult:
    if provider not in {"openai", "grok", "claude"}:
        raise AIUnavailableError("Unsupported research provider.")
    if not markets:
        return AnalysisResult(
            category=category,
            summary="No active markets were found in this category.",
            overall_insights="Choose another category or try again later.",
        )

    key_names = {
        "openai": "OPENAI_API_KEY",
        "grok": "XAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }
    api_key = os.getenv(key_names[provider])
    if not api_key:
        if os.getenv("DEMO_MODE", "true").casefold() == "true":
            return _demo_analysis(markets, category, provider)
        raise AIUnavailableError(f"{key_names[provider]} is not configured.")

    if provider == "claude":
        generated, response_data = _analyze_with_claude(
            markets, category, api_key
        )
    else:
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=XAI_BASE_URL if provider == "grok" else None,
            )
            request_options: dict[str, Any] = {
                "model": (
                    os.getenv("XAI_MODEL", DEFAULT_XAI_MODEL)
                    if provider == "grok"
                    else os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
                ),
                "instructions": SYSTEM_INSTRUCTIONS,
                "input": _build_input(markets, category),
                "tools": [
                    {"type": "x_search"}
                    if provider == "grok"
                    else {"type": "web_search"}
                ],
                "text_format": GeneratedAnalysis,
            }
            if provider == "openai":
                request_options["include"] = [
                    "web_search_call.action.sources"
                ]
                request_options["reasoning"] = {
                    "effort": os.getenv("OPENAI_REASONING_EFFORT", "low")
                }
            else:
                request_options["prompt_cache_key"] = "predict-with-fun-analysis"
            response = client.responses.parse(**request_options)
            generated = response.output_parsed
            if generated is None:
                raise AIUnavailableError(
                    "The AI response did not contain usable data."
                )
            response_data = response.model_dump()
        except RateLimitError as exc:
            raise AIUnavailableError(
                "The research provider rate limit was reached. "
                "Please try again later."
            ) from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise AIUnavailableError(
                "The selected research provider is currently unavailable."
            ) from exc

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
        sources=_extract_sources(response_data),
        research_provider=provider,
    )
