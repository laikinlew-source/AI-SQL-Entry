from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ai_sql_entry.batch import BatchResult
from ai_sql_entry.cli import main
from ai_sql_entry.pipeline import PipelineResult


class CliTests(unittest.TestCase):
    def test_reports_generated_canonical_path(self) -> None:
        observed: dict[str, object] = {}

        def processor(pdf_path: Path, output_root: Path, **options: object) -> PipelineResult:
            observed.update(pdf_path=pdf_path, output_root=output_root, **options)
            artifact_dir = output_root / "processing" / "doc-test"
            return PipelineResult(
                document_id="doc-test",
                artifact_dir=artifact_dir,
                canonical_path=artifact_dir / "canonical.json",
                extraction_report_path=artifact_dir / "extraction_report.json",
                sql_validation_report_path=(
                    artifact_dir / "sql_account_validation_report.json"
                ),
            )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                ["invoices/invoice.pdf", "--output-root", "artifacts"], processor=processor
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed["pdf_path"], Path("invoices/invoice.pdf"))
        self.assertEqual(observed["output_root"], Path("artifacts"))
        self.assertEqual(observed["source_relative_path"], "invoices/invoice.pdf")
        self.assertIn("doc-test", stdout.getvalue())
        self.assertIn("canonical.json", stdout.getvalue())
        self.assertIn("extraction_report.json", stdout.getvalue())
        self.assertIn("sql_account_validation_report.json", stdout.getvalue())

    def test_rejects_single_pdf_outside_project_invoices_directory(self) -> None:
        def processor(*args: object, **kwargs: object) -> PipelineResult:
            self.fail("PDF outside invoices/ must not reach the production processor")

        with self.assertRaises(SystemExit) as raised:
            main(["samples/invoice.pdf"], processor=processor)

        self.assertEqual(raised.exception.code, 2)

    def test_defaults_to_processing_invoices_directory_into_output(self) -> None:
        observed: dict[str, object] = {}

        def batch_processor(
            invoices_dir: Path, output_dir: Path, **options: object
        ) -> BatchResult:
            observed.update(
                invoices_dir=invoices_dir, output_dir=output_dir, **options
            )
            return BatchResult(processed=(), failed=())

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            try:
                exit_code = main([], batch_processor=batch_processor)
            except (SystemExit, TypeError) as error:
                self.fail(f"CLI rejected folder-processing mode: {error}")

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed["invoices_dir"], Path("invoices"))
        self.assertEqual(observed["output_dir"], Path("output"))
        self.assertIn('"processed": 0', stdout.getvalue())
        self.assertIn('"failed": 0', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
