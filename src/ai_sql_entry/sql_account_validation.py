from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SupplierRecord:
    code: str
    name: str
    aliases: tuple[str, ...] = ()
    active: bool = True


@dataclass(frozen=True)
class TaxCodeRecord:
    code: str
    tax_amount: str
    active: bool = True


@dataclass(frozen=True)
class GlAccountRecord:
    code: str
    name: str
    keywords: tuple[str, ...] = ()
    default: bool = False
    active: bool = True


@dataclass(frozen=True)
class CurrencyRecord:
    code: str
    active: bool = True


@dataclass(frozen=True)
class SqlAccountMasterData:
    suppliers: tuple[SupplierRecord, ...] = ()
    tax_codes: tuple[TaxCodeRecord, ...] = ()
    gl_accounts: tuple[GlAccountRecord, ...] = ()
    currencies: tuple[CurrencyRecord, ...] = ()


class JsonSnapshotProvider:
    """Load editable SQL Accounting master-data snapshots without external access."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def _records(self, filename: str, key: str) -> list[dict[str, Any]]:
        path = self.config_dir / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "1.0.0":
            raise ValueError(f"Unsupported schema version in {filename}")
        records = payload.get(key)
        if not isinstance(records, list):
            raise ValueError(f"{filename} must contain a {key} list")
        return records

    def load(self) -> SqlAccountMasterData:
        suppliers = tuple(
            SupplierRecord(
                code=record["code"],
                name=record["name"],
                aliases=tuple(record.get("aliases", [])),
                active=record.get("active", True),
            )
            for record in self._records("suppliers.json", "suppliers")
        )
        tax_codes = tuple(
            TaxCodeRecord(
                code=record["code"],
                tax_amount=record["tax_amount"],
                active=record.get("active", True),
            )
            for record in self._records("tax_codes.json", "tax_codes")
        )
        gl_accounts = tuple(
            GlAccountRecord(
                code=record["code"],
                name=record["name"],
                keywords=tuple(record.get("keywords", [])),
                default=record.get("default", False),
                active=record.get("active", True),
            )
            for record in self._records("gl_accounts.json", "gl_accounts")
        )
        currencies = tuple(
            CurrencyRecord(
                code=record["code"],
                active=record.get("active", True),
            )
            for record in self._records("currencies.json", "currencies")
        )
        return SqlAccountMasterData(
            suppliers=suppliers,
            tax_codes=tax_codes,
            gl_accounts=gl_accounts,
            currencies=currencies,
        )


def _business_value(field: dict[str, Any]) -> Any:
    reviewed = field.get("reviewed", {})
    if reviewed.get("status") in {"corrected", "supplied"}:
        return reviewed.get("value")
    return field["extracted"]["normalized_value"]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _supplier_check(
    supplier_name: str, records: tuple[SupplierRecord, ...]
) -> dict[str, Any]:
    source_name = _normalized_name(supplier_name)
    match = next(
        (
            record
            for record in records
            if record.active
            and source_name
            in {_normalized_name(record.name), *map(_normalized_name, record.aliases)}
        ),
        None,
    )
    return {
        "status": "found" if match else "missing",
        "source_value": supplier_name,
        "mapped_code": match.code if match else None,
        "matched_name": match.name if match else None,
        "field_path": "/parties/issuer/name",
        "reason": None
        if match
        else "No active supplier mapping matched the extracted supplier name.",
    }


def _tax_check(tax_value: str, records: tuple[TaxCodeRecord, ...]) -> dict[str, Any]:
    condition = "zero" if Decimal(tax_value) == 0 else "nonzero"
    match = next(
        (
            record
            for record in records
            if record.active and record.tax_amount == condition
        ),
        None,
    )
    return {
        "status": "found" if match else "missing",
        "source_value": tax_value,
        "match_condition": condition,
        "mapped_code": match.code if match else None,
        "field_path": "/financial_summary/tax",
        "reason": None
        if match
        else f"No active tax-code mapping handles a {condition} tax amount.",
    }


def _gl_check(
    line_items: list[dict[str, Any]], records: tuple[GlAccountRecord, ...]
) -> dict[str, Any]:
    active_records = tuple(record for record in records if record.active)
    default = next((record for record in active_records if record.default), None)
    results = []
    for index, line_item in enumerate(line_items):
        description = str(_business_value(line_item["description"]))
        normalized_description = description.casefold()
        match = next(
            (
                record
                for record in active_records
                if record.keywords
                and any(
                    keyword.casefold() in normalized_description
                    for keyword in record.keywords
                )
            ),
            default,
        )
        results.append(
            {
                "line_item_id": line_item.get("line_item_id"),
                "field_path": f"/line_items/{index}/description",
                "source_value": description,
                "status": "found" if match else "missing",
                "mapped_code": match.code if match else None,
                "matched_name": match.name if match else None,
                "reason": None
                if match
                else "No active GL account keyword or default mapping matched this line item.",
            }
        )
    all_found = bool(results) and all(item["status"] == "found" for item in results)
    return {
        "status": "found" if all_found else "missing",
        "line_items": results,
        "reason": None
        if all_found
        else "One or more line items have no active GL account mapping.",
    }


def _currency_check(
    currency: str, records: tuple[CurrencyRecord, ...]
) -> dict[str, Any]:
    match = next(
        (
            record
            for record in records
            if record.active and record.code.casefold() == currency.casefold()
        ),
        None,
    )
    return {
        "status": "found" if match else "missing",
        "source_value": currency,
        "mapped_code": match.code if match else None,
        "field_path": "/document_details/currency",
        "reason": None
        if match
        else "The extracted currency is not present in the active currency snapshot.",
    }


def validate_invoice(
    canonical: dict[str, Any],
    master_data: SqlAccountMasterData,
    *,
    validated_at: str,
) -> dict[str, Any]:
    """Validate canonical invoice values against source-independent master data."""
    supplier_name = str(_business_value(canonical["parties"]["issuer"]["name"]))
    tax_value = str(
        _business_value(canonical["financial_summary"]["tax"])["value"]
    )
    currency = str(_business_value(canonical["document_details"]["currency"]))
    checks = {
        "supplier": _supplier_check(supplier_name, master_data.suppliers),
        "tax_code": _tax_check(tax_value, master_data.tax_codes),
        "gl_account": _gl_check(canonical["line_items"], master_data.gl_accounts),
        "currency": _currency_check(currency, master_data.currencies),
    }
    ready = all(check["status"] == "found" for check in checks.values())
    return {
        "report_version": "1.0.0",
        "document_id": canonical["document_id"],
        "source_pdf_filename": canonical["source"]["original_filename"],
        "source_relative_path": canonical["source"]["source_relative_path"],
        "ocr_timestamp": canonical["processing"]["ocr_timestamp"],
        "parser_version": canonical["processing"]["parser_version"],
        "processing_status": canonical["processing"]["processing_status"],
        "validated_at": validated_at,
        "master_data_source": "local_json_snapshots",
        "access_mode": "read_only",
        "writes_performed": False,
        "checks": checks,
        "ready_for_sql_import": "Yes" if ready else "No",
    }
