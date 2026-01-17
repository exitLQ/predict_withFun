import requests
from typing import List, Optional
from models import Category, Market, Outcome


POLYMARKET_BASE_URL = "https://gamma-api.polymarket.com"


def fetch_categories() -> List[Category]:
    """Fetch all categories/tags from Polymarket"""
    try:
        response = requests.get(f"{POLYMARKET_BASE_URL}/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        categories = []
        for tag in data:
            categories.append(Category(
                id=str(tag.get("id", "")),
                name=tag.get("name", "Unknown"),
                description=tag.get("description")
            ))
        return categories
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return []


def fetch_markets_by_category(tag_id: str) -> List[dict]:
    """Fetch open markets for a specific category"""
    try:
        params = {
            "tag_id": tag_id,
            "active": "true",
            "closed": "false"
        }
        response = requests.get(
            f"{POLYMARKET_BASE_URL}/events",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error fetching markets for category {tag_id}: {e}")
        return []


def fetch_market_details(market_slug: str) -> Optional[Market]:
    """Fetch detailed information for a specific market"""
    try:
        response = requests.get(
            f"{POLYMARKET_BASE_URL}/markets",
            params={"slug": market_slug},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            return None
        
        market_data = data[0] if isinstance(data, list) else data
        
        # Extract outcomes and prices
        outcomes = []
        condition_id = market_data.get("conditionId")
        
        # Try to get outcome prices from the market data
        # Polymarket API structure may vary, so we handle different formats
        if "outcomePrices" in market_data:
            prices = market_data["outcomePrices"]
            if isinstance(prices, list):
                for i, price in enumerate(prices):
                    prob = float(price) if price else 0.0
                    outcomes.append(Outcome(
                        title=f"Outcome {i+1}",
                        price=prob,
                        probability=prob
                    ))
        elif "tokens" in market_data:
            # Alternative structure with tokens
            tokens = market_data["tokens"]
            for token in tokens:
                outcomes.append(Outcome(
                    title=token.get("outcome", "Unknown"),
                    price=float(token.get("price", 0)),
                    probability=float(token.get("price", 0))
                ))
        
        # Get volume
        volume = float(market_data.get("volume", 0))
        liquidity = market_data.get("liquidity")
        if liquidity:
            liquidity = float(liquidity)
        
        return Market(
            slug=market_slug,
            title=market_data.get("question", market_data.get("title", "Unknown Market")),
            description=market_data.get("description"),
            volume=volume,
            liquidity=liquidity,
            outcomes=outcomes,
            active=market_data.get("active", True)
        )
    except Exception as e:
        print(f"Error fetching market details for {market_slug}: {e}")
        return None


def get_top_markets_by_volume(markets: List[Market], n: int = 10) -> List[Market]:
    """Sort markets by volume and return top N"""
    sorted_markets = sorted(markets, key=lambda m: m.volume, reverse=True)
    return sorted_markets[:n]


def get_top_markets_for_category(tag_id: str, tag_name: str, n: int = 10) -> List[Market]:
    """Get top N markets by volume for a category"""
    events = fetch_markets_by_category(tag_id)
    markets = []
    
    for event in events:
        slug = event.get("slug") or event.get("id")
        if not slug:
            continue
        
        market = fetch_market_details(slug)
        if market:
            market.category = tag_name
            markets.append(market)
    
    return get_top_markets_by_volume(markets, n)
