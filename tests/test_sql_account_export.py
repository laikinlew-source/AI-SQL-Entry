from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.canonical import build_canonical
from ai_sql_entry.extraction import extract_invoice
from ai_sql_entry.sql_account_export import write_import_package


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


class SqlAccountExportTests(unittest.TestCase):
    def test_writes_header_lines_and_safety_manifest(self) -> None:
        invoice = extract_invoice(
            (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        )
        canonical = build_canonical(
            invoice,
            document_id="doc-test-0001",
            source_filename="invoice.pdf",
            source_sha256="a" * 64,
            page_count=1,
            created_at=datetime(2026, 7, 21, 4, 15, 30, tzinfo=timezone.utc),
        )

        output = RUNTIME
        generated = (
            output / "sql_account_purchase_invoice_header.csv",
            output / "sql_account_purchase_invoice_lines.csv",
            output / "sql_account_import_manifest.json",
        )
        try:
            write_import_package(canonical, output)

            self.assertTrue(
                (output / "sql_account_purchase_invoice_header.csv").exists()
            )

            header = (output / "sql_account_purchase_invoice_header.csv").read_text(
                encoding="utf-8-sig"
            )
            lines = (output / "sql_account_purchase_invoice_lines.csv").read_text(
                encoding="utf-8-sig"
            )
            manifest = json.loads(
                (output / "sql_account_import_manifest.json").read_text(encoding="utf-8")
            )
        finally:
            for path in generated:
                path.unlink(missing_ok=True)

        self.assertEqual(
            header,
            "Supplier,InvoiceNumber,InvoiceDate,Currency,Subtotal,SST,TotalAmount\n"
            "ACORN OFFICE SUPPLIES SDN BHD,INV-0042,2026-07-18,MYR,100.00,6.00,106.00\n",
        )
        self.assertEqual(
            lines,
            "InvoiceNumber,LineNumber,Description,Quantity,UnitPrice,Amount\n"
            "INV-0042,1,Fictional Desk Set,2,50.00,100.00\n",
        )
        self.assertEqual(manifest["status"], "mapping_review_required")
        self.assertFalse(manifest["authorized_for_sql_account_write"])
        self.assertEqual(manifest["source_schema_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
