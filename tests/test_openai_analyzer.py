import openai_analyzer
from models import Market, Outcome


def test_demo_analysis_works_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    market = Market(
        slug="demo-market",
        title="Demo market",
        volume=1000,
        outcomes=[Outcome(title="Yes", price=0.6, probability=0.6)],
    )

    result = openai_analyzer.analyze_markets([market], "Demo")

    assert result.demo is True
    assert result.markets[0].fair_probability == 0.6
    assert result.markets[0].assessment == "fair"


def test_grok_demo_reports_selected_provider(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    market = Market(
        slug="grok-demo",
        title="Grok demo",
        volume=500,
        outcomes=[Outcome(title="Yes", price=0.4, probability=0.4)],
    )

    result = openai_analyzer.analyze_markets([market], "Demo", "grok")

    assert result.demo is True
    assert result.research_provider == "grok"
