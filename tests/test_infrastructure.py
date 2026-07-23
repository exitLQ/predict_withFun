import sys
import time
from types import SimpleNamespace

import infrastructure
import job_queue


def _successful_job():
    return {"finished": True}


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value

    def eval(self, script, keys, key, cutoff, limit, now, member):
        return 1


def test_shared_cache_and_job_status(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(infrastructure, "_redis_checked", True)
    monkeypatch.setattr(infrastructure, "_redis_client", fake)

    infrastructure.shared_cache_set("key", {"value": 1}, 60)
    infrastructure.store_job_status(
        "job",
        {"id": "job", "status": "finished", "result": {"ok": True}},
    )

    assert infrastructure.shared_cache_get("key") == {"value": 1}
    assert infrastructure.load_job_status("job")["status"] == "finished"
    assert infrastructure.distributed_rate_limit_allowed("client", 5) is True


def test_local_background_job_finishes(monkeypatch):
    monkeypatch.setattr(infrastructure, "_redis_checked", True)
    monkeypatch.setattr(infrastructure, "_redis_client", None)
    monkeypatch.setattr(job_queue, "redis_client", lambda: None)
    monkeypatch.setattr(job_queue, "load_job_status", lambda _: None)

    job = job_queue.submit_job(_successful_job)
    status = None
    for _ in range(100):
        status = job_queue.get_job_status(job.id)
        if status and status.status == "finished":
            break
        time.sleep(0.01)

    assert status is not None
    assert status.status == "finished"
    assert status.result == {"finished": True}


def test_local_background_job_preserves_owner(monkeypatch):
    monkeypatch.setattr(infrastructure, "_redis_checked", True)
    monkeypatch.setattr(infrastructure, "_redis_client", None)
    monkeypatch.setattr(job_queue, "redis_client", lambda: None)
    monkeypatch.setattr(job_queue, "load_job_status", lambda _: None)

    job = job_queue.submit_job(_successful_job, owner_id="user-1")
    status = job_queue.get_job_status(job.id)

    assert job.owner_id == "user-1"
    assert status is not None
    assert status.owner_id == "user-1"


def test_redis_connection_is_retried_after_failure(monkeypatch):
    calls = {"count": 0}

    class Client:
        def __init__(self, fails):
            self.fails = fails

        def ping(self):
            if self.fails:
                raise ConnectionError("temporary")
            return True

    class Redis:
        @staticmethod
        def from_url(*args, **kwargs):
            calls["count"] += 1
            return Client(calls["count"] == 1)

    clock = {"now": 100.0}
    monkeypatch.setenv("REDIS_URL", "redis://example")
    monkeypatch.setenv("REDIS_RETRY_SECONDS", "5")
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=Redis))
    monkeypatch.setattr(infrastructure.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(infrastructure, "_redis_client", None)
    monkeypatch.setattr(infrastructure, "_redis_checked", False)
    monkeypatch.setattr(infrastructure, "_redis_retry_at", 0.0)

    assert infrastructure.redis_client() is None
    assert infrastructure.redis_client() is None
    clock["now"] = 106.0
    assert infrastructure.redis_client() is not None
    assert calls["count"] == 2
