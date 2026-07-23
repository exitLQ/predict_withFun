import json

import pytest

import resolution_sync


def test_resolution_sync_cli_prints_machine_readable_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        resolution_sync,
        "run_accuracy_sync_task",
        lambda limit: {
            "checked_markets": limit,
            "newly_resolved_markets": 2,
            "scored_forecasts": 5,
        },
    )

    assert resolution_sync.main(["--limit", "25"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["checked_markets"] == 25
    assert output["scored_forecasts"] == 5


def test_resolution_sync_cli_rejects_invalid_limit():
    with pytest.raises(SystemExit):
        resolution_sync.main(["--limit", "0"])
