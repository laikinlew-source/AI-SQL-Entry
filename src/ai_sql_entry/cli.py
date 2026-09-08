from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from .batch import BatchResult, process_invoice_directory
from .pipeline import PipelineResult, process_invoice_pdf


Processor = Callable[..., PipelineResult]
BatchProcessor = Callable[..., BatchResult]


def main(
    argv: Sequence[str] | None = None,
    *,
    processor: Processor = process_invoice_pdf,
    batch_processor: BatchProcessor = process_invoice_directory,
) -> int:
    """Run the local invoice pipeline command."""
    parser = argparse.ArgumentParser(
        prog="ai-sql-entry",
        description="Convert a supplier-invoice PDF into local review artifacts.",
    )
    parser.add_argument("pdf", type=Path, nargs="?")
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument("--pdftoppm", default="pdftoppm")
    parser.add_argument("--tesseract", default="tesseract")
    arguments = parser.parse_args(argv)

    processing_options = {
        "created_at": datetime.now(timezone.utc),
        "pdftoppm_command": (arguments.pdftoppm,),
        "tesseract_command": (arguments.tesseract,),
    }
    if arguments.pdf is None:
        batch_result = batch_processor(
            Path("invoices"),
            Path("output"),
            **processing_options,
        )
        print(
            json.dumps(
                {
                    "processed": len(batch_result.processed),
                    "failed": len(batch_result.failed),
                },
                indent=2,
            )
        )
        return 0

    result = processor(
        arguments.pdf,
        arguments.output_root,
        **processing_options,
    )
    print(
        json.dumps(
            {
                "document_id": result.document_id,
                "artifact_dir": str(result.artifact_dir),
                "canonical_json": str(result.canonical_path),
            },
            indent=2,
        )
    )
    return 0
