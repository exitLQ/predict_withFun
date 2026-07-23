import threading
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_provider_metrics: dict[str, dict[str, float | int]] = defaultdict(
    lambda: {
        "calls": 0,
        "successes": 0,
        "failures": 0,
        "retries": 0,
        "duration_ms": 0.0,
    }
)


def increment(metric: str) -> None:
    with _lock:
        _counters[metric] += 1


def record_provider(provider: str, duration_ms: float, success: bool) -> None:
    with _lock:
        metrics = _provider_metrics[provider]
        metrics["calls"] += 1
        metrics["successes" if success else "failures"] += 1
        metrics["duration_ms"] += duration_ms


def record_retry(provider: str) -> None:
    with _lock:
        _provider_metrics[provider]["retries"] += 1


def metrics_snapshot() -> dict[str, Any]:
    with _lock:
        counters = dict(_counters)
        providers = {
            name: {
                "calls": int(values["calls"]),
                "successes": int(values["successes"]),
                "failures": int(values["failures"]),
                "retries": int(values["retries"]),
                "average_duration_ms": round(
                    float(values["duration_ms"]) / max(int(values["calls"]), 1),
                    1,
                ),
            }
            for name, values in _provider_metrics.items()
        }
    hits = counters.get("cache_hits", 0)
    misses = counters.get("cache_misses", 0)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "analysis_requests": counters.get("analysis_requests", 0),
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_hit_rate": round(hits / max(hits + misses, 1), 4),
        "jobs_queued": counters.get("jobs_queued", 0),
        "jobs_finished": counters.get("jobs_finished", 0),
        "jobs_failed": counters.get("jobs_failed", 0),
        "rate_limited": counters.get("rate_limited", 0),
        "providers": providers,
    }


def _reset_for_tests() -> None:
    with _lock:
        _counters.clear()
        _provider_metrics.clear()
