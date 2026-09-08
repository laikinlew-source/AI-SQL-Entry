from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.canonical import build_canonical
from ai_sql_entry.extraction import extract_invoice


FIXTURES = Path(__file__).parent / "fixtures"


class CanonicalJsonTests(unittest.TestCase):
    def test_builds_awaiting_review_payload_with_documented_field_envelopes(self) -> None:
        invoice = extract_invoice(
            (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
        )

        payload = build_canonical(
            invoice,
            document_id="doc-test-0001",
            source_filename="invoice.pdf",
            source_relative_path="invoices/invoice.pdf",
            source_sha256="a" * 64,
            page_count=1,
            created_at=datetime(2026, 7, 21, 4, 15, 30, tzinfo=timezone.utc),
            ocr_timestamp="2026-07-21T04:15:31Z",
            parser_version="0.2.0",
            processing_status="extraction_succeeded",
        )

        self.assertIn("schema_version", payload)
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertEqual(payload["document_id"], "doc-test-0001")
        self.assertEqual(payload["lifecycle_status"], "awaiting_review")
        self.assertEqual(payload["source"]["sha256"], "a" * 64)
        self.assertEqual(payload["source"]["source_relative_path"], "invoices/invoice.pdf")
        self.assertEqual(payload["processing"]["ocr_timestamp"], "2026-07-21T04:15:31Z")
        self.assertEqual(payload["processing"]["parser_version"], "0.2.0")
        self.assertEqual(payload["processing"]["processing_status"], "extraction_succeeded")
        self.assertEqual(
            payload["parties"]["issuer"]["name"]["extracted"]["normalized_value"],
            "ACORN OFFICE SUPPLIES SDN BHD",
        )
        self.assertEqual(
            payload["document_details"]["document_number"]["extracted"]["normalized_value"],
            "INV-0042",
        )
        self.assertEqual(
            payload["financial_summary"]["grand_total"]["extracted"]["normalized_value"],
            {"value": "106.00", "currency": "MYR"},
        )
        self.assertEqual(payload["line_items"][0]["line_item_id"], "line-0001")
        self.assertEqual(
            payload["line_items"][0]["quantity"]["extracted"]["normalized_value"],
            "2",
        )
        self.assertNotIn("effective_value", str(payload))
        self.assertEqual(payload["review"]["status"], "not_started")
        self.assertIsNone(payload["error"])


if __name__ == "__main__":
    unittest.main()
