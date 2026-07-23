import os
import time
from asyncio import gather
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_analysis, list_analyses, save_analysis
from models import (
    AnalysisHistoryItem,
    AnalysisResult,
    Category,
    HealthResponse,
    Market,
    PricePoint,
    ProviderComparison,
)
from openai_analyzer import AIUnavailableError, analyze_markets
from polymarket_client import (
    PolymarketError,
    fetch_categories,
    fetch_price_history,
    get_top_markets_for_category,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="predict_withFun",
    description="Explore Polymarket data and put market signals into context with AI.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
_analysis_requests: dict[str, deque[float]] = defaultdict(deque)


def _enforce_analysis_limit(request: Request) -> None:
    limit = int(os.getenv("ANALYSIS_REQUESTS_PER_HOUR", "5"))
    identity = request.client.host if request.client else "unknown"
    now = time.time()
    requests = _analysis_requests[identity]
    while requests and now - requests[0] > 3600:
        requests.popleft()
    if len(requests) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Analysis limit reached ({limit} per hour). Try again later.",
        )
    requests.append(now)


async def _category_or_404(category_id: str) -> Category:
    categories = await run_in_threadpool(fetch_categories)
    category = next((item for item in categories if item.id == category_id), None)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    return category


@app.get("/", include_in_schema=False)
async def read_root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        openai_configured=bool(os.getenv("OPENAI_API_KEY")),
        grok_configured=bool(os.getenv("XAI_API_KEY")),
        claude_configured=bool(os.getenv("ANTHROPIC_API_KEY")),
        demo_mode=(
            not bool(
                os.getenv("OPENAI_API_KEY")
                or os.getenv("XAI_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
            )
            and os.getenv("DEMO_MODE", "true").casefold() == "true"
        ),
    )


@app.get("/api/categories", response_model=list[Category])
async def get_categories() -> list[Category]:
    try:
        return await run_in_threadpool(fetch_categories)
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/markets/{category_id}", response_model=list[Market])
async def get_markets(
    category_id: str,
    limit: int = Query(default=10, ge=1, le=25),
) -> list[Market]:
    try:
        category = await _category_or_404(category_id)
        return await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, limit
        )
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_category_markets(
    request: Request,
    category_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
    provider: str = Query(default="openai", pattern="^(openai|grok|claude)$"),
) -> AnalysisResult:
    _enforce_analysis_limit(request)
    try:
        category = await _category_or_404(category_id)
        markets = await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, limit
        )
        result = await run_in_threadpool(
            analyze_markets, markets, category.name, provider
        )
        await run_in_threadpool(save_analysis, result)
        return result
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/compare", response_model=ProviderComparison)
async def compare_category_markets(
    request: Request,
    category_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
) -> ProviderComparison:
    _enforce_analysis_limit(request)
    try:
        category = await _category_or_404(category_id)
        markets = await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, limit
        )
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
        raise HTTPException(status_code=503, detail="No AI provider is configured.")

    async def run_provider(provider: str) -> tuple[str, AnalysisResult | Exception]:
        try:
            result = await run_in_threadpool(
                analyze_markets, markets, category.name, provider, False
            )
            return provider, result
        except AIUnavailableError as exc:
            return provider, exc

    outcomes = await gather(*(run_provider(provider) for provider in providers))
    successful = [
        result for _, result in outcomes if isinstance(result, AnalysisResult)
    ]
    await gather(
        *(run_in_threadpool(save_analysis, result) for result in successful)
    )
    return ProviderComparison(
        results=successful,
        errors={
            provider: str(result)
            for provider, result in outcomes
            if isinstance(result, Exception)
        },
    )


@app.post(
    "/api/analyze/{category_id}/{market_slug}",
    response_model=AnalysisResult,
)
async def analyze_single_market(
    request: Request,
    category_id: str,
    market_slug: str,
    provider: str = Query(default="openai", pattern="^(openai|grok|claude)$"),
) -> AnalysisResult:
    _enforce_analysis_limit(request)
    try:
        category = await _category_or_404(category_id)
        markets = await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, 100
        )
        market = next((item for item in markets if item.slug == market_slug), None)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found.")
        result = await run_in_threadpool(
            analyze_markets, [market], category.name, provider
        )
        await run_in_threadpool(save_analysis, result)
        return result
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/analyses", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[AnalysisHistoryItem]:
    return await run_in_threadpool(list_analyses, limit)


@app.get("/api/analyses/{record_id}", response_model=AnalysisResult)
async def get_saved_analysis(record_id: str) -> AnalysisResult:
    result = await run_in_threadpool(get_analysis, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


@app.get(
    "/api/history/{category_id}/{market_slug}",
    response_model=list[PricePoint],
)
async def get_market_history(
    category_id: str,
    market_slug: str,
    interval: str = Query(default="1m", pattern="^(1h|6h|1d|1w|1m|max)$"),
) -> list[PricePoint]:
    try:
        category = await _category_or_404(category_id)
        markets = await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, 100
        )
        market = next((item for item in markets if item.slug == market_slug), None)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found.")
        if not market.token_id:
            return []
        history = await run_in_threadpool(
            fetch_price_history, market.token_id, interval, 60
        )
        return [PricePoint(**point) for point in history]
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
    )
