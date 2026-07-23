import json
import logging

import structured_logging


def test_json_formatter_adds_context_and_redacts_sensitive_fields():
    token = structured_logging.set_request_id("request-123")
    try:
        record = logging.LogRecord(
            "predict_with_fun.test",
            logging.INFO,
            __file__,
            1,
            "test",
            (),
            None,
        )
        record.event = "test_event"
        record.event_fields = {
            "provider": "openai",
            "api_key": "must-not-appear",
            "nested": {"authorization": "Bearer secret"},
        }

        document = json.loads(structured_logging.JsonFormatter().format(record))
    finally:
        structured_logging.reset_request_id(token)

    assert document["event"] == "test_event"
    assert document["request_id"] == "request-123"
    assert document["provider"] == "openai"
    assert document["api_key"] == "[REDACTED]"
    assert document["nested"]["authorization"] == "[REDACTED]"
    assert "must-not-appear" not in json.dumps(document)
