from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .master_data_builder import DATASET_KEYS, build_snapshot


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.parent / f"{path.name}.{uuid4().hex}.tmp"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, path)


def main(argv: Sequence[str] | None = None) -> int:
    """Build one local SQL Accounting master-data snapshot."""
    parser = argparse.ArgumentParser(
        prog="ai-sql-master-data",
        description=(
            "Validate CSV, XLSX, or JSON master data and safely replace one "
            "local SQL Accounting snapshot."
        ),
    )
    parser.add_argument("dataset", choices=tuple(DATASET_KEYS))
    parser.add_argument("input", type=Path)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--min-retention-ratio",
        type=Decimal,
        default=Decimal("0.50"),
    )
    arguments = parser.parse_args(argv)

    report = build_snapshot(
        arguments.dataset,
        arguments.input,
        arguments.config_dir,
        dry_run=arguments.dry_run,
        minimum_retention_ratio=arguments.min_retention_ratio,
        sheet_name=arguments.sheet,
    )
    report_path = arguments.report
    if report_path is None:
        timestamp_token = re.sub(r"[^0-9]", "", report["generated_at"])
        report_path = (
            Path("output")
            / "master-data-import-reports"
            / f"{arguments.dataset}-{timestamp_token}.json"
        )
    report["statistics_report_path"] = str(report_path)
    _write_report(report_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in {"valid", "written"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
