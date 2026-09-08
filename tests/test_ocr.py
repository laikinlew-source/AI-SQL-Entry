from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

from ai_sql_entry.ocr import ocr_pdf


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = Path(__file__).parent / "runtime"


class PdfOcrTests(unittest.TestCase):
    def test_renders_pages_and_combines_ocr_text_in_page_order(self) -> None:
        work_dir = RUNTIME / "ocr-test"
        shutil.rmtree(work_dir, ignore_errors=True)
        try:
            result = ocr_pdf(
                FIXTURES / "minimal.pdf",
                work_dir,
                pdftoppm_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "render",
                ),
                tesseract_command=(
                    sys.executable,
                    str(FIXTURES / "fake_document_tool.py"),
                    "ocr",
                ),
            )

            self.assertEqual(
                result.text, "OCR text from page-0001\n\nOCR text from page-0002"
            )
            self.assertEqual(
                [path.name for path in result.page_paths],
                ["page-0001.png", "page-0002.png"],
            )
            self.assertTrue(all(path.exists() for path in result.page_paths))
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
