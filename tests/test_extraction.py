from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from ai_sql_entry.extraction import extract_invoice


FIXTURES = Path(__file__).parent / "fixtures"


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


if __name__ == "__main__":
    unittest.main()
