from __future__ import annotations

import csv
import json
import shutil
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from ai_sql_entry.master_data_builder import build_snapshot


RUNTIME = Path(__file__).parent / "runtime"
NOW = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class MasterDataBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = RUNTIME / self._testMethodName
        shutil.rmtree(self.work_dir, ignore_errors=True)
        self.config_dir = self.work_dir / "config"
        self.config_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def _snapshot(self, dataset: str, records: list[dict[str, object]]) -> Path:
        path = self.config_dir / f"{dataset}.json"
        _write_json(path, {"schema_version": "1.0.0", dataset: records})
        return path

    def test_csv_supplier_import_normalizes_names_backs_up_and_replaces(self) -> None:
        snapshot_path = self._snapshot(
            "suppliers", [{"code": "OLD", "name": "Old Supplier", "active": True}]
        )
        source = self.work_dir / "suppliers.csv"
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["code", "name", "aliases", "active"])
            writer.writerow(
                ["SUP-001", "Alpha Trading Sdn. Bhd.", "Alpha Trading;Alpha", "yes"]
            )
            writer.writerow(["SUP-002", "Beta Supplies", "", "true"])

        report = build_snapshot(
            "suppliers", source, self.config_dir, timestamp=NOW
        )

        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "written")
        self.assertEqual(report["statistics"]["rows_read"], 2)
        self.assertEqual(report["statistics"]["rows_accepted"], 2)
        self.assertTrue(report["snapshot_written"])
        self.assertEqual(snapshot["suppliers"][0]["normalized_name"], "alphatradingsdnbhd")
        self.assertEqual(snapshot["suppliers"][0]["aliases"], ["Alpha Trading", "Alpha"])
        backup_path = Path(report["backup_path"])
        self.assertTrue(backup_path.is_file())
        self.assertEqual(
            json.loads(backup_path.read_text(encoding="utf-8"))["suppliers"][0]["code"],
            "OLD",
        )

    def test_duplicate_supplier_codes_and_normalized_names_block_replacement(self) -> None:
        snapshot_path = self._snapshot(
            "suppliers", [{"code": "KEEP", "name": "Keep Supplier"}]
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "suppliers.json"
        _write_json(
            source,
            [
                {"code": "SUP-001", "name": "Alpha Trading Sdn. Bhd."},
                {"code": "sup-001", "name": "Different Supplier"},
                {"code": "SUP-003", "name": "ALPHA TRADING SDN BHD"},
            ],
        )

        report = build_snapshot(
            "suppliers", source, self.config_dir, timestamp=NOW
        )

        self.assertEqual(report["status"], "invalid")
        self.assertFalse(report["snapshot_written"])
        self.assertEqual(snapshot_path.read_bytes(), original)
        self.assertEqual(report["duplicates"]["supplier_codes"], ["SUP-001"])
        self.assertEqual(
            report["duplicates"]["supplier_names"], ["alphatradingsdnbhd"]
        )
        self.assertIsNone(report["backup_path"])

    def test_retention_floor_blocks_significantly_smaller_replacement(self) -> None:
        existing = [
            {"code": f"SUP-{index:03d}", "name": f"Supplier {index}"}
            for index in range(10)
        ]
        snapshot_path = self._snapshot("suppliers", existing)
        original = snapshot_path.read_bytes()
        source = self.work_dir / "suppliers.json"
        _write_json(
            source,
            [
                {"code": f"NEW-{index:03d}", "name": f"New Supplier {index}"}
                for index in range(4)
            ],
        )

        report = build_snapshot(
            "suppliers",
            source,
            self.config_dir,
            minimum_retention_ratio=Decimal("0.50"),
            timestamp=NOW,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["statistics"]["existing_rows"], 10)
        self.assertEqual(report["statistics"]["retention_ratio"], "0.4000")
        self.assertIn("retention", report["warnings"][0].casefold())
        self.assertFalse(report["snapshot_written"])
        self.assertEqual(snapshot_path.read_bytes(), original)
        self.assertIsNone(report["backup_path"])

    def test_dry_run_validates_without_snapshot_or_backup_write(self) -> None:
        snapshot_path = self._snapshot(
            "currencies", [{"code": "MYR", "active": True}]
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "currencies.json"
        _write_json(source, [{"code": "USD", "active": True}])

        report = build_snapshot(
            "currencies", source, self.config_dir, dry_run=True, timestamp=NOW
        )

        self.assertEqual(report["status"], "valid")
        self.assertTrue(report["would_replace_snapshot"])
        self.assertFalse(report["snapshot_written"])
        self.assertIsNone(report["backup_path"])
        self.assertEqual(snapshot_path.read_bytes(), original)
        self.assertFalse((self.config_dir / "backups").exists())

    def test_excel_tax_code_import_reads_first_worksheet(self) -> None:
        self._snapshot("tax_codes", [])
        source = self.work_dir / "tax_codes.xlsx"
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["code", "tax_amount", "active"])
        worksheet.append(["SST0", "zero", True])
        worksheet.append(["SST", "nonzero", True])
        workbook.save(source)
        workbook.close()

        report = build_snapshot(
            "tax_codes", source, self.config_dir, timestamp=NOW
        )

        snapshot = json.loads(
            (self.config_dir / "tax_codes.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["source_format"], "excel")
        self.assertEqual(report["statistics"]["rows_accepted"], 2)
        self.assertEqual(
            [record["tax_amount"] for record in snapshot["tax_codes"]],
            ["zero", "nonzero"],
        )

    def test_invalid_required_value_is_reported_without_replacement(self) -> None:
        snapshot_path = self._snapshot(
            "gl_accounts", [{"code": "5000", "name": "Purchases"}]
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "gl_accounts.csv"
        source.write_text(
            "code,name,keywords,default,active\n,Missing Code,steel,false,true\n",
            encoding="utf-8",
        )

        report = build_snapshot(
            "gl_accounts", source, self.config_dir, timestamp=NOW
        )

        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["statistics"]["rows_rejected"], 1)
        self.assertEqual(report["errors"][0]["row"], 2)
        self.assertIn("code", report["errors"][0]["message"])
        self.assertEqual(snapshot_path.read_bytes(), original)

    def test_malformed_json_is_reported_without_replacement(self) -> None:
        snapshot_path = self._snapshot(
            "currencies", [{"code": "MYR", "active": True}]
        )
        original = snapshot_path.read_bytes()
        source = self.work_dir / "currencies.json"
        _write_json(source, {"wrong_key": []})

        report = build_snapshot(
            "currencies", source, self.config_dir, timestamp=NOW
        )

        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["source_format"], "json")
        self.assertEqual(report["statistics"]["rows_read"], 0)
        self.assertIn("record list", report["errors"][0]["message"])
        self.assertFalse(report["snapshot_written"])
        self.assertEqual(snapshot_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
