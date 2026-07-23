from fastapi.testclient import TestClient

import app

client = TestClient(app.app)


def _empty_admin_statistics():
    return {
        "stored_analyses": 0,
        "estimated_cost_usd": 0,
        "total_forecasts": 0,
        "resolved_forecasts": 0,
        "providers": {},
    }


def test_health_endpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("BACKGROUND_QUEUE", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "openai_configured": False,
        "grok_configured": False,
        "claude_configured": False,
        "redis_configured": False,
        "background_queue": "local",
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


def test_admin_endpoint_requires_configured_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setattr(app, "admin_database_statistics", _empty_admin_statistics)
    monkeypatch.setattr(app, "redis_client", lambda: None)

    unauthorized = client.get("/api/admin/metrics")
    authorized = client.get(
        "/api/admin/metrics",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["stored_analyses"] == 0


def test_admin_endpoint_is_disabled_without_token_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    response = client.get("/api/admin/metrics")

    assert response.status_code == 503


def test_analysis_history_endpoints(monkeypatch):
    item = app.AnalysisHistoryItem(
        id="saved-id",
        created_at="2026-07-23T10:00:00Z",
        category="Politics",
        provider="openai",
        requested_provider="openai",
        market_count=2,
        estimated_cost_usd=0.01,
    )
    result = app.AnalysisResult(category="Politics", summary="Restored")
    monkeypatch.setattr(app, "list_analyses", lambda limit: [item])
    monkeypatch.setattr(
        app,
        "get_analysis",
        lambda record_id: result if record_id == "saved-id" else None,
    )

    history = client.get("/api/analyses?limit=10")
    restored = client.get("/api/analyses/saved-id")
    missing = client.get("/api/analyses/missing")

    assert history.status_code == 200
    assert history.json()[0]["category"] == "Politics"
    assert restored.json()["summary"] == "Restored"
    assert missing.status_code == 404


def test_compare_endpoint_returns_all_demo_providers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(
        app,
        "run_comparison_task",
        lambda *args: app.ProviderComparison(
            results=[
                app.AnalysisResult(
                    category="Politics",
                    summary="Demo",
                    demo=True,
                    research_provider=provider,
                    requested_provider=provider,
                )
                for provider in ("openai", "grok", "claude")
            ]
        ).model_dump(mode="json"),
    )

    response = client.post("/api/compare?category_id=1&limit=1")

    assert response.status_code == 200
    assert {item["research_provider"] for item in response.json()["results"]} == {
        "openai",
        "grok",
        "claude",
    }
