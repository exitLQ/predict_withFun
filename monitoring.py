import logging
import os
from typing import Any

from structured_logging import get_logger, log_event

logger = get_logger("monitoring")
_initialized = False


def _sample_rate(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, 0.0), 1.0)


def _scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    del hint
    event.pop("user", None)
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("cookies", "data", "env", "headers", "query_string"):
            request.pop(key, None)
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        for breadcrumb in breadcrumbs["values"]:
            if isinstance(breadcrumb, dict):
                breadcrumb.pop("data", None)
    event.pop("extra", None)
    return event


def initialize_monitoring() -> bool:
    global _initialized
    if _initialized:
        return True
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT")
            or os.getenv("ENVIRONMENT", "development"),
            release=os.getenv("SENTRY_RELEASE") or None,
            traces_sample_rate=_sample_rate("SENTRY_TRACES_SAMPLE_RATE", 0.1),
            profiles_sample_rate=_sample_rate("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
            send_default_pii=False,
            before_send=_scrub_event,
        )
    except Exception as error:
        log_event(
            logger,
            logging.ERROR,
            "monitoring_initialization_failed",
            error_type=type(error).__name__,
        )
        return False
    _initialized = True
    log_event(logger, logging.INFO, "monitoring_initialized")
    return True


def monitoring_enabled() -> bool:
    return _initialized
