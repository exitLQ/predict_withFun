import logging
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import (
    accuracy_summaries,
    admin_database_statistics,
    calibration_series,
    get_analysis,
    list_analyses,
    list_forecast_scores,
    save_analysis,
)
from infrastructure import distributed_rate_limit_allowed, redis_client
from job_queue import get_job_status, submit_job
from job_tasks import run_accuracy_sync_task, run_comparison_task
from models import (
    AccuracySummary,
    AdminMetrics,
    AnalysisHistoryItem,
    AnalysisResult,
    CalibrationSeries,
    Category,
    ForecastScore,
    HealthResponse,
    JobStatus,
    Market,
    PricePoint,
    ProviderComparison,
    ResolutionSyncResult,
)
from openai_analyzer import AIUnavailableError, analyze_markets
from operations import increment, metrics_snapshot
from polymarket_client import (
    PolymarketError,
    fetch_categories,
    fetch_price_history,
    get_top_markets_for_category,
)
from structured_logging import (
    get_logger,
    log_event,
    reset_request_id,
    set_request_id,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
logger = get_logger("http")

app = FastAPI(
    title="predict_withFun",
    description="Explore Polymarket data and put market signals into context with AI.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
_analysis_requests: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied)
        else str(uuid.uuid4())
    )
    token = set_request_id(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        log_event(
            logger,
            logging.INFO,
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        log_event(
            logger,
            logging.ERROR,
            "http_request_failed",
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
        )
        raise
    finally:
        reset_request_id(token)


def _enforce_analysis_limit(request: Request) -> None:
    increment("analysis_requests")
    limit = int(os.getenv("ANALYSIS_REQUESTS_PER_HOUR", "5"))
    identity = request.client.host if request.client else "unknown"
    distributed = distributed_rate_limit_allowed(identity, limit)
    if distributed is False:
        increment("rate_limited")
        raise HTTPException(
            status_code=429,
            detail=f"Analysis limit reached ({limit} per hour). Try again later.",
        )
    if distributed is True:
        return
    now = time.time()
    requests = _analysis_requests[identity]
    while requests and now - requests[0] > 3600:
        requests.popleft()
    if len(requests) >= limit:
        increment("rate_limited")
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
        redis_configured=bool(os.getenv("REDIS_URL")),
        background_queue=(
            "rq" if os.getenv("BACKGROUND_QUEUE", "local") == "rq" else "local"
        ),
        demo_mode=(
            not bool(
                os.getenv("OPENAI_API_KEY")
                or os.getenv("XAI_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
            )
            and os.getenv("DEMO_MODE", "true").casefold() == "true"
        ),
    )


def _authorize_admin(request: Request) -> None:
    configured_token = os.getenv("ADMIN_TOKEN", "")
    production = os.getenv("ENVIRONMENT", "development").casefold() == "production"
    if not configured_token:
        if production:
            raise HTTPException(
                status_code=503,
                detail="The admin dashboard is disabled until ADMIN_TOKEN is set.",
            )
        return
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {configured_token}"
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@app.get("/api/admin/metrics", response_model=AdminMetrics)
async def admin_metrics(request: Request) -> AdminMetrics:
    _authorize_admin(request)
    process = metrics_snapshot()
    database_available = True
    try:
        stored = await run_in_threadpool(admin_database_statistics)
    except Exception:
        database_available = False
        stored = {
            "stored_analyses": 0,
            "estimated_cost_usd": 0,
            "total_forecasts": 0,
            "resolved_forecasts": 0,
            "providers": {},
        }
    providers = []
    for provider in ("openai", "grok", "claude"):
        runtime = process["providers"].get(provider, {})
        durable = stored["providers"].get(provider, {})
        providers.append(
            {
                "provider": provider,
                "calls": runtime.get("calls", 0),
                "successes": runtime.get("successes", 0),
                "failures": runtime.get("failures", 0),
                "retries": runtime.get("retries", 0),
                "average_duration_ms": runtime.get("average_duration_ms", 0),
                "stored_analyses": durable.get("stored_analyses", 0),
                "estimated_cost_usd": durable.get("estimated_cost_usd", 0),
            }
        )
    return AdminMetrics(
        **{key: value for key, value in process.items() if key != "providers"},
        database_available=database_available,
        redis_configured=bool(os.getenv("REDIS_URL")),
        redis_available=redis_client() is not None,
        background_queue=(
            "rq" if os.getenv("BACKGROUND_QUEUE", "local") == "rq" else "local"
        ),
        providers=providers,
        **{key: value for key, value in stored.items() if key != "providers"},
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
        data = await run_in_threadpool(run_comparison_task, category_id, limit)
        return ProviderComparison.model_validate(data)
    except (PolymarketError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


@app.get("/api/accuracy", response_model=list[AccuracySummary])
async def get_accuracy_summary() -> list[AccuracySummary]:
    return await run_in_threadpool(accuracy_summaries)


@app.get("/api/accuracy/calibration", response_model=list[CalibrationSeries])
async def get_calibration_series(
    bins: int = Query(default=10, ge=5, le=20),
) -> list[CalibrationSeries]:
    return await run_in_threadpool(calibration_series, bins)


@app.get("/api/accuracy/forecasts", response_model=list[ForecastScore])
async def get_forecast_scores(
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ForecastScore]:
    return await run_in_threadpool(list_forecast_scores, limit)


@app.post("/api/accuracy/sync", response_model=ResolutionSyncResult)
async def sync_accuracy(
    limit: int = Query(default=100, ge=1, le=500),
) -> ResolutionSyncResult:
    data = await run_in_threadpool(run_accuracy_sync_task, limit)
    return ResolutionSyncResult.model_validate(data)


@app.post("/api/jobs/compare", response_model=JobStatus)
async def submit_comparison_job(
    request: Request,
    category_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
) -> JobStatus:
    _enforce_analysis_limit(request)
    return submit_job(run_comparison_task, category_id, limit)


@app.post("/api/jobs/accuracy-sync", response_model=JobStatus)
async def submit_accuracy_sync_job(
    limit: int = Query(default=100, ge=1, le=500),
) -> JobStatus:
    return submit_job(run_accuracy_sync_task, limit)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def read_job_status(job_id: str) -> JobStatus:
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Background job not found.")
    return status


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
