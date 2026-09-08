from __future__ import annotations

import shutil
import sys
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.batch import process_invoice_directory


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


class InvoiceBatchTests(unittest.TestCase):
    def test_processes_every_pdf_from_invoices_directory_into_output(self) -> None:
        work_dir = RUNTIME / "batch-test"
        invoices_dir = work_dir / "invoices"
        output_dir = work_dir / "output"
        shutil.rmtree(work_dir, ignore_errors=True)
        invoices_dir.mkdir(parents=True)
        (invoices_dir / "first.pdf").write_bytes(
            (FIXTURES / "minimal.pdf").read_bytes()
        )
        (invoices_dir / "SECOND.PDF").write_bytes(
            (FIXTURES / "minimal.pdf").read_bytes() + b"\n% second"
        )
        (invoices_dir / "ignore.txt").write_text("not a PDF", encoding="utf-8")
        (invoices_dir / "not-a-file.pdf").mkdir()
        try:
            result = process_invoice_directory(
                invoices_dir,
                output_dir,
                created_at=datetime(2026, 7, 21, 4, 15, 30, tzinfo=timezone.utc),
                pdftoppm_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "render",
                ),
                tesseract_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "invoice_ocr",
                ),
            )

            self.assertEqual(len(result.processed), 2)
            self.assertEqual(result.failed, ())
            for processed in result.processed:
                self.assertTrue(processed.canonical_path.is_file())
                self.assertTrue(
                    (
                        processed.artifact_dir
                        / "sql_account_import"
                        / "sql_account_purchase_invoice_header.csv"
                    ).is_file()
                )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_records_a_safe_error_and_continues_after_a_failed_pdf(self) -> None:
        work_dir = RUNTIME / "batch-failure-test"
        invoices_dir = work_dir / "invoices"
        output_dir = work_dir / "output"
        shutil.rmtree(work_dir, ignore_errors=True)
        invoices_dir.mkdir(parents=True)
        (invoices_dir / "broken.pdf").write_bytes(b"%PDF broken")
        try:
            result = process_invoice_directory(
                invoices_dir,
                output_dir,
                created_at=datetime(2026, 7, 21, 4, 15, 30, tzinfo=timezone.utc),
                pdftoppm_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "render",
                ),
                tesseract_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "invoice_ocr",
                ),
            )

            error_path = output_dir / "error" / "broken.json"
            self.assertTrue(error_path.is_file())
            error = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual(len(result.processed), 0)
            self.assertEqual(result.failed[0].error_path, error_path)
            self.assertEqual(error["source_filename"], "broken.pdf")
            self.assertEqual(error["source_relative_path"], "invoices/broken.pdf")
            self.assertIn("ocr_timestamp", error)
            self.assertEqual(error["parser_version"], "0.3.0")
            self.assertEqual(error["processing_status"], "extraction_failed")
            self.assertEqual(error["missing_fields"], [])
            self.assertEqual(error["category"], "processing_failure")
            self.assertNotIn("stderr", error)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_error_report_lists_all_unextracted_required_fields(self) -> None:
        work_dir = RUNTIME / "batch-incomplete-test"
        invoices_dir = work_dir / "invoices"
        output_dir = work_dir / "output"
        shutil.rmtree(work_dir, ignore_errors=True)
        invoices_dir.mkdir(parents=True)
        (invoices_dir / "incomplete.pdf").write_bytes(
            (FIXTURES / "minimal.pdf").read_bytes()
        )
        try:
            result = process_invoice_directory(
                invoices_dir,
                output_dir,
                created_at=datetime(2026, 7, 21, 4, 15, 30, tzinfo=timezone.utc),
                pdftoppm_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "render",
                ),
                tesseract_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "incomplete_invoice_ocr",
                ),
            )

            error = json.loads(result.failed[0].error_path.read_text(encoding="utf-8"))
            self.assertEqual(
                error["missing_fields"], ["invoice_number", "sst", "line_items"]
            )
            self.assertIn("invoice_number", error["message"])
            self.assertIn("sst", error["message"])
            self.assertIn("line_items", error["message"])
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
