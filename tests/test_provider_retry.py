import operations
import provider_retry


class ProviderError(RuntimeError):
    def __init__(self, status_code, retry_after=None):
        super().__init__("provider error")
        self.status_code = status_code
        self.response = type(
            "Response",
            (),
            {"headers": {"retry-after": retry_after} if retry_after else {}},
        )()


def test_transient_error_retries_with_retry_after(monkeypatch):
    operations._reset_for_tests()
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "2")
    attempts = []
    delays = []

    def operation():
        attempts.append(True)
        if len(attempts) == 1:
            raise ProviderError(429, "1.5")
        return "ok"

    result = provider_retry.call_with_retry("openai", operation, sleep=delays.append)

    assert result == "ok"
    assert len(attempts) == 2
    assert delays == [1.5]
    assert operations.metrics_snapshot()["providers"]["openai"]["retries"] == 1


def test_permanent_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("CLAUDE_MAX_RETRIES", "4")
    attempts = []

    def operation():
        attempts.append(True)
        raise ProviderError(401)

    try:
        provider_retry.call_with_retry("claude", operation, sleep=lambda _: None)
    except ProviderError:
        pass
    else:
        raise AssertionError("A permanent provider error must be raised.")

    assert len(attempts) == 1


def test_provider_retry_settings_are_bounded(monkeypatch):
    monkeypatch.setenv("GROK_MAX_RETRIES", "99")
    monkeypatch.setenv("GROK_RETRY_BASE_DELAY", "-2")
    monkeypatch.setenv("GROK_RETRY_MAX_DELAY", "999")

    assert provider_retry.retry_settings("grok") == (8, 0, 60)
