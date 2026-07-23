import contextvars
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
_configured = False
_sensitive_fragments = (
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
)


def set_request_id(value: str) -> contextvars.Token:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def _safe_value(key: str, value: Any) -> Any:
    if any(fragment in key.casefold() for fragment in _sensitive_fragments):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item): _safe_value(str(item), child)
            for item, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in value[:50]]
    if isinstance(value, str):
        return value[:1000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:1000]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": _request_id.get(),
        }
        fields = getattr(record, "event_fields", {})
        if isinstance(fields, dict):
            document.update(
                {
                    str(key): _safe_value(str(key), value)
                    for key, value in fields.items()
                }
            )
        if record.exc_info:
            document["exception_type"] = record.exc_info[0].__name__
        return json.dumps(document, separators=(",", ":"), ensure_ascii=True)


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logger = logging.getLogger("predict_with_fun")
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "json").casefold() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    _configured = True


def get_logger(component: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"predict_with_fun.{component}")


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger.log(
        level,
        event,
        extra={"event": event, "event_fields": fields},
    )
