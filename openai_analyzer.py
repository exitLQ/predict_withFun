import os

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from models import AnalysisResult, Market, MarketAnalysis

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-sol"
SYSTEM_INSTRUCTIONS = """
Du analysierst Prognosemärkte nüchtern und transparent. Trenne beobachtete
Marktpreise von deiner Schätzung. Behaupte keine Kenntnis zukünftiger Ereignisse.
Berücksichtige Basisraten, Aktualität, Liquidität, Auflösungsregeln und bekannte
Informationslücken. Verwende ausschließlich die gelieferten Marktdaten und
formuliere auf Deutsch. Die Ausgabe ist keine Finanzberatung.
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
        f'Analysiere die folgenden Märkte der Kategorie "{category}".',
        "Bewerte jeweils die Wahrscheinlichkeit des ersten Outcomes.",
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
                    f"Volumen: ${market.volume:,.0f}; "
                    f"Liquidität: ${market.liquidity or 0:,.0f}"
                ),
                f"Outcomes: {outcomes}",
                f"Beschreibung: {market.description or 'nicht angegeben'}",
                "",
            ]
        )
    return "\n".join(lines)


def _normalize_assessment(value: str) -> str:
    normalized = value.casefold()
    if "unter" in normalized or "under" in normalized:
        return "unterbewertet"
    if "über" in normalized or "over" in normalized:
        return "überbewertet"
    return "fair"


def analyze_markets(markets: list[Market], category: str) -> AnalysisResult:
    if not markets:
        return AnalysisResult(
            category=category,
            summary="Keine aktiven Märkte in dieser Kategorie gefunden.",
            overall_insights=(
                "Wähle eine andere Kategorie oder versuche es später erneut."
            ),
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIUnavailableError("OPENAI_API_KEY ist nicht konfiguriert.")

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
                "Die KI-Antwort enthielt keine auswertbaren Daten."
            )
    except RateLimitError as exc:
        raise AIUnavailableError(
            "Das OpenAI-Limit wurde erreicht. Bitte versuche es später erneut."
        ) from exc
    except (APIConnectionError, APIStatusError) as exc:
        raise AIUnavailableError("OpenAI ist momentan nicht erreichbar.") from exc

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
                    reasoning="Für diesen Markt wurde keine Einzelanalyse erzeugt.",
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
