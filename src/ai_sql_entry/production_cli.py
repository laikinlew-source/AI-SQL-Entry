from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .production_validation import (
    ProductionConfig,
    load_production_config,
    run_production_once,
    write_production_reports,
)


Runner = Callable[..., dict[str, object]]


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner = run_production_once,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-sql-production",
        description="Run the local read-only production invoice validation coordinator.",
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--poll-seconds", type=float)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one scan (the default).")
    mode.add_argument("--watch", action="store_true", help="Repeat scans until interrupted.")
    arguments = parser.parse_args(argv)

    try:
        config_path = arguments.config
        if config_path is None:
            candidate = (arguments.project_root or Path.cwd()) / "config" / "production_validation.json"
            if candidate.is_file():
                config_path = candidate
        config = load_production_config(
            config_path,
            project_root=arguments.project_root,
        )
        if arguments.poll_seconds is not None:
            if arguments.poll_seconds < 0:
                parser.error("--poll-seconds must not be negative")
            config = replace(config, poll_interval_seconds=arguments.poll_seconds)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    def run_once() -> dict[str, object]:
        report = runner(config, now=datetime.now(timezone.utc))
        paths = write_production_reports(config, report)
        return {
            "run_id": report.get("run_id"),
            "processed": report.get("processed", 0),
            "skipped": report.get("skipped", 0),
            "production_report": str(paths["json"]),
            "production_dashboard": str(paths["current_dashboard"]),
        }

    try:
        if not arguments.watch:
            print(json.dumps(run_once(), indent=2))
            return 0
        while True:
            print(json.dumps(run_once(), indent=2))
            sleeper(config.poll_interval_seconds)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
