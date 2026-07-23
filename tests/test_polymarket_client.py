import polymarket_client


def test_market_parses_string_encoded_outcomes():
    market = polymarket_client._market_from_api(
        {
            "slug": "will-it-rain",
            "question": "Wird es regnen?",
            "outcomes": '["Ja", "Nein"]',
            "outcomePrices": '["0.62", "0.38"]',
            "volume": "1200.5",
            "liquidity": "300",
            "active": True,
        },
        "Wetter",
        "rain-event",
    )

    assert market is not None
    assert market.outcomes[0].title == "Ja"
    assert market.outcomes[0].probability == 0.62
    assert market.url == "https://polymarket.com/event/rain-event"


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
