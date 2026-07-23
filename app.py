import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import AnalysisResult, Category, HealthResponse, Market
from openai_analyzer import AIUnavailableError, analyze_markets
from polymarket_client import (
    PolymarketError,
    fetch_categories,
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
    category_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
) -> AnalysisResult:
    try:
        category = await _category_or_404(category_id)
        markets = await run_in_threadpool(
            get_top_markets_for_category, category_id, category.name, limit
        )
        return await run_in_threadpool(analyze_markets, markets, category.name)
    except PolymarketError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
    )
