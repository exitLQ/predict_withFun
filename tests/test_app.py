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
