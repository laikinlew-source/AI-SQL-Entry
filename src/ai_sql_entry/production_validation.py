from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_FOLDERS = {
    "incoming": "incoming",
    "production": "production",
    "quarantine": "quarantine",
    "archive": "archive",
    "history": "output/production-history",
    "diagnostics": "diagnostics",
}

PRODUCTION_STATES = ("READY", "FAILED", "REVIEW", "DUPLICATE")
EXCEPTION_CATEGORIES = (
    "OCR_FAILURE",
    "MISSING_FIELD",
    "SUPPLIER_MISMATCH",
    "TAX_MISMATCH",
    "GL_MISMATCH",
    "CURRENCY_MISMATCH",
    "ARITHMETIC_MISMATCH",
    "DUPLICATE",
    "MANUAL_REVIEW_REQUIRED",
)


@dataclass(frozen=True)
class ProductionConfig:
    project_root: Path
    incoming_dir: Path
    production_dir: Path
    quarantine_dir: Path
    archive_dir: Path
    history_dir: Path
    diagnostics_dir: Path
    poll_interval_seconds: float = 30.0
    stability_seconds: float = 2.0
    supported_extensions: tuple[str, ...] = (".pdf",)
    retry_failed: bool = False
    snapshot_version: str = "1.0.0"
    validation_version: str = "1.0.0"
    import_package_version: str = "1.0.0"


@dataclass(frozen=True)
class InvoiceOutcome:
    state: str
    document_id: str | None
    source_path: Path
    source_sha256: str
    run_id: str
    artifact_dir: Path
    manifest_path: Path
    exception_report_path: Path | None
    processing_seconds: float
    review_status: str


def _resolve_folder(project_root: Path, value: object, default: str) -> Path:
    folder = Path(str(value if value is not None else default))
    return folder if folder.is_absolute() else project_root / folder


def _non_negative_number(value: object, name: str, default: float) -> float:
    number = float(default if value is None else value)
    if number < 0:
        raise ValueError(f"{name} must not be negative")
    return number


def load_production_config(
    path: Path | None,
    *,
    project_root: Path | None = None,
) -> ProductionConfig:
    """Load local production settings without contacting external systems."""
    resolved_path = path.resolve() if path is not None else None
    root = (project_root or Path.cwd()).resolve()
    if resolved_path is not None:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    else:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Production configuration must be a JSON object")

    folders = payload.get("folders", {})
    if not isinstance(folders, dict):
        raise ValueError("Production configuration folders must be an object")
    folder_values = {
        name: _resolve_folder(root, folders.get(name), default)
        for name, default in DEFAULT_FOLDERS.items()
    }
    extensions = payload.get("supported_extensions", [".pdf"])
    if not isinstance(extensions, list) or not extensions:
        raise ValueError("supported_extensions must be a non-empty list")
    normalized_extensions = tuple(
        extension.casefold() if str(extension).startswith(".") else f".{extension.casefold()}"
        for extension in extensions
    )
    return ProductionConfig(
        project_root=root,
        incoming_dir=folder_values["incoming"],
        production_dir=folder_values["production"],
        quarantine_dir=folder_values["quarantine"],
        archive_dir=folder_values["archive"],
        history_dir=folder_values["history"],
        diagnostics_dir=folder_values["diagnostics"],
        poll_interval_seconds=_non_negative_number(
            payload.get("poll_interval_seconds"), "poll_interval_seconds", 30.0
        ),
        stability_seconds=_non_negative_number(
            payload.get("stability_seconds"), "stability_seconds", 2.0
        ),
        supported_extensions=normalized_extensions,
        retry_failed=bool(payload.get("retry_failed", False)),
        snapshot_version=str(payload.get("snapshot_version", "1.0.0")),
        validation_version=str(payload.get("validation_version", "1.0.0")),
        import_package_version=str(
            payload.get("import_package_version", "1.0.0")
        ),
    )


