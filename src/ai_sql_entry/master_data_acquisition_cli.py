from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .master_data_acquisition import run_master_data_acquisition


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-sql-master-data-acquire",
        description=(
            "Discover local SQL Account master-data exports, validate all four, "
            "build snapshots, and rerun invoice readiness."
        ),
    )
    parser.add_argument("--incoming-dir", type=Path, default=Path("incoming/master-data"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--invoice-root", type=Path, default=Path("."))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--generated-at")
    arguments = parser.parse_args(argv)
    generated_at = (
        datetime.fromisoformat(arguments.generated_at.replace("Z", "+00:00"))
        if arguments.generated_at
        else None
    )
    report = run_master_data_acquisition(
        arguments.incoming_dir,
        arguments.config_dir,
        arguments.output_root,
        invoice_root=arguments.invoice_root,
        generated_at=generated_at,
        dry_run=arguments.dry_run,
    )
    printable = dict(report)
    printable["report_paths"] = {
        name: str(path) for name, path in report["report_paths"].items()
    }
    print(json.dumps(printable, indent=2, ensure_ascii=False, default=str))
    return 0 if report["status"] in {"written", "dry_run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
