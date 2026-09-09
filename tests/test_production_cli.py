from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from ai_sql_entry.production_cli import main


class ProductionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path(__file__).parent / "runtime" / "production-cli"
        shutil.rmtree(self.runtime, ignore_errors=True)
        self.runtime.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_once_invokes_runner_with_configured_project_root(self) -> None:
        config_path = self.runtime / "production.json"
        config_path.write_text(json.dumps({"stability_seconds": 0}), encoding="utf-8")
        calls: list[Path] = []

        def runner(config, *, now):
            calls.append(config.project_root)
            return {
                "run_id": "20260909T041530Z-test",
                "counts": {"READY": 0, "FAILED": 0, "REVIEW": 0, "DUPLICATE": 0},
                "metrics": {},
                "outcomes": [],
            }

        result = main(
            ["--config", str(config_path), "--project-root", str(self.runtime), "--once"],
            runner=runner,
        )

        self.assertEqual(result, 0)
        self.assertEqual(calls, [self.runtime.resolve()])

    def test_rejects_once_and_watch_together(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--once", "--watch"], runner=lambda **_: {})

    def test_uses_project_default_config_when_config_is_not_supplied(self) -> None:
        config_dir = self.runtime / "config"
        config_dir.mkdir()
        (config_dir / "production_validation.json").write_text(
            json.dumps({"folders": {"incoming": "configured-incoming"}}),
            encoding="utf-8",
        )
        incoming_paths: list[Path] = []

        def runner(config, *, now):
            incoming_paths.append(config.incoming_dir)
            return {
                "run_id": "20260909T041530Z-default",
                "counts": {"READY": 0, "FAILED": 0, "REVIEW": 0, "DUPLICATE": 0},
                "metrics": {},
                "outcomes": [],
            }

        self.assertEqual(
            main(
                ["--project-root", str(self.runtime), "--once"],
                runner=runner,
            ),
            0,
        )
        self.assertEqual(incoming_paths, [self.runtime / "configured-incoming"])


class ProductionDocumentationTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).parents[1]

    def test_production_documentation_contains_required_operating_contract(self) -> None:
        paths = [
            self.PROJECT_ROOT / "README.md",
            self.PROJECT_ROOT / "docs" / "001-Project-Vision.md",
            self.PROJECT_ROOT / "docs" / "002-System-Architecture.md",
            self.PROJECT_ROOT / "docs" / "003-Development-Workflow.md",
            self.PROJECT_ROOT / "docs" / "010-Production-Validation-Guide.md",
            self.PROJECT_ROOT / "docs" / "roadmap.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())

        for term in (
            "incoming/",
            "production/",
            "quarantine/",
            "archive/",
            "READY",
            "FAILED",
            "REVIEW",
            "DUPLICATE",
            "resume",
            "SHA-256",
            "production_dashboard.md",
            "never writes to SQL Account",
        ):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
