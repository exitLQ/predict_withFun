import json
import time
from typing import Any

import requests

from models import Category, Market, Outcome

POLYMARKET_BASE_URL = "https://gamma-api.polymarket.com"
POLYMARKET_WEB_URL = "https://polymarket.com/event"
CLOB_BASE_URL = "https://clob.polymarket.com"
REQUEST_TIMEOUT = 20
CACHE_TTL_SECONDS = 300

_session = requests.Session()
_session.headers.update(
    {
        "Accept": "application/json",
        "User-Agent": "predict-with-fun/2.0 (+https://github.com/exitLQ/predict_withFun)",
    }
)
_cache: dict[str, tuple[float, Any]] = {}


class PolymarketError(RuntimeError):
    pass


def _get(path: str, params: dict[str, Any]) -> Any:
    cache_key = f"{path}:{json.dumps(params, sort_keys=True)}"
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = _session.get(
            f"{POLYMARKET_BASE_URL}{path}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PolymarketError("Polymarket is currently unavailable.") from exc

    _cache[cache_key] = (time.monotonic(), data)
    return data


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def fetch_categories() -> list[Category]:
    data = _get("/tags", {"limit": 100})
    if not isinstance(data, list):
        raise PolymarketError("Polymarket returned an unexpected data format.")

    categories = [
        Category(
            id=str(tag["id"]),
            name=str(tag.get("label") or tag.get("name") or "Untitled"),
            description=tag.get("description"),
        )
        for tag in data
        if tag.get("id") is not None
    ]
    return sorted(categories, key=lambda category: category.name.casefold())


def fetch_markets_by_category(tag_id: str) -> list[dict[str, Any]]:
    data = _get(
        "/events",
        {
            "tag_id": tag_id,
            "active": "true",
            "closed": "false",
            "limit": 100,
        },
    )
    if not isinstance(data, list):
        raise PolymarketError("Polymarket returned an unexpected data format.")
    return data


def _market_from_api(
    raw: dict[str, Any], category: str, event_slug: str
) -> Market | None:
    slug = str(raw.get("slug") or "")
    title = str(raw.get("question") or raw.get("title") or "")
    if not slug or not title:
        return None

    names = _as_list(raw.get("outcomes"))
    prices = _as_list(raw.get("outcomePrices"))
    token_ids = _as_list(raw.get("clobTokenIds"))
    outcomes = []
    for index, name in enumerate(names):
        probability = min(1.0, _as_float(prices[index] if index < len(prices) else 0))
        outcomes.append(
            Outcome(title=str(name), price=probability, probability=probability)
        )

    return Market(
        slug=slug,
        title=title,
        description=raw.get("description"),
        volume=_as_float(raw.get("volumeNum", raw.get("volume"))),
        liquidity=_as_float(raw.get("liquidityNum", raw.get("liquidity")))
        if raw.get("liquidityNum", raw.get("liquidity")) is not None
        else None,
        outcomes=outcomes,
        category=category,
        active=bool(raw.get("active", True)),
        url=f"{POLYMARKET_WEB_URL}/{event_slug}" if event_slug else None,
        token_id=str(token_ids[0]) if token_ids else None,
    )


def get_top_markets_for_category(
    tag_id: str, tag_name: str, n: int = 10
) -> list[Market]:
    markets: list[Market] = []
    for event in fetch_markets_by_category(tag_id):
        event_slug = str(event.get("slug") or "")
        raw_markets = event.get("markets")
        if not isinstance(raw_markets, list):
            continue
        for raw_market in raw_markets:
            if isinstance(raw_market, dict):
                market = _market_from_api(raw_market, tag_name, event_slug)
                if market:
                    markets.append(market)

    return sorted(markets, key=lambda market: market.volume, reverse=True)[:n]


def fetch_price_history(
    token_id: str, interval: str = "1m", fidelity: int = 60
) -> list[dict[str, float | int]]:
    if interval not in {"1h", "6h", "1d", "1w", "1m", "max"}:
        raise PolymarketError("Unsupported price-history interval.")
    try:
        response = _session.get(
            f"{CLOB_BASE_URL}/prices-history",
            params={
                "market": token_id,
                "interval": interval,
                "fidelity": fidelity,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PolymarketError("Price history is currently unavailable.") from exc
    history = data.get("history", []) if isinstance(data, dict) else []
    return [
        {"timestamp": int(point["t"]), "price": min(1.0, _as_float(point["p"]))}
        for point in history
        if isinstance(point, dict) and "t" in point and "p" in point
    ]
