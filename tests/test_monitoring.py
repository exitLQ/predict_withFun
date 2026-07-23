import monitoring


def test_sentry_event_scrubbing_removes_request_and_user_data():
    event = {
        "user": {"ip_address": "127.0.0.1"},
        "request": {
            "url": "https://example.test/api/health",
            "headers": {"Authorization": "Bearer secret"},
            "query_string": "token=secret",
            "data": {"prompt": "private"},
        },
        "extra": {"api_key": "secret"},
        "breadcrumbs": {"values": [{"message": "request", "data": {"token": "x"}}]},
    }

    scrubbed = monitoring._scrub_event(event, {})

    assert "user" not in scrubbed
    assert "headers" not in scrubbed["request"]
    assert "query_string" not in scrubbed["request"]
    assert "data" not in scrubbed["request"]
    assert "extra" not in scrubbed
    assert "data" not in scrubbed["breadcrumbs"]["values"][0]


def test_monitoring_sample_rates_are_bounded(monkeypatch):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "4")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "-1")

    assert monitoring._sample_rate("SENTRY_TRACES_SAMPLE_RATE", 0.1) == 1
    assert monitoring._sample_rate("SENTRY_PROFILES_SAMPLE_RATE", 0.0) == 0
