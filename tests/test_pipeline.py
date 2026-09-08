from __future__ import annotations

import json
import shutil
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.pipeline import process_invoice_pdf


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


class InvoicePipelineTests(unittest.TestCase):
    def test_processes_pdf_into_canonical_json_and_import_preparation_data(self) -> None:
        output_root = RUNTIME / "pipeline-test"
        shutil.rmtree(output_root, ignore_errors=True)
        try:
            result = process_invoice_pdf(
                FIXTURES / "minimal.pdf",
                output_root,
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
                source_relative_path="invoices/minimal.pdf",
            )

            self.assertEqual(result.document_id, "doc-e53302bb9d4b")

            canonical = json.loads(result.canonical_path.read_text(encoding="utf-8"))
            copied_original = result.artifact_dir / "original" / "minimal.pdf"

            self.assertEqual(
                copied_original.read_bytes(), (FIXTURES / "minimal.pdf").read_bytes()
            )
            self.assertEqual(
                canonical["source"]["sha256"],
                "e53302bb9d4bb3a69bb58c198ad333944137ee5656f57e7281204b6409f078a3",
            )
            self.assertEqual(canonical["source"]["page_count"], 2)
            self.assertEqual(
                canonical["source"]["source_relative_path"], "invoices/minimal.pdf"
            )
            self.assertEqual(
                canonical["processing"]["ocr_timestamp"], "2026-07-21T04:15:30Z"
            )
            self.assertEqual(canonical["processing"]["parser_version"], "0.3.0")
            self.assertEqual(
                canonical["processing"]["processing_status"], "extraction_succeeded"
            )
            self.assertEqual(
                canonical["document_details"]["document_number"]["extracted"][
                    "normalized_value"
                ],
                "INV-0042",
            )
            self.assertTrue(
                (
                    result.artifact_dir
                    / "extraction"
                    / "extract-doc-e53302bb9d4b"
                    / "ocr.txt"
                ).is_file()
            )
            self.assertTrue(
                (
                    result.artifact_dir
                    / "sql_account_import"
                    / "sql_account_purchase_invoice_header.csv"
                ).is_file()
            )
            report = json.loads(result.extraction_report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                result.extraction_report_path,
                result.artifact_dir / "extraction_report.json",
            )
            self.assertEqual(report["source_pdf_filename"], "minimal.pdf")
            self.assertEqual(report["source_relative_path"], "invoices/minimal.pdf")
            self.assertEqual(report["processing_status"], "extraction_succeeded")
            self.assertEqual(report["missing_fields"], [])
            self.assertEqual(report["fields"]["line_items"]["count"], 1)
            self.assertEqual(list(result.artifact_dir.glob("canonical.*.tmp")), [])
        finally:
            shutil.rmtree(output_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
