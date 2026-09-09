from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .extraction import ExtractionError, PARSER_VERSION
from .pipeline import PipelineResult, process_invoice_pdf


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
    identity = (entry.get("source_sha256"), entry.get("source_path"))
    entries = [
        existing
        for existing in index["entries"]
        if (existing.get("source_sha256"), existing.get("source_path")) != identity
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


def _default_processor(
    pdf_path: Path,
    output_root: Path,
    *,
    created_at: datetime,
    source_relative_path: str,
) -> PipelineResult:
    return process_invoice_pdf(
        pdf_path,
        output_root,
        created_at=created_at,
        source_relative_path=source_relative_path,
    )


def _source_relative_path(config: ProductionConfig, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_stable(path: Path, seconds: float, sleep: Any) -> bool:
    try:
        before = path.stat()
    except OSError:
        return False
    if seconds:
        sleep(seconds)
    try:
        after = path.stat()
    except OSError:
        return False
    return before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns


def _json_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return payload


def _write_exception_report(path: Path, audit: Mapping[str, object], findings: list[dict[str, object]]) -> None:
    atomic_write_json(
        path,
        {
            "report_version": "1.0.0",
            "audit": dict(audit),
            "findings": findings,
        },
    )


def classify_pipeline_artifacts(
    canonical: Mapping[str, object],
    package_report: Mapping[str, object],
) -> tuple[str, list[dict[str, object]]]:
    findings: list[dict[str, object]] = []
    for mapping in package_report.get("missing_mappings", []):
        if not isinstance(mapping, Mapping):
            continue
        mapping_name = str(mapping.get("mapping", "")).casefold()
        category = {
            "supplier": "SUPPLIER_MISMATCH",
            "tax_code": "TAX_MISMATCH",
            "gl_account": "GL_MISMATCH",
            "currency": "CURRENCY_MISMATCH",
        }.get(mapping_name, "MANUAL_REVIEW_REQUIRED")
        findings.append(
            exception_report(
                category,
                str(mapping.get("reason", "Required master-data mapping is missing.")),
                field_path=mapping.get("field_path"),
                retryable=False,
                operator_action="Update the local snapshot or correct the invoice during review.",
                report_reference="Mapping_Report.json",
            )
        )

    validations = package_report.get("validations", {})
    if isinstance(validations, Mapping):
        for name in ("totals", "sst", "line_totals"):
            result = validations.get(name)
            if isinstance(result, Mapping) and result.get("passed") is False:
                findings.append(
                    exception_report(
                        "ARITHMETIC_MISMATCH",
                        f"{name} validation failed.",
                        field_path=None,
                        retryable=False,
                        operator_action="Correct the extracted values and review the invoice.",
                        report_reference="Validation_Report.json",
                    )
                )
        review = validations.get("human_review")
        if isinstance(review, Mapping) and review.get("passed") is False:
            findings.append(
                exception_report(
                    "MANUAL_REVIEW_REQUIRED",
                    "Human review or approval is incomplete.",
                    field_path="/review",
                    retryable=False,
                    operator_action="Complete human review and approval.",
                    report_reference="Validation_Report.json",
                )
            )

    if str(package_report.get("ReadyForImport", "NO")).upper() == "YES" and not findings:
        return "READY", []
    if any(finding["category"] == "ARITHMETIC_MISMATCH" for finding in findings):
        return "FAILED", findings
    return "REVIEW", findings or [
        exception_report(
            "MANUAL_REVIEW_REQUIRED",
            "Import package preflight did not report readiness.",
            field_path=None,
            retryable=False,
            operator_action="Inspect the validation report and complete review.",
            report_reference="Validation_Report.json",
        )
    ]


def _error_category(error: Exception) -> str:
    if isinstance(error, ExtractionError) and error.missing_fields:
        return "MISSING_FIELD"
    if "ocr" in type(error).__name__.casefold() or "pdf" in type(error).__name__.casefold():
        return "OCR_FAILURE"
    return "OCR_FAILURE"


def _audit_for_source(
    config: ProductionConfig,
    path: Path,
    sha256: str,
    run_id: str,
    processed_at: str,
    *,
    canonical: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    if canonical is not None:
        return build_audit(canonical, config, run_id, processed_at)
    return {
        "document_id": f"doc-{sha256[:12]}",
        "run_id": run_id,
        "source_pdf_filename": path.name,
        "source_relative_path": _source_relative_path(config, path),
        "source_sha256": sha256,
        "processing_timestamp": processed_at,
        "parser_version": PARSER_VERSION,
        "snapshot_version": config.snapshot_version,
        "validation_version": config.validation_version,
        "import_package_version": config.import_package_version,
        "review_status": "not_reviewed",
    }


def _outcome_payload(outcome: InvoiceOutcome) -> dict[str, object]:
    return {
        "state": outcome.state,
        "document_id": outcome.document_id,
        "source_path": outcome.source_path.as_posix(),
        "source_sha256": outcome.source_sha256,
        "run_id": outcome.run_id,
        "artifact_dir": outcome.artifact_dir.as_posix(),
        "manifest_path": outcome.manifest_path.as_posix(),
        "exception_report_path": (
            outcome.exception_report_path.as_posix()
            if outcome.exception_report_path is not None
            else None
        ),
        "processing_seconds": outcome.processing_seconds,
        "review_status": outcome.review_status,
    }


def _publish_outcome(
    config: ProductionConfig,
    run_id: str,
    state: str,
    source_path: Path,
    sha256: str,
    document_id: str,
    staging_artifact: Path | None,
    audit: Mapping[str, object],
    findings: list[dict[str, object]],
    processing_seconds: float,
    *,
    duplicate_report: Mapping[str, object] | None = None,
) -> InvoiceOutcome:
    state_dir = config.production_dir / run_id / state / document_id
    state_dir.parent.mkdir(parents=True, exist_ok=True)
    if state_dir.exists():
        raise FileExistsError(f"Production state artifact already exists: {state_dir}")
    state_dir.mkdir()
    if staging_artifact is not None and staging_artifact.is_dir():
        for child in staging_artifact.iterdir():
            destination = state_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)
    exception_path: Path | None = None
    if findings:
        exception_path = state_dir / "exception_report.json"
        _write_exception_report(exception_path, audit, findings)
    if duplicate_report is not None:
        atomic_write_json(state_dir / "duplicate_report.json", dict(duplicate_report))
    manifest_path = state_dir / "manifest.json"
    outcome = InvoiceOutcome(
        state=state,
        document_id=document_id,
        source_path=source_path,
        source_sha256=sha256,
        run_id=run_id,
        artifact_dir=state_dir,
        manifest_path=manifest_path,
        exception_report_path=exception_path,
        processing_seconds=processing_seconds,
        review_status=str(audit.get("review_status", "not_reviewed")),
    )
    references = {"state_directory": state_dir.as_posix()}
    if (state_dir / "canonical.json").is_file():
        references["canonical"] = "canonical.json"
    if (state_dir / "sql_account_import_package").is_dir():
        references["import_package"] = "sql_account_import_package"
    write_invoice_manifest(manifest_path, audit, outcome, references)
    return outcome


def _hash_entry(
    index: Mapping[str, object],
    sha256: str,
    source_path: str | None = None,
) -> Mapping[str, object] | None:
    matches: list[Mapping[str, object]] = []
    for entry in index.get("entries", []):
        if isinstance(entry, Mapping) and entry.get("source_sha256") == sha256:
            matches.append(entry)
    if source_path is not None:
        for entry in matches:
            if entry.get("source_path") == source_path:
                return entry
    return matches[0] if matches else None


def run_production_once(
    config: ProductionConfig,
    *,
    now: datetime,
    processor: Any = None,
    run_token: str | None = None,
    sleep: Any = time.sleep,
) -> dict[str, object]:
    """Process one deterministic production scan without external access."""
    ensure_production_roots(config)
    run_id = create_run_id(now, run_token or uuid4().hex[:8])
    run_dir = config.production_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    staging_dir = run_dir / ".staging"
    staging_dir.mkdir()
    index = load_resume_index(config)
    outcomes: list[InvoiceOutcome] = []
    skipped = 0
    unstable = 0
    processor = processor or _default_processor
    for source_path in discover_invoice_files(config):
        if not _is_stable(source_path, config.stability_seconds, sleep):
            unstable += 1
            continue
        started = time.perf_counter()
        sha256 = _sha256(source_path)
        source_relative_path = _source_relative_path(config, source_path)
        previous = _hash_entry(index, sha256, source_relative_path)
        same_source = previous is not None and previous.get("source_path") == source_relative_path
        if (
            previous is not None
            and previous.get("state") in PRODUCTION_STATES
            and same_source
            and not config.retry_failed
        ):
            skipped += 1
            continue
        processed_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        direct_duplicate = previous is not None and previous.get("state") in PRODUCTION_STATES
        if direct_duplicate:
            audit = _audit_for_source(config, source_path, sha256, run_id, processed_at)
            finding = exception_report(
                "DUPLICATE",
                "The source SHA-256 matches a prior processed invoice.",
                field_path=None,
                retryable=False,
                operator_action="Review the prior artifact and duplicate disposition.",
                report_reference=str(previous.get("artifact_path") or "resume_index.json"),
            )
            outcome = _publish_outcome(
                config,
                run_id,
                "DUPLICATE",
                source_path,
                sha256,
                f"doc-{sha256[:12]}",
                None,
                audit,
                [finding],
                time.perf_counter() - started,
                duplicate_report={"reason": "sha256_match", "prior": dict(previous)},
            )
            outcomes.append(outcome)
            record_resume_entry(
                config,
                {
                    "source_sha256": sha256,
                    "source_path": source_relative_path,
                    "document_id": outcome.document_id,
                    "run_id": run_id,
                    "state": outcome.state,
                    "artifact_path": outcome.artifact_dir.as_posix(),
                    "invoice_number": "",
                    "supplier": "",
                    "invoice_date": "",
                    "total_amount": "",
                },
            )
            continue

        try:
            result = processor(
                source_path,
                staging_dir,
                created_at=now,
                source_relative_path=source_relative_path,
            )
            canonical = _json_report(result.canonical_path)
            business_duplicate = find_duplicate(canonical, index)
            if business_duplicate is not None:
                audit = build_audit(canonical, config, run_id, processed_at)
                finding = exception_report(
                    "DUPLICATE",
                    "The invoice matches a prior invoice by a composite business key.",
                    field_path=None,
                    retryable=False,
                    operator_action="Review the prior artifact and duplicate disposition.",
                    report_reference="duplicate_report.json",
                )
                outcome = _publish_outcome(
                    config,
                    run_id,
                    "DUPLICATE",
                    source_path,
                    sha256,
                    str(canonical.get("document_id") or f"doc-{sha256[:12]}"),
                    result.artifact_dir,
                    audit,
                    [finding],
                    time.perf_counter() - started,
                    duplicate_report=business_duplicate,
                )
            else:
                package_path = result.artifact_dir / "sql_account_import_package" / "Validation_Report.json"
                package_report = _json_report(package_path)
                state, findings = classify_pipeline_artifacts(canonical, package_report)
                audit = build_audit(canonical, config, run_id, processed_at)
                outcome = _publish_outcome(
                    config,
                    run_id,
                    state,
                    source_path,
                    sha256,
                    str(canonical.get("document_id") or f"doc-{sha256[:12]}"),
                    result.artifact_dir,
                    audit,
                    findings,
                    time.perf_counter() - started,
                )
        except Exception as error:
            audit = _audit_for_source(config, source_path, sha256, run_id, processed_at)
            category = _error_category(error)
            if isinstance(error, ExtractionError) and error.missing_fields:
                message = "Required fields could not be extracted: " + ", ".join(error.missing_fields)
            else:
                message = "Invoice processing failed before a canonical artifact was produced."
            finding = exception_report(
                category,
                message,
                field_path=None,
                retryable=True,
                operator_action="Inspect the source PDF and local OCR runtime, then retry.",
            )
            outcome = _publish_outcome(
                config,
                run_id,
                "FAILED",
                source_path,
                sha256,
                f"doc-{sha256[:12]}",
                None,
                audit,
                [finding],
                time.perf_counter() - started,
            )
        outcomes.append(outcome)
        index = load_resume_index(config)
        canonical_for_index = None
        canonical_path = outcome.artifact_dir / "canonical.json"
        if canonical_path.is_file():
            canonical_for_index = _json_report(canonical_path)
        business = _canonical_business_keys(canonical_for_index) if canonical_for_index else {}
        record_resume_entry(
            config,
            {
                "source_sha256": sha256,
                "source_path": source_relative_path,
                "document_id": outcome.document_id,
                "run_id": run_id,
                "state": outcome.state,
                "artifact_path": outcome.artifact_dir.as_posix(),
                "invoice_number": business.get("invoice_number", ""),
                "supplier": business.get("supplier", ""),
                "invoice_date": business.get("invoice_date", ""),
                "total_amount": business.get("total_amount", ""),
            },
        )

    counts = {state: sum(1 for outcome in outcomes if outcome.state == state) for state in PRODUCTION_STATES}
    return {
        "report_version": "1.0.0",
        "run_id": run_id,
        "started_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "counts": counts,
        "processed": len(outcomes),
        "skipped": skipped,
        "unstable": unstable,
        "outcomes": [_outcome_payload(outcome) for outcome in outcomes],
    }
