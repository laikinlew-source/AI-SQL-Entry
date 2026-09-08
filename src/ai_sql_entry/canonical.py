from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from .extraction import Invoice


def _review_state() -> dict[str, Any]:
    return {
        "status": "not_reviewed",
        "value": None,
        "reviewer": None,
        "reviewed_at": None,
        "reason": None,
        "notes": None,
        "latest_event_id": None,
    }


def _field(raw_value: str, normalized_value: Any, timestamp: str) -> dict[str, Any]:
    return {
        "value_status": "present",
        "extracted": {
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "confidence": None,
            "source_page": None,
            "source_location": None,
            "extractor": {
                "engine": "local-ocr-command",
                "engine_version": "unknown",
                "model_name": "not_applicable",
                "model_revision": "not_applicable",
            },
            "extracted_at": timestamp,
        },
        "reviewed": _review_state(),
    }


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _money(value: Decimal, currency: str) -> dict[str, str]:
    return {"value": f"{value:.2f}", "currency": currency}


def build_canonical(
    invoice: Invoice,
    *,
    document_id: str,
    source_filename: str,
    source_sha256: str,
    page_count: int,
    created_at: datetime,
) -> dict[str, Any]:
    """Build the documented canonical JSON projection for extracted invoice data."""
    timestamp = created_at.isoformat().replace("+00:00", "Z")
    line_items = []
    for position, item in enumerate(invoice.line_items, start=1):
        line_items.append(
            {
                "line_item_id": f"line-{position:04d}",
                "sequence_number": _field(str(position), str(position), timestamp),
                "description": _field(item.description, item.description, timestamp),
                "quantity": _field(
                    _decimal_text(item.quantity), _decimal_text(item.quantity), timestamp
                ),
                "unit_price": _field(
                    _decimal_text(item.unit_price),
                    _money(item.unit_price, invoice.currency),
                    timestamp,
                ),
                "line_total": _field(
                    _decimal_text(item.amount),
                    _money(item.amount, invoice.currency),
                    timestamp,
                ),
            }
        )

    return {
        "schema_version": "1.0.0",
        "document_id": document_id,
        "document_revision": 1,
        "document_type": _field("TAX INVOICE", "supplier_invoice", timestamp),
        "lifecycle_status": "awaiting_review",
        "source": {
            "original_filename": source_filename,
            "original_extension": ".pdf",
            "mime_type": "application/pdf",
            "sha256": source_sha256,
            "source_channel": "manual_copy",
            "received_at": timestamp,
            "page_count": page_count,
            "original_file_reference": f"original/{source_filename}",
            "rendered_page_references": [
                f"pages/page-{page:04d}.png" for page in range(1, page_count + 1)
            ],
        },
        "processing": {
            "pipeline_version": "0.1.0",
            "attempt_number": 1,
            "current_stage": "human_review",
            "page_count_status": "present",
            "tax_basis": "exclusive",
            "started_at": timestamp,
            "completed_at": None,
            "stage_history": [],
        },
        "parties": {
            "issuer": {
                "value_status": "present",
                "name": _field(invoice.supplier, invoice.supplier, timestamp),
            }
        },
        "document_details": {
            "document_number": _field(
                invoice.invoice_number, invoice.invoice_number, timestamp
            ),
            "issue_date": _field(
                invoice.invoice_date.isoformat(), invoice.invoice_date.isoformat(), timestamp
            ),
            "currency": _field(invoice.currency, invoice.currency, timestamp),
        },
        "financial_summary": {
            "subtotal": _field(
                _decimal_text(invoice.subtotal),
                _money(invoice.subtotal, invoice.currency),
                timestamp,
            ),
            "tax": _field(
                _decimal_text(invoice.sst),
                _money(invoice.sst, invoice.currency),
                timestamp,
            ),
            "grand_total": _field(
                _decimal_text(invoice.total_amount),
                _money(invoice.total_amount, invoice.currency),
                timestamp,
            ),
        },
        "line_items": line_items,
        "extraction": {
            "run_id": f"extract-{document_id}",
            "status": "succeeded",
            "started_at": timestamp,
            "completed_at": timestamp,
            "identity": {
                "provider": "local",
                "engine": "local-ocr-command",
                "engine_version": "unknown",
                "model_name": "not_applicable",
                "model_revision": "not_applicable",
                "ocr_language_packs": ["eng"],
                "prompt_template_version": "not_applicable",
                "preprocessing_pipeline_version": "pdf-raster-v1",
                "configuration_fingerprint": "not_applicable",
                "runtime_version": "python-3",
                "extraction_run_id": f"extract-{document_id}",
            },
            "raw_output_references": [f"extraction/extract-{document_id}/ocr.txt"],
            "populated_field_paths": [],
        },
        "duplicate_detection": {
            "status": "clear",
            "duplicate_type": "none",
            "matching_document_id": None,
            "matching_sha256": None,
            "matching_artifact_reference": None,
            "detected_at": timestamp,
            "detection_method": "sha256_current_output_directory",
            "disposition": "continue_processing",
            "operator_decision": None,
            "reprocessing_allowed": True,
        },
        "validation": {
            "current_run_id": "validation-0001",
            "runs": [
                {
                    "validation_run_id": "validation-0001",
                    "validated_at": timestamp,
                    "input_document_revision": 1,
                    "validator": {"name": "minimum-invoice-rules", "version": "1.0.0"},
                    "status": "blocked",
                    "supersedes_run_id": None,
                    "findings": [
                        {
                            "finding_id": "finding-review-required",
                            "severity": "blocking",
                            "code": "REVIEW.REQUIRED",
                            "message": "Human review is required before completion.",
                            "field_path": "/review",
                            "line_item_id": None,
                            "expected": "Explicit human approval",
                            "actual": "not_started",
                            "retryable": False,
                            "operator_action": "Review all extracted invoice values.",
                            "resolution_status": "active",
                            "resolved_by_event_id": None,
                        }
                    ],
                }
            ],
        },
        "review": {
            "status": "not_started",
            "decision": None,
            "reviewer": None,
            "started_at": None,
            "completed_at": None,
            "profile": {"name": "supplier_invoice", "version": "1.0.0"},
            "notes": None,
            "corrections": [],
        },
        "audit_references": [],
        "error": None,
    }
