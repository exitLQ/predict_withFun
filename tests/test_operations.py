import operations


def test_runtime_metrics_snapshot():
    operations._reset_for_tests()
    operations.increment("cache_hits")
    operations.increment("cache_misses")
    operations.record_provider("openai", 100, True)
    operations.record_provider("openai", 300, False)
    operations.record_retry("openai")

    snapshot = operations.metrics_snapshot()

    assert snapshot["cache_hit_rate"] == 0.5
    assert snapshot["providers"]["openai"]["calls"] == 2
    assert snapshot["providers"]["openai"]["average_duration_ms"] == 200
    assert snapshot["providers"]["openai"]["retries"] == 1
