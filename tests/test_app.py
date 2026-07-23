from fastapi.testclient import TestClient

import app

client = TestClient(app.app)


def test_health_endpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "openai_configured": False,
        "grok_configured": False,
        "claude_configured": False,
        "demo_mode": True,
    }


def test_categories_endpoint(monkeypatch):
    monkeypatch.setattr(
        app,
        "fetch_categories",
        lambda: [app.Category(id="1", name="Politics")],
    )

    response = client.get("/api/categories")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Politics"


def test_compare_endpoint_returns_all_demo_providers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(
        app,
        "fetch_categories",
        lambda: [app.Category(id="1", name="Politics")],
    )
    monkeypatch.setattr(
        app,
        "get_top_markets_for_category",
        lambda *args: [
            app.Market(slug="demo", title="Demo", volume=100, outcomes=[])
        ],
    )

    response = client.post("/api/compare?category_id=1&limit=1")

    assert response.status_code == 200
    assert {item["research_provider"] for item in response.json()["results"]} == {
        "openai",
        "grok",
        "claude",
    }
