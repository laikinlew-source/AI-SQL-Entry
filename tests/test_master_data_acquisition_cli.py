from __future__ import annotations

import csv
import io
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ai_sql_entry.master_data_acquisition_cli import main


RUNTIME = Path(__file__).parent / "runtime" / "master-data-acquisition-cli"


def _csv(path: Path, headers: list[str], row: list[object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerow(row)


class MasterDataAcquisitionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(RUNTIME, ignore_errors=True)
        incoming = RUNTIME / "incoming" / "master-data"
        incoming.mkdir(parents=True)
        (RUNTIME / "config").mkdir()
        _csv(incoming / "Supplier Export.csv", ["Code", "CompanyName"], ["S1", "Supplier One"])
        _csv(incoming / "Tax Codes.csv", ["Code", "TaxRate"], ["T0", "0"])
        _csv(incoming / "GL Account Export.csv", ["Code", "Description", "Default"], ["G1", "Purchases", "Yes"])
        _csv(incoming / "Currency Export.csv", ["CurrencyCode"], ["MYR"])

    def tearDown(self) -> None:
        shutil.rmtree(RUNTIME, ignore_errors=True)

    def test_runs_acquisition_and_prints_report_paths(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "--incoming-dir",
                    str(RUNTIME / "incoming" / "master-data"),
                    "--config-dir",
                    str(RUNTIME / "config"),
                    "--output-root",
                    str(RUNTIME / "output"),
                    "--generated-at",
                    "2026-09-09T04:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("readiness_report.json", output.getvalue())
        self.assertTrue(
            list((RUNTIME / "output" / "master-data-readiness" / "history").rglob("readiness_report.json"))
        )


if __name__ == "__main__":
    unittest.main()
