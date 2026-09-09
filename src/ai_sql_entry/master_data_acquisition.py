from __future__ import annotations

import csv
import json
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook

from .master_data_builder import build_snapshot
from .sql_account_validation import (
    JsonSnapshotProvider,
    SqlAccountMasterData,
    validate_invoice,
)


DATASETS = ("suppliers", "tax_codes", "gl_accounts", "currencies")
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".json"}


def _header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")


FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "suppliers": {
        "code": ("code", "supplier_code", "suppliercode", "creditor_code", "creditorcode"),
        "name": ("name", "company", "company_name", "companyname", "supplier_name"),
        "aliases": ("aliases", "alias"),
        "active": ("active", "is_active", "isactive"),
    },
    "tax_codes": {
        "code": ("code", "tax_code", "taxcode"),
        "tax_amount": ("tax_amount", "taxamount"),
        "rate": ("tax_rate", "taxrate", "rate", "percentage"),
        "tax_type": ("tax_type", "taxtype", "type", "description"),
        "active": ("active", "is_active", "isactive"),
    },
    "gl_accounts": {
        "code": ("code", "account_code", "accountcode", "gl_code", "glcode"),
        "name": ("name", "description", "account_name", "accountname"),
        "keywords": ("keywords", "keyword"),
        "default": ("default", "is_default", "isdefault"),
        "active": ("active", "is_active", "isactive"),
    },
    "currencies": {
        "code": ("code", "currency", "currency_code", "currencycode"),
        "active": ("active", "is_active", "isactive"),
    },
}


