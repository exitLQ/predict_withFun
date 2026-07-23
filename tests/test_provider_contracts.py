import sys
from types import ModuleType, SimpleNamespace

import pytest

import openai_analyzer
from models import Market, Outcome


def _market():
    return Market(
        slug="contract-market",
        title="Will the contract pass?",
        description="A test market.",
        volume=12_000,
        liquidity=3_000,
        outcomes=[
            Outcome(title="Yes", price=0.45, probability=0.45),
            Outcome(title="No", price=0.55, probability=0.55),
        ],
    )


def _generated():
    return openai_analyzer.GeneratedAnalysis(
        summary="Evidence summary",
        overall_insights="Uncertainty remains.",
        markets=[
            openai_analyzer.GeneratedMarketAnalysis(
                market_title="Will the contract pass?",
                fair_probability=0.6,
                assessment="underpriced",
                risks=["Policy change"],
                reasoning="Primary evidence supports a higher estimate.",
            )
        ],
    )


class FakeOpenAIResponse:
    output_parsed = _generated()

    def model_dump(self):
        return {
            "usage": {"input_tokens": 120, "output_tokens": 40},
            "output": [
                {"type": "web_search_call"},
                {
                    "sources": [
                        {
                            "title": "Primary source",
                            "url": "https://example.gov/report?utm_source=test",
                        }
                    ]
                },
            ],
        }


def _install_fake_openai(monkeypatch):
    calls = []

    class FakeResponses:
        def parse(self, **options):
            calls.append(options)
            return FakeOpenAIResponse()

    class FakeOpenAI:
        instances = []

        def __init__(self, **options):
            self.options = options
            self.responses = FakeResponses()
            self.instances.append(self)

    monkeypatch.setattr(openai_analyzer, "OpenAI", FakeOpenAI)
    return calls, FakeOpenAI


def test_openai_api_contract_is_fully_mocked(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-openai-model")
    calls, fake_client = _install_fake_openai(monkeypatch)

    result = openai_analyzer._analyze_provider(
        [_market()], "Policy", "openai"
    )

    assert fake_client.instances[0].options == {
        "api_key": "test-key",
        "base_url": None,
    }
    request = calls[0]
    assert request["model"] == "test-openai-model"
    assert request["tools"] == [{"type": "web_search"}]
    assert request["text_format"] is openai_analyzer.GeneratedAnalysis
    assert request["reasoning"] == {"effort": "low"}
    assert request["include"] == ["web_search_call.action.sources"]
    assert "BEGIN_UNTRUSTED_MARKET_DATA" in request["input"]
    assert result.markets[0].fair_probability == 0.6
    assert result.markets[0].assessment == "undervalued"
    assert result.sources[0].url == "https://example.gov/report"
    assert result.usage.input_tokens == 120
    assert result.usage.search_calls == 1


def test_grok_api_contract_uses_x_search(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_MODEL", "test-grok-model")
    calls, fake_client = _install_fake_openai(monkeypatch)

    result = openai_analyzer._analyze_provider([_market()], "Policy", "grok")

    assert fake_client.instances[0].options["base_url"] == openai_analyzer.XAI_BASE_URL
    request = calls[0]
    assert request["model"] == "test-grok-model"
    assert request["tools"] == [{"type": "x_search"}]
    assert request["prompt_cache_key"] == "predict-with-fun-analysis"
    assert "include" not in request
    assert result.research_provider == "grok"


def test_claude_api_contract_continues_paused_tool_turn(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-claude-model")
    calls = []

    class FakeClaudeResponse:
        def __init__(self, paused):
            self.stop_reason = "pause_turn" if paused else "end_turn"
            self.content = [{"type": "text", "text": "tool continuation"}]
            self.parsed_output = None if paused else _generated()

        def to_dict(self):
            return {
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 80,
                    "server_tool_use": {"web_search_requests": 2},
                }
            }

    class FakeMessages:
        def parse(self, **options):
            calls.append(options)
            return FakeClaudeResponse(paused=len(calls) == 1)

    fake_module = ModuleType("anthropic")
    fake_module.Anthropic = lambda **_: SimpleNamespace(messages=FakeMessages())
    fake_module.RateLimitError = type("RateLimitError", (Exception,), {})
    fake_module.APIConnectionError = type("APIConnectionError", (Exception,), {})
    fake_module.APIStatusError = type("APIStatusError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    result = openai_analyzer._analyze_provider(
        [_market()], "Policy", "claude"
    )

    assert len(calls) == 2
    assert calls[0]["model"] == "test-claude-model"
    assert calls[0]["tools"][0]["type"] == "web_search_20250305"
    assert calls[0]["output_format"] is openai_analyzer.GeneratedAnalysis
    assert len(calls[1]["messages"]) == 2
    assert calls[1]["messages"][1]["role"] == "assistant"
    assert result.research_provider == "claude"
    assert result.usage.search_calls == 2


def test_openai_connection_error_is_translated_without_network(monkeypatch):
    class FakeConnectionError(Exception):
        pass

    class FailingResponses:
        def parse(self, **_):
            raise FakeConnectionError("private upstream detail")

    class FailingOpenAI:
        def __init__(self, **_):
            self.responses = FailingResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "0")
    monkeypatch.setattr(openai_analyzer, "OpenAI", FailingOpenAI)
    monkeypatch.setattr(openai_analyzer, "APIConnectionError", FakeConnectionError)

    with pytest.raises(
        openai_analyzer.AIUnavailableError,
        match="currently unavailable",
    ):
        openai_analyzer._analyze_provider([_market()], "Policy", "openai")
