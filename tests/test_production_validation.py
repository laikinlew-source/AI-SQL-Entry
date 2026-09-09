from __future__ import annotations

import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.production_validation import (
    atomic_write_json,
    build_audit,
    create_run_id,
    discover_invoice_files,
    ensure_production_roots,
    find_duplicate,
    load_resume_index,
    load_production_config,
    record_resume_entry,
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


def _canonical_for_history(
    *,
    document_id: str = "doc-new",
    sha256: str = "a" * 64,
    supplier: str = "Acorn Supplies Sdn Bhd",
    invoice_number: str = "INV-1",
    invoice_date: str = "2026-09-09",
    total: str = "106.00",
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "source": {
            "original_filename": "invoice.pdf",
            "source_relative_path": "incoming/invoice.pdf",
            "sha256": sha256,
        },
        "processing": {
            "ocr_timestamp": "2026-09-09T04:15:30Z",
            "parser_version": "0.3.0",
            "processing_status": "extraction_succeeded",
        },
        "parties": {"issuer": {"name": {"extracted": {"normalized_value": supplier}}}},
        "document_details": {
            "document_number": {"extracted": {"normalized_value": invoice_number}},
            "issue_date": {"extracted": {"normalized_value": invoice_date}},
        },
        "financial_summary": {
            "grand_total": {
                "extracted": {"normalized_value": {"value": total, "currency": "MYR"}}
            }
        },
    }


class ProductionHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path(__file__).parent / "runtime" / "production-history"
        shutil.rmtree(self.runtime, ignore_errors=True)
        self.runtime.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_atomic_resume_index_round_trip_and_replaces_same_hash(self) -> None:
        config = load_production_config(None, project_root=self.runtime)
        ensure_production_roots(config)
        first = {"source_sha256": "a" * 64, "state": "REVIEW", "run_id": "run-1"}
        second = {"source_sha256": "a" * 64, "state": "READY", "run_id": "run-2"}

        atomic_write_json(config.history_dir / "custom.json", {"ok": True})
        record_resume_entry(config, first)
        record_resume_entry(config, second)

        self.assertEqual(json.loads((config.history_dir / "custom.json").read_text())["ok"], True)
        self.assertEqual(load_resume_index(config)["entries"], [second])

    def test_duplicate_report_lists_every_matching_key(self) -> None:
        canonical = _canonical_for_history()
        index = {
            "entries": [
                {
                    "source_sha256": "a" * 64,
                    "supplier": "Acorn Supplies Sdn Bhd",
                    "invoice_number": "INV-1",
                    "invoice_date": "2026-09-09",
                    "total_amount": "106.00",
                    "document_id": "doc-old",
                    "run_id": "prior-run",
                }
            ]
        }

        duplicate = find_duplicate(canonical, index)

        self.assertIsNotNone(duplicate)
        self.assertEqual(
            duplicate["matching_keys"],
            ["sha256", "invoice_number", "supplier", "invoice_date", "total_amount"],
        )
        self.assertEqual(duplicate["prior_document_id"], "doc-old")

    def test_missing_business_keys_do_not_match(self) -> None:
        canonical = _canonical_for_history(invoice_number="")
        index = {
            "entries": [
                {
                    "source_sha256": "b" * 64,
                    "supplier": "Acorn Supplies",
                    "invoice_number": "",
                    "invoice_date": "2026-09-09",
                    "total_amount": "106.00",
                }
            ]
        }

        self.assertIsNone(find_duplicate(canonical, index))

    def test_audit_contains_versions_and_source_provenance(self) -> None:
        config = load_production_config(None, project_root=self.runtime)
        audit = build_audit(
            _canonical_for_history(),
            config,
            "20260909T041530Z-run1",
            "2026-09-09T04:15:30Z",
        )

        self.assertEqual(audit["source_pdf_filename"], "invoice.pdf")
        self.assertEqual(audit["source_sha256"], "a" * 64)
        self.assertEqual(audit["parser_version"], "0.3.0")
        self.assertEqual(audit["snapshot_version"], "1.0.0")
        self.assertEqual(audit["validation_version"], "1.0.0")
        self.assertEqual(audit["import_package_version"], "1.0.0")
        self.assertEqual(audit["review_status"], "not_reviewed")


if __name__ == "__main__":
    unittest.main()
