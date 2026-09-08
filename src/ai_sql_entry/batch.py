from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .pipeline import PipelineResult, process_invoice_pdf


@dataclass(frozen=True)
class BatchResult:
    processed: tuple[PipelineResult, ...]
    failed: tuple[BatchFailure, ...]


@dataclass(frozen=True)
class BatchFailure:
    source_path: Path
    error_path: Path


def process_invoice_directory(
    invoices_dir: Path,
    output_dir: Path,
    *,
    created_at: datetime,
    pdftoppm_command: tuple[str, ...] = ("pdftoppm",),
    tesseract_command: tuple[str, ...] = ("tesseract",),
) -> BatchResult:
    """Process every PDF in an invoice intake directory."""
    if not invoices_dir.is_dir():
        raise FileNotFoundError(f"Invoice directory does not exist: {invoices_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = sorted(
        (path for path in invoices_dir.iterdir() if path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    processed = []
    failed = []
    for pdf_path in pdf_paths:
        try:
            processed.append(
                process_invoice_pdf(
                    pdf_path,
                    output_dir,
                    created_at=created_at,
                    pdftoppm_command=pdftoppm_command,
                    tesseract_command=tesseract_command,
                )
            )
        except Exception as error:
            error_dir = output_dir / "error"
            error_dir.mkdir(parents=True, exist_ok=True)
            error_path = error_dir / f"{pdf_path.stem}.json"
            error_payload = {
                "source_filename": pdf_path.name,
                "category": "processing_failure",
                "occurred_at": created_at.isoformat().replace("+00:00", "Z"),
                "technical_code": type(error).__name__,
                "retryable": True,
                "operator_action": "Inspect the source PDF and local OCR runtime, then retry.",
            }
            error_path.write_text(
                json.dumps(error_payload, indent=2) + "\n", encoding="utf-8"
            )
            failed.append(BatchFailure(pdf_path, error_path))

    return BatchResult(processed=tuple(processed), failed=tuple(failed))
