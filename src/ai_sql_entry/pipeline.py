from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .canonical import build_canonical
from .extraction import extract_invoice
from .ocr import ocr_pdf
from .sql_account_export import write_import_package


@dataclass(frozen=True)
class PipelineResult:
    document_id: str
    artifact_dir: Path
    canonical_path: Path


def process_invoice_pdf(
    pdf_path: Path,
    output_root: Path,
    *,
    created_at: datetime,
    pdftoppm_command: tuple[str, ...] = ("pdftoppm",),
    tesseract_command: tuple[str, ...] = ("tesseract",),
) -> PipelineResult:
    """Process one supplier-invoice PDF into local artifacts."""
    source_bytes = pdf_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    document_id = f"doc-{source_sha256[:12]}"
    artifact_dir = output_root / "processing" / document_id
    artifact_dir.mkdir(parents=True, exist_ok=False)

    original_dir = artifact_dir / "original"
    original_dir.mkdir()
    copied_original = original_dir / pdf_path.name
    shutil.copy2(pdf_path, copied_original)

    ocr_result = ocr_pdf(
        copied_original,
        artifact_dir,
        pdftoppm_command=pdftoppm_command,
        tesseract_command=tesseract_command,
    )
    invoice = extract_invoice(ocr_result.text)

    extraction_run_id = f"extract-{document_id}"
    extraction_dir = artifact_dir / "extraction" / extraction_run_id
    extraction_dir.mkdir(parents=True)
    (extraction_dir / "ocr.txt").write_text(
        ocr_result.text + "\n", encoding="utf-8"
    )

    canonical = build_canonical(
        invoice,
        document_id=document_id,
        source_filename=pdf_path.name,
        source_sha256=source_sha256,
        page_count=len(ocr_result.page_paths),
        created_at=created_at,
    )
    canonical_path = artifact_dir / "canonical.json"
    temporary_path = artifact_dir / f"canonical.{uuid4().hex}.tmp"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(canonical, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, canonical_path)

    write_import_package(canonical, artifact_dir / "sql_account_import")
    return PipelineResult(document_id, artifact_dir, canonical_path)