def ensure_production_roots(config: ProductionConfig) -> None:
    for path in (
        config.incoming_dir,
        config.production_dir,
        config.quarantine_dir,
        config.archive_dir,
        config.history_dir,
        config.diagnostics_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def create_run_id(now: datetime, token: str) -> str:
    utc_now = now.astimezone(timezone.utc)
    return f"{utc_now:%Y%m%dT%H%M%SZ}-{token}"


def discover_invoice_files(config: ProductionConfig) -> tuple[Path, ...]:
    if not config.incoming_dir.is_dir():
        return ()
    return tuple(
        sorted(
            (
                path
                for path in config.incoming_dir.rglob("*")
                if path.is_file()
                and path.suffix.casefold() in config.supported_extensions
            ),
            key=lambda path: path.as_posix().casefold(),
        )
    )


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.parent / f"{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_resume_index(config: ProductionConfig) -> dict[str, object]:
    path = config.history_dir / "resume_index.json"
    if not path.is_file():
        return {"version": "1.0.0", "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError("resume_index.json must contain an entries list")
    return payload


def record_resume_entry(
    config: ProductionConfig, entry: Mapping[str, object]
) -> None:
    index = load_resume_index(config)
    entries = [
        existing
        for existing in index["entries"]
        if existing.get("source_sha256") != entry.get("source_sha256")
    ]
    entries.append(dict(entry))
    atomic_write_json(
        config.history_dir / "resume_index.json",
        {"version": index.get("version", "1.0.0"), "entries": entries},
    )


def _normalize_business_value(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _field_value(field: Mapping[str, Any] | None) -> object:
    if not isinstance(field, Mapping):
        return None
    reviewed = field.get("reviewed")
    if isinstance(reviewed, Mapping) and reviewed.get("status") in {
        "corrected",
        "supplied",
    }:
        return reviewed.get("value")
    extracted = field.get("extracted")
    if isinstance(extracted, Mapping):
        return extracted.get("normalized_value")
    return None


def _canonical_business_keys(canonical: Mapping[str, Any]) -> dict[str, str]:
    source = canonical.get("source", {})
    parties = canonical.get("parties", {})
    issuer = parties.get("issuer", {}) if isinstance(parties, Mapping) else {}
    details = canonical.get("document_details", {})
    summary = canonical.get("financial_summary", {})
    total = _field_value(summary.get("grand_total")) if isinstance(summary, Mapping) else None
    if isinstance(total, Mapping):
        total = total.get("value")
    return {
        "sha256": str(source.get("sha256", "")) if isinstance(source, Mapping) else "",
        "invoice_number": _normalize_business_value(
            _field_value(details.get("document_number")) if isinstance(details, Mapping) else None
        ),
        "supplier": _normalize_business_value(
            _field_value(issuer.get("name")) if isinstance(issuer, Mapping) else None
        ),
        "invoice_date": str(
            _field_value(details.get("issue_date")) if isinstance(details, Mapping) else ""
        ),
        "total_amount": str(total or ""),
    }


def find_duplicate(
    canonical: Mapping[str, Any], index: Mapping[str, object]
) -> dict[str, object] | None:
    current = _canonical_business_keys(canonical)
    for entry in index.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        prior = {
            "sha256": str(entry.get("source_sha256", "")),
            "invoice_number": _normalize_business_value(entry.get("invoice_number")),
            "supplier": _normalize_business_value(entry.get("supplier")),
            "invoice_date": str(entry.get("invoice_date", "")),
            "total_amount": str(entry.get("total_amount", "")),
        }
        sha_match = bool(current["sha256"] and prior["sha256"] == current["sha256"])
        business_names = ("invoice_number", "supplier", "invoice_date", "total_amount")
        business_matches = [
            name
            for name in business_names
            if current[name] and prior[name] and current[name] == prior[name]
        ]
        composite_match = len(business_matches) == len(business_names)
        if not sha_match and not composite_match:
            continue
        matching_keys = (["sha256"] if sha_match else []) + business_matches
        return {
            "reason": "sha256_match" if sha_match else "composite_business_key_match",
            "matching_keys": matching_keys,
            "prior_document_id": entry.get("document_id"),
            "prior_run_id": entry.get("run_id"),
            "prior_artifact_path": entry.get("artifact_path"),
            "current_values": current,
            "prior_values": prior,
        }
    return None


def build_audit(
    canonical: Mapping[str, Any],
    config: ProductionConfig,
    run_id: str,
    processed_at: str,
) -> dict[str, object]:
    source = canonical.get("source", {})
    processing = canonical.get("processing", {})
    review = canonical.get("review", {})
    return {
        "document_id": canonical.get("document_id"),
        "run_id": run_id,
        "source_pdf_filename": source.get("original_filename"),
        "source_relative_path": source.get("source_relative_path"),
        "source_sha256": source.get("sha256"),
        "processing_timestamp": processed_at,
        "parser_version": processing.get("parser_version"),
        "snapshot_version": config.snapshot_version,
        "validation_version": config.validation_version,
        "import_package_version": config.import_package_version,
        "review_status": review.get("status", "not_reviewed")
        if isinstance(review, Mapping)
        else "not_reviewed",
    }


def exception_report(
    category: str,
    message: str,
    *,
    field_path: str | None,
    retryable: bool,
    operator_action: str,
    report_reference: str | None = None,
) -> dict[str, object]:
    if category not in EXCEPTION_CATEGORIES:
        raise ValueError(f"Unsupported production exception category: {category}")
    severity = "warning" if category in {"DUPLICATE", "MANUAL_REVIEW_REQUIRED"} else "error"
    return {
        "category": category,
        "severity": severity,
        "message": message,
        "field_path": field_path,
        "retryable": retryable,
        "operator_action": operator_action,
        "report_reference": report_reference,
    }


def write_invoice_manifest(
    path: Path,
    audit: Mapping[str, object],
    outcome: InvoiceOutcome,
    references: Mapping[str, str],
) -> None:
    if outcome.state not in PRODUCTION_STATES:
        raise ValueError(f"Unsupported production state: {outcome.state}")
    payload = {
        "manifest_version": "1.0.0",
        "state": outcome.state,
        "document_id": outcome.document_id,
        "run_id": outcome.run_id,
        "source_path": outcome.source_path.as_posix(),
        "source_sha256": outcome.source_sha256,
        "processing_seconds": outcome.processing_seconds,
        "review_status": outcome.review_status,
        "audit": dict(audit),
        "references": dict(references),
        "exception_report_path": (
            outcome.exception_report_path.as_posix()
            if outcome.exception_report_path is not None
            else None
        ),
    }
    atomic_write_json(path, payload)
