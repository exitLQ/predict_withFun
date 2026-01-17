from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List
import os

from models import Category, Market, AnalysisResult
from polymarket_client import fetch_categories, get_top_markets_for_category
from openai_analyzer import analyze_markets

app = FastAPI(title="Polymarket Analysis Tool")

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def read_root():
    """Serve the frontend"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Please create static/index.html"}


@app.get("/api/categories", response_model=List[Category])
async def get_categories():
    """Get all available categories"""
    try:
        categories = fetch_categories()
        return categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")


@app.get("/api/markets/{category_id}", response_model=List[Market])
async def get_markets(category_id: str):
    """Get top 10 markets for a category by volume"""
    try:
        # First, get the category name
        categories = fetch_categories()
        category = next((c for c in categories if c.id == category_id), None)
        
        if not category:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        
        markets = get_top_markets_for_category(category_id, category.name, n=10)
        return markets
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching markets: {str(e)}")


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_category_markets(category_id: str = Query(..., description="Category ID to analyze")):
    """Analyze top markets for a category using OpenAI"""
    try:
        # Get category name
        categories = fetch_categories()
        category = next((c for c in categories if c.id == category_id), None)
        
        if not category:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        
        # Get top markets
        markets = get_top_markets_for_category(category_id, category.name, n=10)
        
        if not markets:
            return AnalysisResult(
                category=category.name,
                summary="Keine Märkte in dieser Kategorie gefunden.",
                markets=[],
                overall_insights="Keine Daten verfügbar."
            )
        
        # Analyze with OpenAI
        analysis = analyze_markets(markets, category.name)
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing markets: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
