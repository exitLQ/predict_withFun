import polymarket_client


def test_market_parses_string_encoded_outcomes():
    market = polymarket_client._market_from_api(
        {
            "slug": "will-it-rain",
            "question": "Will it rain?",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.62", "0.38"]',
            "clobTokenIds": '["token-yes", "token-no"]',
            "volume": "1200.5",
            "liquidity": "300",
            "active": True,
        },
        "Weather",
        "rain-event",
    )

    assert market is not None
    assert market.outcomes[0].title == "Yes"
    assert market.outcomes[0].probability == 0.62
    assert market.url == "https://polymarket.com/event/rain-event"
    assert market.token_id == "token-yes"


def test_price_history_is_normalized(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"history": [{"t": 100, "p": "0.42"}]}

    monkeypatch.setattr(
        polymarket_client._session,
        "get",
        lambda *args, **kwargs: Response(),
    )

    history = polymarket_client.fetch_price_history("token", "1d", 60)

    assert history == [{"timestamp": 100, "price": 0.42}]


def test_top_markets_are_flattened_and_sorted(monkeypatch):
    monkeypatch.setattr(
        polymarket_client,
        "fetch_markets_by_category",
        lambda _: [
            {
                "slug": "event",
                "markets": [
                    {
                        "slug": "small",
                        "question": "Small",
                        "outcomes": '["Yes"]',
                        "outcomePrices": '["0.1"]',
                        "volume": 10,
                    },
                    {
                        "slug": "large",
                        "question": "Large",
                        "outcomes": '["Yes"]',
                        "outcomePrices": '["0.9"]',
                        "volume": 100,
                    },
                ],
            }
        ],
    )

    markets = polymarket_client.get_top_markets_for_category("1", "Test", 1)

    assert [market.slug for market in markets] == ["large"]


def test_closed_market_resolution_is_detected(monkeypatch):
    monkeypatch.setattr(
        polymarket_client,
        "_get",
        lambda *args: {
            "closed": True,
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["1", "0"]',
        },
    )

    assert polymarket_client.fetch_market_resolution("resolved-market") == 1.0


def test_ambiguous_market_is_not_treated_as_resolved(monkeypatch):
    monkeypatch.setattr(
        polymarket_client,
        "_get",
        lambda *args: {"closed": True, "outcomePrices": '["0.6", "0.4"]'},
    )

    assert polymarket_client.fetch_market_resolution("ambiguous") is None


def test_api_cache_is_bounded(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    monkeypatch.setenv("POLYMARKET_CACHE_MAX_ENTRIES", "2")
    monkeypatch.setattr(
        polymarket_client._session,
        "get",
        lambda *args, **kwargs: Response(),
    )
    polymarket_client._cache.clear()

    for identifier in ("one", "two", "three"):
        polymarket_client._get("/tags", {"id": identifier})

    assert len(polymarket_client._cache) == 2