def _first(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def _raw_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            return [
                {_header(key): value for key, value in row.items() if key is not None}
                for row in reader
            ]
    if suffix == ".xlsx":
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            worksheet = workbook.worksheets[0]
            values = worksheet.iter_rows(values_only=True)
            headers = next(values, None)
            if headers is None:
                return []
            normalized_headers = [_header(value) for value in headers]
            return [
                dict(zip(normalized_headers, row, strict=False))
                for row in values
                if any(value not in (None, "") for value in row)
            ]
        finally:
            workbook.close()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            lists = [value for value in payload.values() if isinstance(value, list)]
            records = lists[0] if len(lists) == 1 else []
        else:
            records = []
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError("JSON export must contain a record list")
        return [{_header(key): value for key, value in row.items()} for row in records]
    raise ValueError("Supported exports are CSV, XLSX, and JSON")


def _possible_datasets(rows: list[dict[str, Any]], filename: str) -> list[str]:
    if not rows:
        return []
    headers = set(rows[0])
    possible: list[str] = []
    for dataset in DATASETS:
        aliases = FIELD_ALIASES[dataset]
        has_code = bool(headers.intersection(aliases["code"]))
        if dataset == "suppliers":
            qualifies = has_code and bool(headers.intersection(aliases["name"]))
        elif dataset == "tax_codes":
            qualifies = has_code and bool(
                headers.intersection(aliases["tax_amount"] + aliases["rate"] + aliases["tax_type"])
            )
        elif dataset == "gl_accounts":
            qualifies = has_code and bool(headers.intersection(aliases["name"]))
        else:
            qualifies = has_code
        if qualifies:
            possible.append(dataset)
    filename_key = _header(Path(filename).stem)
    hints = {
        "suppliers": ("supplier", "vendor", "creditor"),
        "tax_codes": ("tax", "sst", "gst"),
        "gl_accounts": ("gl", "account", "chart"),
        "currencies": ("currency", "currencies"),
    }
    hinted = [dataset for dataset in possible if any(hint in filename_key for hint in hints[dataset])]
    return hinted or possible


def discover_exports(incoming_dir: Path) -> dict[str, Any]:
    """Find one unambiguous export for each required master-data dataset."""
    candidates: dict[str, list[Path]] = {dataset: [] for dataset in DATASETS}
    errors: dict[str, list[str]] = {dataset: [] for dataset in DATASETS}
    if not incoming_dir.is_dir():
        return {
            "status": "blocked",
            "files": {},
            "errors": {dataset: [f"Directory does not exist: {incoming_dir}"] for dataset in DATASETS},
        }
    for path in sorted(incoming_dir.iterdir(), key=lambda value: value.name.casefold()):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue
        try:
            possible = _possible_datasets(_raw_rows(path), path.name)
        except Exception as error:
            possible = []
            errors_for_file = [f"{path.name}: {error}"]
            for dataset in DATASETS:
                errors[dataset].extend(errors_for_file)
        if len(possible) == 1:
            candidates[possible[0]].append(path)
        elif len(possible) > 1:
            for dataset in possible:
                errors[dataset].append(f"{path.name}: export matches multiple datasets")
    files: dict[str, str] = {}
    for dataset in DATASETS:
        if len(candidates[dataset]) == 1 and not errors[dataset]:
            files[dataset] = str(candidates[dataset][0])
        elif not candidates[dataset]:
            errors[dataset].append("No unambiguous export was found.")
        elif len(candidates[dataset]) > 1:
            errors[dataset].append("Multiple candidate exports were found.")
    return {
        "status": "ready" if len(files) == len(DATASETS) and not any(errors.values()) else "blocked",
        "files": files,
        "errors": errors,
    }


def _as_bool(value: Any) -> Any:
    return value


def _adapt_rows(dataset: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = FIELD_ALIASES[dataset]
    adapted: list[dict[str, Any]] = []
    for row in rows:
        normalized: dict[str, Any] = {
            "code": _first(row, aliases["code"]),
            "active": _as_bool(_first(row, aliases["active"])),
        }
        if dataset == "suppliers":
            normalized.update(
                {
                    "name": _first(row, aliases["name"]),
                    "aliases": _first(row, aliases["aliases"]),
                }
            )
        elif dataset == "tax_codes":
            tax_amount = _first(row, aliases["tax_amount"])
            if tax_amount in (None, ""):
                rate = _first(row, aliases["rate"])
                tax_type = _first(row, aliases["tax_type"])
                if rate not in (None, ""):
                    try:
                        tax_amount = (
                            "zero"
                            if Decimal(str(rate).strip().rstrip("%")) == 0
                            else "nonzero"
                        )
                    except InvalidOperation:
                        tax_amount = None
                elif tax_type not in (None, ""):
                    tax_amount = (
                        "zero"
                        if any(word in str(tax_type).casefold() for word in ("zero", "exempt", "out"))
                        else "nonzero"
                    )
            normalized["tax_amount"] = tax_amount
        elif dataset == "gl_accounts":
            normalized.update(
                {
                    "name": _first(row, aliases["name"]),
                    "keywords": _first(row, aliases["keywords"]),
                    "default": _first(row, aliases["default"]),
                }
            )
        adapted.append(normalized)
    return adapted


def _timestamp(value: datetime) -> tuple[str, str]:
    utc_value = value.astimezone(timezone.utc)
    return (
        utc_value.isoformat().replace("+00:00", "Z"),
        utc_value.strftime("%Y%m%dT%H%M%S%fZ"),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _canonical_paths(output_root: Path) -> list[Path]:
    return sorted(
        {path for path in output_root.rglob("canonical.json") if path.is_file()},
        key=lambda path: str(path).casefold(),
    )


def _readiness(output_root: Path, config_dir: Path) -> dict[str, Any]:
    snapshot_error: str | None = None
    try:
        master_data = JsonSnapshotProvider(config_dir).load()
    except Exception as error:
        # Still walk every canonical invoice when snapshots are unavailable so
        # the report identifies all invoices affected by the missing snapshot.
        master_data = SqlAccountMasterData()
        snapshot_error = str(error)
    counts = {
        "total_invoices": 0,
        "ready_for_import": 0,
        "not_ready": 0,
        "missing_supplier": 0,
        "missing_tax_code": 0,
        "missing_gl_account": 0,
        "missing_currency": 0,
    }
    failures: dict[str, int] = {}
    if snapshot_error:
        failures["snapshot"] = 1
    invoices: list[dict[str, Any]] = []
    for path in _canonical_paths(output_root):
        try:
            canonical = json.loads(path.read_text(encoding="utf-8"))
            validation = validate_invoice(canonical, master_data, validated_at=datetime.now(timezone.utc).isoformat())
        except Exception as error:
            counts["total_invoices"] += 1
            counts["not_ready"] += 1
            failures["canonical_read_error"] = failures.get("canonical_read_error", 0) + 1
            invoices.append({"path": str(path), "ready_for_import": "No", "failures": [str(error)]})
            continue
        counts["total_invoices"] += 1
        invoice_failures: list[str] = []
        category_map = {
            "supplier": "missing_supplier",
            "tax_code": "missing_tax_code",
            "gl_account": "missing_gl_account",
            "currency": "missing_currency",
        }
        for check_name, count_name in category_map.items():
            if validation["checks"][check_name]["status"] != "found":
                counts[count_name] += 1
                invoice_failures.append(check_name)
                failures[check_name] = failures.get(check_name, 0) + 1
        if canonical.get("lifecycle_status") != "completed":
            invoice_failures.append("lifecycle")
            failures["lifecycle"] = failures.get("lifecycle", 0) + 1
        if canonical.get("review", {}).get("decision") != "approved":
            invoice_failures.append("human_review")
            failures["human_review"] = failures.get("human_review", 0) + 1
        ready = not invoice_failures
        counts["ready_for_import" if ready else "not_ready"] += 1
        invoices.append(
            {
                "path": str(path),
                "document_id": canonical.get("document_id"),
                "source_pdf_filename": canonical.get("source", {}).get("original_filename"),
                "ready_for_import": "Yes" if ready else "No",
                "failures": invoice_failures,
                "mapping_validation": validation,
            }
        )
    counts["validation_failures_by_category"] = failures
    result = counts | {"invoices": invoices}
    if snapshot_error:
        result["snapshot_error"] = snapshot_error
    return result


def _write_markdown_reports(report_dir: Path, report: dict[str, Any]) -> dict[str, Path]:
    history_dir = report_dir / "history" / report["run_id"]
    history_dir.mkdir(parents=True, exist_ok=False)
    json_path = history_dir / "readiness_report.json"
    markdown_path = history_dir / "readiness_report.md"
    dashboard_path = history_dir / "summary_dashboard.md"
    _write_json(json_path, report)
    readiness = report["invoice_readiness"]
    markdown = "\n".join(
        [
            "# Master Data Readiness Report",
            "",
            f"- Run ID: `{report['run_id']}`",
            f"- Generated at: `{report['generated_at']}`",
            f"- Export directory: `{report['export_directory']}`",
            f"- Status: **{report['status']}**",
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Total invoices | {readiness['total_invoices']} |",
            f"| Ready for Import | {readiness['ready_for_import']} |",
            f"| Not Ready | {readiness['not_ready']} |",
            f"| Missing Supplier | {readiness['missing_supplier']} |",
            f"| Missing Tax Code | {readiness['missing_tax_code']} |",
            f"| Missing GL Account | {readiness['missing_gl_account']} |",
            f"| Missing Currency | {readiness['missing_currency']} |",
            "",
            "## Validation failures by category",
            "",
        ]
    )
    categories = readiness["validation_failures_by_category"] or {"none": 0}
    markdown += "\n".join(f"- `{name}`: {count}" for name, count in sorted(categories.items())) + "\n"
    markdown_path.write_text(markdown, encoding="utf-8")
    dashboard = "\n".join(
        [
            "# Master Data Summary Dashboard",
            "",
            f"**Run:** `{report['run_id']}`  ",
            f"**Status:** `{report['status']}`",
            "",
            "```text",
            f"Invoices       {readiness['total_invoices']}",
            f"Ready          {readiness['ready_for_import']}",
            f"Not ready      {readiness['not_ready']}",
            f"Supplier gaps  {readiness['missing_supplier']}",
            f"Tax gaps       {readiness['missing_tax_code']}",
            f"GL gaps        {readiness['missing_gl_account']}",
            f"Currency gaps  {readiness['missing_currency']}",
            "```",
            "",
            "This dashboard is a historical run artifact. It is not a SQL Account write or UI action.",
            "",
        ]
    )
    dashboard_path.write_text(dashboard, encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path, "dashboard": dashboard_path}


def run_master_data_acquisition(
    incoming_dir: Path,
    config_dir: Path,
    output_root: Path,
    *,
    invoice_root: Path | None = None,
    generated_at: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Acquire local exports, atomically replace all snapshots, and report readiness."""
    generated_at = generated_at or datetime.now(timezone.utc)
    generated_value, run_token = _timestamp(generated_at)
    run_id = f"{run_token}-{uuid4().hex[:8]}"
    report_dir = output_root / "master-data-readiness"
    report_dir.mkdir(parents=True, exist_ok=True)
    discovery = discover_exports(incoming_dir)
    snapshot_reports: dict[str, dict[str, Any]] = {}
    snapshot_errors: dict[str, list[dict[str, Any]]] = {}
    snapshots_written = 0
    status = "blocked"
    # Keep transient normalized exports outside the report tree.  This avoids
    # leaving implementation details in historical run artifacts and works
    # reliably when the project output is synchronized by OneDrive.
    # Named temporary files are used instead of a temporary directory.  This
    # keeps normalized reader output ephemeral while remaining compatible with
    # synchronized folders and restricted Windows directory ACLs.
    normalized_paths: dict[str, Path] = {}
    temporary_paths: list[Path] = []
    try:
        if discovery["status"] == "ready":
            for dataset, source in discovery["files"].items():
                rows = _adapt_rows(dataset, _raw_rows(Path(source)))
                temporary_file = tempfile.NamedTemporaryFile(
                    prefix=f"normalized-master-data-{dataset}-",
                    suffix=".json",
                    delete=False,
                    mode="w",
                    encoding="utf-8",
                )
                normalized_path = Path(temporary_file.name)
                try:
                    json.dump(rows, temporary_file)
                    temporary_file.flush()
                finally:
                    temporary_file.close()
                normalized_paths[dataset] = normalized_path
                temporary_paths.append(normalized_path)
            for dataset in DATASETS:
                snapshot_reports[dataset] = build_snapshot(
                    dataset,
                    normalized_paths[dataset],
                    config_dir,
                    dry_run=True,
                    timestamp=generated_at,
                )
            all_valid = all(report["status"] == "valid" for report in snapshot_reports.values())
            if all_valid and not dry_run:
                for dataset in DATASETS:
                    snapshot_reports[dataset] = build_snapshot(
                        dataset,
                        normalized_paths[dataset],
                        config_dir,
                        dry_run=False,
                        timestamp=generated_at,
                    )
                snapshots_written = sum(
                    1 for report in snapshot_reports.values() if report["snapshot_written"]
                )
                status = "written" if snapshots_written == len(DATASETS) else "blocked"
            elif all_valid:
                status = "dry_run"
            else:
                status = "blocked"
        else:
            status = "blocked"
        for dataset, report in snapshot_reports.items():
            if report["status"] != "valid" and report["status"] != "written":
                snapshot_errors[dataset] = report["errors"] + report["warnings"]
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)

    # Readiness is evaluated on every run, even when acquisition is blocked or
    # dry-run, against the snapshots currently on disk.
    readiness = _readiness(invoice_root or output_root, config_dir)
    report: dict[str, Any] = {
        "report_version": "1.0.0",
        "run_id": run_id,
        "generated_at": generated_value,
        "status": status,
        "export_directory": str(incoming_dir),
        "config_directory": str(config_dir),
        "output_root": str(output_root),
        "invoice_root": str(invoice_root or output_root),
        "sql_account_access": "none",
        "sql_account_ui_automated": False,
        "accounting_writes": False,
        "discovery": discovery,
        "snapshot_runs": snapshot_reports,
        "snapshot_errors": snapshot_errors,
        "snapshots": {"written": snapshots_written, "required": len(DATASETS)},
        "invoice_readiness": readiness,
    }
    paths = _write_markdown_reports(report_dir, report)
    report["report_paths"] = paths
    return report
