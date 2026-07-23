import argparse
import json
import logging
import os
from typing import Sequence

from job_tasks import run_accuracy_sync_task
from structured_logging import get_logger, log_event

logger = get_logger("resolution")


def _default_limit() -> int:
    return int(os.getenv("AUTO_RESOLUTION_LIMIT", "500"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score stored forecasts for newly resolved Polymarket markets."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=_default_limit(),
        choices=range(1, 1001),
        metavar="1-1000",
        help="Maximum number of unresolved market slugs to check.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_accuracy_sync_task(args.limit)
    log_event(logger, logging.INFO, "resolution_sync_completed", **result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
