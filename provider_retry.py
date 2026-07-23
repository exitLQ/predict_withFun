import logging
import os
import random
import time
from collections.abc import Callable
from typing import TypeVar

from operations import record_retry
from structured_logging import get_logger, log_event

T = TypeVar("T")

_DEFAULTS = {
    "openai": (2, 0.5, 4.0),
    "grok": (3, 1.0, 8.0),
    "claude": (2, 1.0, 6.0),
}
logger = get_logger("retry")


def _number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


def retry_settings(provider: str) -> tuple[int, float, float]:
    retries, base_delay, maximum_delay = _DEFAULTS[provider]
    prefix = provider.upper()
    return (
        int(_number(f"{prefix}_MAX_RETRIES", retries, 0, 8)),
        _number(f"{prefix}_RETRY_BASE_DELAY", base_delay, 0, 60),
        _number(f"{prefix}_RETRY_MAX_DELAY", maximum_delay, 0, 60),
    )


def is_retryable_provider_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code in {408, 409, 425, 429}:
        return True
    if isinstance(status_code, int) and status_code >= 500:
        return True
    name = type(error).__name__.casefold()
    return "ratelimit" in name or "timeout" in name or "connection" in name


def _retry_after(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) if response is not None else {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def call_with_retry(
    provider: str,
    operation: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    max_retries, base_delay, maximum_delay = retry_settings(provider)
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as error:
            if attempt >= max_retries or not is_retryable_provider_error(error):
                raise
            server_delay = _retry_after(error)
            if server_delay is None:
                exponential = min(base_delay * (2**attempt), maximum_delay)
                delay = min(
                    exponential + random.uniform(0, exponential * 0.25),
                    maximum_delay,
                )
            else:
                delay = min(server_delay, maximum_delay)
            record_retry(provider)
            log_event(
                logger,
                logging.WARNING,
                "provider_retry_scheduled",
                provider=provider,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_seconds=round(delay, 3),
                error_type=type(error).__name__,
                status_code=getattr(error, "status_code", None),
            )
            sleep(delay)
    raise RuntimeError("Provider retry loop ended unexpectedly.")
