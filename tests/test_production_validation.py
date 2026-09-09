from __future__ import annotations

import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.production_validation import (
    create_run_id,
    discover_invoice_files,
    ensure_production_roots,
    load_production_config,
)


class ProductionConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path(__file__).parent / "runtime" / "production-config"
        shutil.rmtree(self.runtime, ignore_errors=True)
        self.runtime.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_loads_default_production_roots_and_discovers_only_pdfs(self) -> None:
        config = load_production_config(None, project_root=self.runtime)
        ensure_production_roots(config)
        (config.incoming_dir / "b.PDF").write_bytes(b"pdf")
        (config.incoming_dir / "a.txt").write_text("ignore", encoding="utf-8")
        (config.incoming_dir / "folder.pdf").mkdir()

        self.assertEqual([path.name for path in discover_invoice_files(config)], ["b.PDF"])
        for path in (
            config.incoming_dir,
            config.production_dir,
            config.quarantine_dir,
            config.archive_dir,
            config.history_dir,
            config.diagnostics_dir,
        ):
            self.assertTrue(path.is_dir())

    def test_relative_paths_are_resolved_from_project_root(self) -> None:
        config_path = self.runtime / "production.json"
        config_path.write_text(
            json.dumps(
                {
                    "folders": {
                        "incoming": "receive",
                        "production": "runs",
                        "quarantine": "quarantine",
                        "archive": "archive",
                        "history": "history",
                        "diagnostics": "diagnostics",
                    },
                    "poll_interval_seconds": 7,
                    "stability_seconds": 3,
                }
            ),
            encoding="utf-8",
        )

        config = load_production_config(config_path, project_root=self.runtime)

        self.assertEqual(config.incoming_dir, self.runtime / "receive")
        self.assertEqual(config.history_dir, self.runtime / "history")
        self.assertEqual(config.poll_interval_seconds, 7)
        self.assertEqual(config.stability_seconds, 3)

    def test_rejects_negative_intervals(self) -> None:
        config_path = self.runtime / "production.json"
        config_path.write_text(
            json.dumps({"poll_interval_seconds": -1}), encoding="utf-8"
        )

        with self.assertRaises(ValueError):
            load_production_config(config_path, project_root=self.runtime)

    def test_run_id_is_utc_timestamp_with_collision_token(self) -> None:
        now = datetime(2026, 9, 9, 4, 15, 30, tzinfo=timezone.utc)

        self.assertEqual(create_run_id(now, "a1b2c3d4"), "20260909T041530Z-a1b2c3d4")


if __name__ == "__main__":
    unittest.main()
