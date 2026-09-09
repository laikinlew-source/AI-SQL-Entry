from __future__ import annotations

import csv
import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.canonical import build_canonical
from ai_sql_entry.extraction import extract_invoice
from ai_sql_entry.master_data_acquisition import run_master_data_acquisition


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime" / "master-data-acquisition"


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def _canonical_invoice() -> dict[str, object]:
    invoice = extract_invoice(
        (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
    )
    return build_canonical(
        invoice,
        document_id="doc-readiness-0001",
        source_filename="invoice.pdf",
        source_relative_path="invoices/invoice.pdf",
        source_sha256="a" * 64,
        page_count=1,
        created_at=datetime(2026, 9, 9, 1, 2, 3, tzinfo=timezone.utc),
        ocr_timestamp="2026-09-09T01:02:03Z",
        parser_version="0.3.0",
        processing_status="extraction_succeeded",
    )


class MasterDataAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(RUNTIME, ignore_errors=True)
        (RUNTIME / "incoming" / "master-data").mkdir(parents=True)
        (RUNTIME / "config").mkdir()
        (RUNTIME / "output" / "processing" / "doc-readiness-0001").mkdir(
            parents=True
        )

    def tearDown(self) -> None:
        shutil.rmtree(RUNTIME, ignore_errors=True)

    def _write_exports(self) -> None:
        incoming = RUNTIME / "incoming" / "master-data"
        _write_csv(
            incoming / "Supplier Export.csv",
            ["Code", "CompanyName", "Active"],
            [["SUP-ACORN", "Acorn Office Supplies Sdn Bhd", "Yes"]],
        )
        _write_csv(
            incoming / "Tax Codes.csv",
            ["Code", "TaxRate", "Active"],
            [["SST-6", "6", "Yes"]],
        )
        _write_csv(
            incoming / "GL Account Export.csv",
            ["Code", "Description", "Default", "Active"],
            [["5000-PURCHASES", "Purchases", "Yes", "Yes"]],
        )
        _write_csv(
            incoming / "Currency Export.csv",
            ["CurrencyCode", "Active"],
            [["MYR", "Yes"]],
        )

    def test_detects_exports_builds_all_snapshots_and_revalidates_invoices(self) -> None:
        self._write_exports()
        (RUNTIME / "output" / "processing" / "doc-readiness-0001" / "canonical.json").write_text(
            json.dumps(_canonical_invoice()), encoding="utf-8"
        )

        result = run_master_data_acquisition(
            RUNTIME / "incoming" / "master-data",
            RUNTIME / "config",
            RUNTIME / "output",
            generated_at=datetime(2026, 9, 9, 2, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "written")
        self.assertEqual(result["snapshots"]["written"], 4)
        self.assertEqual(result["invoice_readiness"]["total_invoices"], 1)
        self.assertEqual(result["invoice_readiness"]["not_ready"], 1)
        self.assertEqual(result["invoice_readiness"]["missing_supplier"], 0)
        self.assertEqual(result["invoice_readiness"]["missing_tax_code"], 0)
        self.assertEqual(result["invoice_readiness"]["missing_gl_account"], 0)
        self.assertEqual(result["invoice_readiness"]["missing_currency"], 0)
        self.assertTrue(result["report_paths"]["json"].is_file())
        self.assertTrue(result["report_paths"]["markdown"].is_file())
        self.assertTrue(result["report_paths"]["dashboard"].is_file())
        self.assertEqual(
            len(list((RUNTIME / "output" / "master-data-readiness" / "history").iterdir())),
            1,
        )
        self.assertEqual(
            json.loads((RUNTIME / "config" / "suppliers.json").read_text())["suppliers"][0][
                "code"
            ],
            "SUP-ACORN",
        )

    def test_invalid_export_blocks_every_snapshot_replacement(self) -> None:
        self._write_exports()
        (RUNTIME / "incoming" / "master-data" / "Tax Codes.csv").write_text(
            "Code,Unrelated\nSST-6,unknown\n", encoding="utf-8"
        )
        old_payload = {"schema_version": "1.0.0", "suppliers": [{"code": "OLD"}]}
        (RUNTIME / "config" / "suppliers.json").write_text(
            json.dumps(old_payload), encoding="utf-8"
        )

        result = run_master_data_acquisition(
            RUNTIME / "incoming" / "master-data",
            RUNTIME / "config",
            RUNTIME / "output",
            generated_at=datetime(2026, 9, 9, 2, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["snapshots"]["written"], 0)
        self.assertEqual(
            json.loads((RUNTIME / "config" / "suppliers.json").read_text())["suppliers"][0][
                "code"
            ],
            "OLD",
        )
        self.assertTrue(result["discovery"]["errors"]["tax_codes"])

    def test_each_run_uses_a_new_history_directory(self) -> None:
        self._write_exports()
        for hour in (2, 3):
            result = run_master_data_acquisition(
                RUNTIME / "incoming" / "master-data",
                RUNTIME / "config",
                RUNTIME / "output",
                generated_at=datetime(2026, 9, 9, hour, 0, 0, tzinfo=timezone.utc),
            )
            self.assertTrue(result["report_paths"]["json"].is_file())

        history = list((RUNTIME / "output" / "master-data-readiness" / "history").iterdir())
        self.assertEqual(len(history), 2)
        self.assertNotEqual(history[0].name, history[1].name)

    def test_revalidates_canonical_files_under_project_lifecycle_roots(self) -> None:
        self._write_exports()
        lifecycle_path = RUNTIME / "completed" / "doc-readiness-0001"
        lifecycle_path.mkdir(parents=True)
        lifecycle_path.joinpath("canonical.json").write_text(
            json.dumps(_canonical_invoice()), encoding="utf-8"
        )

        result = run_master_data_acquisition(
            RUNTIME / "incoming" / "master-data",
            RUNTIME / "config",
            RUNTIME / "output",
            invoice_root=RUNTIME,
            generated_at=datetime(2026, 9, 9, 2, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["invoice_readiness"]["total_invoices"], 1)

    def test_revalidates_existing_invoices_when_export_acquisition_is_blocked(self) -> None:
        (RUNTIME / "output" / "processing" / "doc-readiness-0001" / "canonical.json").write_text(
            json.dumps(_canonical_invoice()), encoding="utf-8"
        )

        result = run_master_data_acquisition(
            RUNTIME / "incoming" / "master-data",
            RUNTIME / "config",
            RUNTIME / "output",
            generated_at=datetime(2026, 9, 9, 2, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["invoice_readiness"]["total_invoices"], 1)
        self.assertEqual(result["invoice_readiness"]["not_ready"], 1)


if __name__ == "__main__":
    unittest.main()
