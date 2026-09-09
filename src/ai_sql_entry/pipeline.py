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
from .extraction import PARSER_VERSION, ExtractionError, Invoice, extract_invoice
from .ocr import ocr_pdf
from .sql_account_export import write_import_package
from .sql_account_validation import JsonSnapshotProvider, validate_invoice


DEFAULT_SQL_ACCOUNT_CONFIG_DIR = (
    Path(__file__).resolve().parents[2] / "config"
)


@dataclass(frozen=True)
class PipelineResult:
    document_id: str
    artifact_dir: Path
    canonical_path: Path
    extraction_report_path: Path
    sql_validation_report_path: Path


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary_path = path.parent / f"{path.name}.{uuid4().hex}.tmp"
    with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, path)


def _extraction_report(
    *,
    source_filename: str,
    source_relative_path: str,
    timestamp: str,
    processing_status: str,
    invoice: Invoice | None = None,
    error: ExtractionError | None = None,
) -> dict[str, object]:
    field_names = (
        "supplier",
        "invoice_number",
        "invoice_date",
        "currency",
        "subtotal",
        "sst",
        "total_amount",
        "line_items",
    )
    missing_fields = list(error.missing_fields) if error else []
    fields: dict[str, object] = {
        field: {
            "status": "failed" if field in missing_fields else "extracted"
        }
        for field in field_names
    }
    if invoice is not None:
        fields["line_items"] = {
            "status": "extracted",
            "count": len(invoice.line_items),
        }
    return {
        "source_pdf_filename": source_filename,
        "source_relative_path": source_relative_path,
        "ocr_timestamp": timestamp,
        "parser_version": PARSER_VERSION,
        "processing_status": processing_status,
        "fields": fields,
        "missing_fields": missing_fields,
        "field_failures": error.field_failures if error else {},
        "warnings": list(invoice.warnings) if invoice else [],
    }


def process_invoice_pdf(
    pdf_path: Path,
    output_root: Path,
    *,
    created_at: datetime,
    pdftoppm_command: tuple[str, ...] = ("pdftoppm",),
    tesseract_command: tuple[str, ...] = ("tesseract",),
    source_relative_path: str | None = None,
    sql_account_config_dir: Path | None = None,
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

    extraction_run_id = f"extract-{document_id}"
    extraction_dir = artifact_dir / "extraction" / extraction_run_id
    extraction_dir.mkdir(parents=True)
    (extraction_dir / "ocr.txt").write_text(
        ocr_result.text + "\n", encoding="utf-8"
    )
    timestamp = created_at.isoformat().replace("+00:00", "Z")
    relative_path = source_relative_path or pdf_path.as_posix()
    extraction_report_path = artifact_dir / "extraction_report.json"
    try:
        invoice = extract_invoice(ocr_result.text)
    except ExtractionError as error:
        _write_json_atomic(
            extraction_report_path,
            _extraction_report(
                source_filename=pdf_path.name,
                source_relative_path=relative_path,
                timestamp=timestamp,
                processing_status="extraction_failed",
                error=error,
            ),
        )
        error.extraction_report_path = extraction_report_path
        raise

    _write_json_atomic(
        extraction_report_path,
        _extraction_report(
            source_filename=pdf_path.name,
            source_relative_path=relative_path,
            timestamp=timestamp,
            processing_status="extraction_succeeded",
            invoice=invoice,
        ),
    )

    canonical = build_canonical(
        invoice,
        document_id=document_id,
        source_filename=pdf_path.name,
        source_relative_path=relative_path,
        source_sha256=source_sha256,
        page_count=len(ocr_result.page_paths),
        created_at=created_at,
        ocr_timestamp=timestamp,
        parser_version=PARSER_VERSION,
        processing_status="extraction_succeeded",
    )
    canonical_path = artifact_dir / "canonical.json"
    _write_json_atomic(canonical_path, canonical)

    master_data = JsonSnapshotProvider(
        sql_account_config_dir or DEFAULT_SQL_ACCOUNT_CONFIG_DIR
    ).load()
    sql_validation_report_path = (
        artifact_dir / "sql_account_validation_report.json"
    )
    _write_json_atomic(
        sql_validation_report_path,
        validate_invoice(canonical, master_data, validated_at=timestamp),
    )

    write_import_package(
        canonical,
        master_data,
        artifact_dir / "sql_account_import_package",
        generated_at=timestamp,
    )
    return PipelineResult(
        document_id,
        artifact_dir,
        canonical_path,
        extraction_report_path,
        sql_validation_report_path,
    )
