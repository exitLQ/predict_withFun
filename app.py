import logging
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthError,
    authenticate,
    bootstrap_admin,
    create_session,
    create_user,
    delete_session,
    session_user,
    valid_csrf,
)
from database import (
    accuracy_summaries,
    admin_database_statistics,
    calibration_series,
    database_is_available,
    get_analysis,
    list_analyses,
    list_forecast_scores,
    save_analysis,
)
from infrastructure import (
    distributed_rate_limit_allowed,
    redis_client,
    redis_is_available,
)
from job_queue import get_job_status, submit_job
from job_tasks import run_accuracy_sync_task, run_comparison_task
from models import (
    AccuracySummary,
    AdminMetrics,
    AnalysisHistoryItem,
    AnalysisResult,
    AuthCredentials,
    CalibrationSeries,
    Category,
    ForecastScore,
    HealthResponse,
    JobStatus,
    Market,
    PricePoint,
    ProviderComparison,
    ReadinessResponse,
    ResolutionSyncResult,
    UserProfile,
)
from monitoring import initialize_monitoring, monitoring_enabled
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
initialize_monitoring()
bootstrap_admin()

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


@app.get(
    "/api/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness() -> ReadinessResponse | JSONResponse:
    database_ready = await run_in_threadpool(database_is_available)
    redis_configured = bool(os.getenv("REDIS_URL"))
    redis_ready = (
        await run_in_threadpool(redis_is_available) if redis_configured else False
    )
    redis_required = os.getenv("BACKGROUND_QUEUE", "local") == "rq"
    unavailable = not database_ready or (redis_required and not redis_ready)
    degraded = redis_configured and not redis_ready
    result = ReadinessResponse(
        status=(
            "unavailable" if unavailable else "degraded" if degraded else "ready"
        ),
        database=database_ready,
        redis_configured=redis_configured,
        redis_available=redis_ready,
        redis_required=redis_required,
        sentry_configured=monitoring_enabled(),
    )
    if unavailable:
        return JSONResponse(status_code=503, content=result.model_dump(mode="json"))
    return result


async def _current_user(request: Request) -> UserProfile | None:
    return await run_in_threadpool(
        session_user,
        request.cookies.get(SESSION_COOKIE),
    )


async def _require_user(
    request: Request,
    *,
    role: str | None = None,
    csrf: bool = False,
) -> UserProfile:
    user = await _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if role and user.role != role:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    if csrf:
        cookie = request.cookies.get(CSRF_COOKIE)
        supplied = request.headers.get("X-CSRF-Token")
        if (
            not cookie
            or not supplied
            or not secrets.compare_digest(cookie, supplied)
            or not await run_in_threadpool(
                valid_csrf,
                request.cookies.get(SESSION_COOKIE),
                supplied,
            )
        ):
            raise HTTPException(status_code=403, detail="Invalid CSRF token.")
    return user


async def _require_analysis_access(request: Request) -> UserProfile | None:
    if os.getenv("AUTH_REQUIRED", "false").casefold() != "true":
        return await _current_user(request)
    return await _require_user(request, csrf=True)


async def _authorize_admin(request: Request, *, csrf: bool = False) -> None:
    user = await _current_user(request)
    if user is not None and user.role == "admin":
        if csrf:
            await _require_user(request, role="admin", csrf=True)
        return
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


def _set_session_cookies(
    response: Response,
    session_token: str,
    csrf_token: str,
) -> None:
    production = os.getenv("ENVIRONMENT", "development").casefold() == "production"
    max_age = max(1, min(int(os.getenv("SESSION_TTL_HOURS", "168")), 720)) * 3600
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=production,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=production,
        samesite="strict",
        path="/",
    )


@app.post("/api/auth/register", response_model=UserProfile)
async def register(credentials: AuthCredentials, response: Response) -> UserProfile:
    if os.getenv("ALLOW_REGISTRATION", "false").casefold() != "true":
        raise HTTPException(status_code=403, detail="Registration is disabled.")
    try:
        user = await run_in_threadpool(
            create_user,
            credentials.email,
            credentials.password,
        )
    except AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    session_token, csrf_token = await run_in_threadpool(create_session, user.id)
    _set_session_cookies(response, session_token, csrf_token)
    return user


@app.post("/api/auth/login", response_model=UserProfile)
async def login(credentials: AuthCredentials, response: Response) -> UserProfile:
    try:
        user = await run_in_threadpool(
            authenticate,
            credentials.email,
            credentials.password,
        )
    except AuthError:
        user = None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    session_token, csrf_token = await run_in_threadpool(create_session, user.id)
    _set_session_cookies(response, session_token, csrf_token)
    return user


@app.get("/api/auth/me", response_model=UserProfile)
async def auth_me(request: Request) -> UserProfile:
    return await _require_user(request)


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    await _require_user(request, csrf=True)
    await run_in_threadpool(
        delete_session,
        request.cookies.get(SESSION_COOKIE),
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"logged_out": True}


@app.get("/api/admin/metrics", response_model=AdminMetrics)
async def admin_metrics(request: Request) -> AdminMetrics:
    await _authorize_admin(request)
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
    await _require_analysis_access(request)
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
    await _require_analysis_access(request)
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
    await _require_analysis_access(request)
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
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
) -> list[AnalysisHistoryItem]:
    if os.getenv("AUTH_REQUIRED", "false").casefold() == "true":
        await _require_user(request)
    return await run_in_threadpool(list_analyses, limit)


@app.get("/api/analyses/{record_id}", response_model=AnalysisResult)
async def get_saved_analysis(request: Request, record_id: str) -> AnalysisResult:
    if os.getenv("AUTH_REQUIRED", "false").casefold() == "true":
        await _require_user(request)
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
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> ResolutionSyncResult:
    await _authorize_admin(request, csrf=True)
    data = await run_in_threadpool(run_accuracy_sync_task, limit)
    return ResolutionSyncResult.model_validate(data)


@app.post("/api/jobs/compare", response_model=JobStatus)
async def submit_comparison_job(
    request: Request,
    category_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
) -> JobStatus:
    await _require_analysis_access(request)
    _enforce_analysis_limit(request)
    return submit_job(run_comparison_task, category_id, limit)


@app.post("/api/jobs/accuracy-sync", response_model=JobStatus)
async def submit_accuracy_sync_job(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> JobStatus:
    await _authorize_admin(request, csrf=True)
    return submit_job(run_accuracy_sync_task, limit)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def read_job_status(request: Request, job_id: str) -> JobStatus:
    if os.getenv("AUTH_REQUIRED", "false").casefold() == "true":
        await _require_user(request)
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
