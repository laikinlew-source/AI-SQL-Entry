from __future__ import annotations

import json
import io
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ai_sql_entry.snapshot_cli import main


RUNTIME = Path(__file__).parent / "runtime"


class SnapshotCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = RUNTIME / self._testMethodName
        shutil.rmtree(self.work_dir, ignore_errors=True)
        self.config_dir = self.work_dir / "config"
        self.config_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def _snapshot(self, dataset: str, records: list[dict[str, object]]) -> Path:
        path = self.config_dir / f"{dataset}.json"
        path.write_text(
            json.dumps({"schema_version": "1.0.0", dataset: records}),
            encoding="utf-8",
        )
        return path

    def test_dry_run_writes_statistics_but_does_not_replace_snapshot(self) -> None:
        snapshot_path = self._snapshot(
            "currencies", [{"code": "MYR", "active": True}]
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "currencies.csv"
        source.write_text("code,active\nUSD,true\n", encoding="utf-8")
        report_path = self.work_dir / "dry-run-report.json"

        with redirect_stdout(io.StringIO()):
            exit_code = main(
                [
                    "currencies",
                    str(source),
                    "--config-dir",
                    str(self.config_dir),
                    "--report",
                    str(report_path),
                    "--dry-run",
                ]
            )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "valid")
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["snapshot_written"])
        self.assertEqual(snapshot_path.read_bytes(), original)

    def test_retention_warning_returns_nonzero_and_preserves_snapshot(self) -> None:
        snapshot_path = self._snapshot(
            "suppliers",
            [
                {"code": f"SUP-{index}", "name": f"Supplier {index}"}
                for index in range(4)
            ],
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "suppliers.csv"
        source.write_text("code,name\nSUP-X,Replacement Supplier\n", encoding="utf-8")
        report_path = self.work_dir / "blocked-report.json"

        with redirect_stdout(io.StringIO()):
            exit_code = main(
                [
                    "suppliers",
                    str(source),
                    "--config-dir",
                    str(self.config_dir),
                    "--report",
                    str(report_path),
                ]
            )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["warnings"])
        self.assertEqual(snapshot_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
