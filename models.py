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


class AnalysisResult(BaseModel):
    category: str
    summary: str
    markets: list[MarketAnalysis] = Field(default_factory=list)
    overall_insights: str | None = None
    disclaimer: str = (
        "AI-generated assessment for informational purposes only — "
        "not financial advice."
    )


class HealthResponse(BaseModel):
    status: Literal["ok"]
    openai_configured: bool
