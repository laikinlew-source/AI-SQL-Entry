from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ai_sql_entry.extraction import ExtractionError, extract_invoice


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


class ExtractInvoiceTests(unittest.TestCase):
    def test_extracts_required_invoice_fields_and_line_items(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")

        invoice = extract_invoice(text)

        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.supplier, "ACORN OFFICE SUPPLIES SDN BHD")
        self.assertEqual(invoice.invoice_number, "INV-0042")
        self.assertEqual(invoice.invoice_date.isoformat(), "2026-07-18")
        self.assertEqual(invoice.currency, "MYR")
        self.assertEqual(invoice.subtotal, Decimal("100.00"))
        self.assertEqual(invoice.sst, Decimal("6.00"))
        self.assertEqual(invoice.total_amount, Decimal("106.00"))
        self.assertEqual(len(invoice.line_items), 1)
        self.assertEqual(invoice.line_items[0].description, "Fictional Desk Set")
        self.assertEqual(invoice.line_items[0].quantity, Decimal("2"))
        self.assertEqual(invoice.line_items[0].unit_price, Decimal("50.00"))
        self.assertEqual(invoice.line_items[0].amount, Decimal("100.00"))

    def test_rejects_invoice_without_line_items(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace("Fictional Desk Set | 2 | 50.00 | 100.00", "")

        with self.assertRaisesRegex(ValueError, "line item"):
            extract_invoice(text)

    def test_rejects_total_that_does_not_equal_subtotal_plus_sst(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace("Total Amount: 106.00", "Total Amount: 999.00")

        with self.assertRaisesRegex(ValueError, "total"):
            extract_invoice(text)

    def test_extracts_line_item_with_ocr_whitespace_columns(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace(
            "Fictional Desk Set | 2 | 50.00 | 100.00",
            "Fictional Desk Set    2    50.00    100.00",
        )

        invoice = extract_invoice(text)

        self.assertEqual(invoice.line_items[0].description, "Fictional Desk Set")
        self.assertEqual(invoice.line_items[0].quantity, Decimal("2"))

    def test_extracts_line_item_when_ocr_collapses_columns_to_single_spaces(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace(
            "Fictional Desk Set | 2 | 50.00 | 100.00",
            "Fictional Desk Set 2 50.00 100.00",
        )

        invoice = extract_invoice(text)

        self.assertEqual(invoice.line_items[0].description, "Fictional Desk Set")
        self.assertEqual(invoice.line_items[0].quantity, Decimal("2"))
        self.assertEqual(invoice.line_items[0].unit_price, Decimal("50.00"))
        self.assertEqual(invoice.line_items[0].amount, Decimal("100.00"))

    def test_supports_common_configured_field_aliases(self) -> None:
        base = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        cases = {
            "invoice_number": (
                "Invoice No",
                [
                    "Invoice Number",
                    "Inv No",
                    "Inv #",
                    "Invoice #",
                    "Doc No",
                    "Document No",
                    "Reference No",
                    "Ref No",
                    "e-Invoice Number",
                    "eInvoice Number",
                    "e Invoice Number",
                ],
            ),
            "invoice_date": (
                "Invoice Date",
                ["Date", "Document Date", "Tax Date", "e-Invoice Date"],
            ),
            "supplier": (
                "ACORN OFFICE SUPPLIES SDN BHD",
                ["Supplier", "Vendor", "Seller", "Company"],
            ),
            "subtotal": (
                "Subtotal",
                ["Before Tax", "Amount Before SST"],
            ),
            "sst": (
                "SST 6%",
                ["Service Tax", "Sales Tax", "Tax Amount"],
            ),
            "total": (
                "Total Amount",
                ["Total", "Grand Total", "Amount Due", "Net Total"],
            ),
        }

        for field, (original, aliases) in cases.items():
            for alias in aliases:
                with self.subTest(field=field, alias=alias):
                    if field == "supplier":
                        text = base.replace(original, f"{alias}: {original}", 1)
                    else:
                        text = base.replace(original, alias, 1)
                    invoice = extract_invoice(text)
                    self.assertEqual(invoice.invoice_number, "INV-0042")
                    self.assertEqual(invoice.invoice_date.isoformat(), "2026-07-18")
                    self.assertEqual(invoice.supplier, "ACORN OFFICE SUPPLIES SDN BHD")
                    self.assertEqual(invoice.subtotal, Decimal("100.00"))
                    self.assertEqual(invoice.sst, Decimal("6.00"))
                    self.assertEqual(invoice.total_amount, Decimal("106.00"))

    def test_alias_matching_ignores_case_spaces_hyphens_and_underscores(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace("Invoice No", "E_iNvOiCe-NuMbEr")

        invoice = extract_invoice(text)

        self.assertEqual(invoice.invoice_number, "INV-0042")

    def test_loads_new_alias_from_an_editable_json_file(self) -> None:
        aliases = {
            "supplier": ["Supplier"],
            "invoice_number": ["Billing Reference"],
            "invoice_date": ["Invoice Date"],
            "currency": ["Currency"],
            "subtotal": ["Subtotal"],
            "sst": ["SST"],
            "total": ["Total Amount"],
        }
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace("Invoice No", "Billing Reference")

        with tempfile.TemporaryDirectory(dir=RUNTIME) as directory:
            config_path = Path(directory) / "aliases.json"
            config_path.write_text(json.dumps(aliases), encoding="utf-8")
            invoice = extract_invoice(text, alias_config_path=config_path)

        self.assertEqual(invoice.invoice_number, "INV-0042")

    def test_reports_every_missing_required_field_without_placeholder_values(self) -> None:
        text = (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        text = text.replace("Invoice No: INV-0042", "")
        text = text.replace("SST 6%: 6.00", "")
        text = text.replace("Fictional Desk Set | 2 | 50.00 | 100.00", "")

        with self.assertRaises(ExtractionError) as raised:
            extract_invoice(text)

        self.assertEqual(
            raised.exception.missing_fields,
            ("invoice_number", "sst", "line_items"),
        )


if __name__ == "__main__":
    unittest.main()
