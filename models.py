from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal


class Outcome(BaseModel):
    """Represents a market outcome with its price/probability"""
    title: str
    price: float
    probability: float  # Implied probability from price


class Market(BaseModel):
    """Represents a Polymarket market"""
    slug: str
    title: str
    description: Optional[str] = None
    volume: float
    liquidity: Optional[float] = None
    outcomes: List[Outcome]
    category: Optional[str] = None
    active: bool = True


class Category(BaseModel):
    """Represents a market category/tag"""
    id: str
    name: str
    description: Optional[str] = None


class MarketAnalysis(BaseModel):
    """Analysis result for a single market"""
    market_slug: str
    market_title: str
    fair_probability: Optional[float] = None  # AI's assessment of fair probability
    market_probability: float  # Current market probability
    assessment: str  # AI's assessment (e.g., "overpriced", "fair", "underpriced")
    risks: List[str] = []
    reasoning: str


class AnalysisResult(BaseModel):
    """Complete analysis result for a set of markets"""
    category: str
    summary: str  # Text summary from OpenAI
    markets: List[MarketAnalysis]  # Structured analysis per market
    overall_insights: Optional[str] = None
