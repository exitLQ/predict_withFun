import json
import os
import time
import uuid
from typing import Any

_redis_client: Any | None = None
_redis_checked = False


def redis_client() -> Any | None:
    global _redis_checked, _redis_client
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


def redis_is_available() -> bool:
    client = redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def shared_cache_get(key: str) -> dict[str, Any] | None:
    client = redis_client()
    if client is None:
        return None
    try:
        value = client.get(f"predict_with_fun:cache:{key}")
        return json.loads(value) if value else None
    except Exception:
        return None


def shared_cache_set(key: str, value: dict[str, Any], ttl: int) -> None:
    client = redis_client()
    if client is None:
        return
    try:
        client.setex(
            f"predict_with_fun:cache:{key}",
            ttl,
            json.dumps(value),
        )
    except Exception:
        return


def distributed_rate_limit_allowed(identity: str, limit: int) -> bool | None:
    client = redis_client()
    if client is None:
        return None
    key = f"predict_with_fun:rate:{identity}"
    now = time.time()
    member = f"{now}:{uuid.uuid4()}"
    script = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
    local count = redis.call('ZCARD', KEYS[1])
    if count >= tonumber(ARGV[2]) then return 0 end
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
    redis.call('EXPIRE', KEYS[1], 3600)
    return 1
    """
    try:
        return bool(
            client.eval(script, 1, key, now - 3600, limit, now, member)
        )
    except Exception:
        return None


def store_job_status(job_id: str, value: dict[str, Any]) -> None:
    client = redis_client()
    if client is None:
        return
    try:
        client.setex(
            f"predict_with_fun:job:{job_id}",
            int(os.getenv("JOB_RESULT_TTL", "3600")),
            json.dumps(value),
        )
    except Exception:
        return


def load_job_status(job_id: str) -> dict[str, Any] | None:
    client = redis_client()
    if client is None:
        return None
    try:
        value = client.get(f"predict_with_fun:job:{job_id}")
        return json.loads(value) if value else None
    except Exception:
        return None
