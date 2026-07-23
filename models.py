from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Outcome(BaseModel):
    title: str
    price: float = Field(ge=0, le=1)
    probability: float = Field(ge=0, le=1)


class Market(BaseModel):
    slug: str
    title: str
    description: str | None = None
    volume: float = Field(ge=0)
    liquidity: float | None = Field(default=None, ge=0)
    outcomes: list[Outcome] = Field(default_factory=list)
    category: str | None = None
    active: bool = True
    url: str | None = None
    token_id: str | None = None


class Category(BaseModel):
    id: str
    name: str
    description: str | None = None


class MarketAnalysis(BaseModel):
    market_slug: str
    market_title: str
    fair_probability: float | None = Field(default=None, ge=0, le=1)
    market_probability: float = Field(ge=0, le=1)
    assessment: Literal["undervalued", "fair", "overvalued"]
    risks: list[str] = Field(default_factory=list)
    reasoning: str


class Source(BaseModel):
    title: str
    url: str


class PricePoint(BaseModel):
    timestamp: int
    price: float = Field(ge=0, le=1)


class UsageInfo(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)


class AnalysisResult(BaseModel):
    category: str
    summary: str
    markets: list[MarketAnalysis] = Field(default_factory=list)
    overall_insights: str | None = None
    sources: list[Source] = Field(default_factory=list)
    demo: bool = False
    research_provider: Literal["openai", "grok", "claude"] = "openai"
    requested_provider: Literal["openai", "grok", "claude"] = "openai"
    fallback_used: bool = False
    cached: bool = False
    usage: UsageInfo = Field(default_factory=UsageInfo)
    disclaimer: str = (
        "AI-generated assessment for informational purposes only — "
        "not financial advice."
    )


class ProviderComparison(BaseModel):
    results: list[AnalysisResult] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
    synthesis: "ComparisonSynthesis | None" = None


class ConsensusMarket(BaseModel):
    market_slug: str
    market_title: str
    market_probability: float = Field(ge=0, le=1)
    mean_probability: float = Field(ge=0, le=1)
    median_probability: float = Field(ge=0, le=1)
    weighted_probability: float = Field(ge=0, le=1)
    minimum_probability: float = Field(ge=0, le=1)
    maximum_probability: float = Field(ge=0, le=1)
    spread: float = Field(ge=0, le=1)
    disagreement: Literal["low", "moderate", "high"]
    assessment: Literal["undervalued", "fair", "overvalued"]
    providers: list[Literal["openai", "grok", "claude"]]
    shared_risks: list[str] = Field(default_factory=list)


class ComparisonSynthesis(BaseModel):
    method: str
    provider_weights: dict[str, float]
    markets: list[ConsensusMarket] = Field(default_factory=list)


class AnalysisHistoryItem(BaseModel):
    id: str
    created_at: datetime
    category: str
    provider: Literal["openai", "grok", "claude"]
    requested_provider: Literal["openai", "grok", "claude"]
    market_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    resolved_outcome: float | None = Field(default=None, ge=0, le=1)
    brier_score: float | None = Field(default=None, ge=0, le=1)


class ForecastScore(BaseModel):
    analysis_id: str
    provider: Literal["openai", "grok", "claude"]
    created_at: datetime
    market_slug: str
    market_title: str
    predicted_probability: float = Field(ge=0, le=1)
    market_probability: float = Field(ge=0, le=1)
    outcome: float | None = Field(default=None, ge=0, le=1)
    brier_score: float | None = Field(default=None, ge=0, le=1)


class AccuracySummary(BaseModel):
    provider: Literal["openai", "grok", "claude"]
    resolved_forecasts: int = Field(ge=0)
    mean_brier_score: float = Field(ge=0, le=1)
    mean_market_brier_score: float = Field(ge=0, le=1)
    mean_absolute_error: float = Field(ge=0, le=1)


class ResolutionSyncResult(BaseModel):
    checked_markets: int = Field(ge=0)
    newly_resolved_markets: int = Field(ge=0)
    scored_forecasts: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    openai_configured: bool
    grok_configured: bool
    claude_configured: bool
    demo_mode: bool
