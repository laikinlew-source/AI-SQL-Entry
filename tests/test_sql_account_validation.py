from __future__ import annotations

import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_sql_entry.canonical import build_canonical
from ai_sql_entry.extraction import extract_invoice
from ai_sql_entry.sql_account_validation import (
    CurrencyRecord,
    GlAccountRecord,
    JsonSnapshotProvider,
    SqlAccountMasterData,
    SupplierRecord,
    TaxCodeRecord,
    validate_invoice,
)


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


def _canonical_invoice() -> dict[str, object]:
    invoice = extract_invoice(
        (FIXTURES / "invoice_ocr.txt").read_text(encoding="utf-8")
    )
    return build_canonical(
        invoice,
        document_id="doc-validation-test",
        source_filename="invoice.pdf",
        source_relative_path="invoices/invoice.pdf",
        source_sha256="a" * 64,
        page_count=1,
        created_at=datetime(2026, 9, 8, 1, 2, 3, tzinfo=timezone.utc),
        ocr_timestamp="2026-09-08T01:02:03Z",
        parser_version="0.3.0",
        processing_status="extraction_succeeded",
    )


class SqlAccountValidationTests(unittest.TestCase):
    def test_reports_all_mappings_found_and_ready(self) -> None:
        master_data = SqlAccountMasterData(
            suppliers=(
                SupplierRecord(
                    code="SUP-ACORN",
                    name="Acorn Office Supplies Sdn Bhd",
                    aliases=("ACORN OFFICE SUPPLIES SDN. BHD.",),
                ),
            ),
            tax_codes=(TaxCodeRecord(code="SST-OUTPUT", tax_amount="nonzero"),),
            gl_accounts=(
                GlAccountRecord(
                    code="5000-PURCHASES",
                    name="Purchases",
                    keywords=("desk", "office supplies"),
                ),
            ),
            currencies=(CurrencyRecord(code="MYR"),),
        )

        report = validate_invoice(
            _canonical_invoice(),
            master_data,
            validated_at="2026-09-08T02:00:00Z",
        )

        self.assertEqual(report["checks"]["supplier"]["status"], "found")
        self.assertEqual(report["checks"]["supplier"]["mapped_code"], "SUP-ACORN")
        self.assertEqual(report["checks"]["tax_code"]["status"], "found")
        self.assertEqual(report["checks"]["tax_code"]["mapped_code"], "SST-OUTPUT")
        self.assertEqual(report["checks"]["gl_account"]["status"], "found")
        self.assertEqual(
            report["checks"]["gl_account"]["line_items"][0]["mapped_code"],
            "5000-PURCHASES",
        )
        self.assertEqual(report["checks"]["currency"]["status"], "found")
        self.assertEqual(report["ready_for_sql_import"], "Yes")
        self.assertFalse(report["writes_performed"])

    def test_reports_each_missing_mapping_and_not_ready(self) -> None:
        report = validate_invoice(
            _canonical_invoice(),
            SqlAccountMasterData(),
            validated_at="2026-09-08T02:00:00Z",
        )

        self.assertEqual(report["checks"]["supplier"]["status"], "missing")
        self.assertEqual(report["checks"]["tax_code"]["status"], "missing")
        self.assertEqual(report["checks"]["gl_account"]["status"], "missing")
        self.assertEqual(report["checks"]["currency"]["status"], "missing")
        self.assertEqual(report["ready_for_sql_import"], "No")
        self.assertEqual(
            report["checks"]["gl_account"]["line_items"][0]["field_path"],
            "/line_items/0/description",
        )

    def test_inactive_master_records_do_not_validate(self) -> None:
        master_data = SqlAccountMasterData(
            suppliers=(
                SupplierRecord(
                    code="SUP-ACORN",
                    name="ACORN OFFICE SUPPLIES SDN BHD",
                    active=False,
                ),
            ),
            tax_codes=(
                TaxCodeRecord(code="SST-OUTPUT", tax_amount="nonzero", active=False),
            ),
            gl_accounts=(
                GlAccountRecord(
                    code="5000-PURCHASES",
                    name="Purchases",
                    keywords=("desk",),
                    active=False,
                ),
            ),
            currencies=(CurrencyRecord(code="MYR", active=False),),
        )

        report = validate_invoice(
            _canonical_invoice(),
            master_data,
            validated_at="2026-09-08T02:00:00Z",
        )

        self.assertEqual(report["ready_for_sql_import"], "No")
        self.assertTrue(
            all(check["status"] == "missing" for check in report["checks"].values())
        )

    def test_uses_a_human_supplied_effective_value_for_mapping(self) -> None:
        canonical = _canonical_invoice()
        supplier_name = canonical["parties"]["issuer"]["name"]
        supplier_name["value_status"] = "missing"
        supplier_name["extracted"]["normalized_value"] = None
        supplier_name["reviewed"]["status"] = "supplied"
        supplier_name["reviewed"]["value"] = "Reviewed Supplier Sdn Bhd"
        master_data = SqlAccountMasterData(
            suppliers=(
                SupplierRecord(
                    code="SUP-REVIEWED", name="Reviewed Supplier Sdn Bhd"
                ),
            ),
            tax_codes=(TaxCodeRecord(code="SST-6", tax_amount="nonzero"),),
            gl_accounts=(
                GlAccountRecord(code="5000", name="Purchases", default=True),
            ),
            currencies=(CurrencyRecord(code="MYR"),),
        )

        report = validate_invoice(
            canonical, master_data, validated_at="2026-09-08T02:00:00Z"
        )

        self.assertEqual(report["checks"]["supplier"]["status"], "found")
        self.assertEqual(
            report["checks"]["supplier"]["mapped_code"], "SUP-REVIEWED"
        )


class JsonSnapshotProviderTests(unittest.TestCase):
    def test_loads_all_four_editable_snapshot_files(self) -> None:
        config_dir = RUNTIME / "sql-account-snapshots"
        shutil.rmtree(config_dir, ignore_errors=True)
        config_dir.mkdir(parents=True)
        snapshots = {
            "suppliers.json": {
                "schema_version": "1.0.0",
                "suppliers": [
                    {
                        "code": "SUP-001",
                        "name": "Supplier One",
                        "aliases": ["Supplier 1"],
                        "active": True,
                    }
                ],
            },
            "tax_codes.json": {
                "schema_version": "1.0.0",
                "tax_codes": [
                    {"code": "SST0", "tax_amount": "zero", "active": True}
                ],
            },
            "gl_accounts.json": {
                "schema_version": "1.0.0",
                "gl_accounts": [
                    {
                        "code": "5000",
                        "name": "Purchases",
                        "keywords": ["steel"],
                        "default": False,
                        "active": True,
                    }
                ],
            },
            "currencies.json": {
                "schema_version": "1.0.0",
                "currencies": [{"code": "MYR", "active": True}],
            },
        }
        try:
            for filename, payload in snapshots.items():
                (config_dir / filename).write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            master_data = JsonSnapshotProvider(config_dir).load()

            self.assertEqual(master_data.suppliers[0].code, "SUP-001")
            self.assertEqual(master_data.tax_codes[0].tax_amount, "zero")
            self.assertEqual(master_data.gl_accounts[0].keywords, ("steel",))
            self.assertEqual(master_data.currencies[0].code, "MYR")
        finally:
            shutil.rmtree(config_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
