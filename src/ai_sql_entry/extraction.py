from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


PARSER_VERSION = "0.3.0"
DEFAULT_ALIAS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "field_aliases.json"
)


class ExtractionError(ValueError):
    """Report all required invoice fields that could not be extracted."""

    def __init__(
        self,
        missing_fields: tuple[str, ...],
        field_failures: dict[str, str] | None = None,
    ) -> None:
        self.missing_fields = missing_fields
        self.field_failures = field_failures or {
            field: "No valid value was found in the OCR text."
            for field in missing_fields
        }
        field_list = ", ".join(
            "line item(s) [line_items]" if field == "line_items" else field
            for field in missing_fields
        )
        super().__init__(
            "Required invoice fields could not be extracted: "
            + field_list
        )


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Invoice:
    supplier: str
    invoice_number: str
    invoice_date: date
    currency: str
    subtotal: Decimal
    sst: Decimal
    total_amount: Decimal
    line_items: tuple[LineItem, ...]
    warnings: tuple[str, ...] = ()


_REQUIRED_ALIAS_FIELDS = {
    "supplier",
    "invoice_number",
    "invoice_date",
    "currency",
    "subtotal",
    "sst",
    "total",
}


def _load_parser_config(
    alias_config_path: Path | None,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    config_path = alias_config_path or DEFAULT_ALIAS_CONFIG_PATH
    config: Any = json.loads(config_path.read_text(encoding="utf-8"))
    aliases = config.get("fields", config) if isinstance(config, dict) else config
    if not isinstance(aliases, dict) or set(aliases) != _REQUIRED_ALIAS_FIELDS:
        raise ValueError("Alias configuration must define every supported field")
    if any(
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value.strip() for value in values)
        for values in aliases.values()
    ):
        raise ValueError("Every alias field must contain non-empty strings")
    if "fields" in config:
        line_items = config.get("line_items", {})
    else:
        default_config = json.loads(
            DEFAULT_ALIAS_CONFIG_PATH.read_text(encoding="utf-8")
        )
        line_items = default_config["line_items"]
    return aliases, line_items


def _alias_pattern(alias: str) -> str:
    normalized = re.sub(r"[\s_-]+", "", alias)
    return r"[\s_-]*".join(re.escape(character) for character in normalized)


def _label(
    text: str,
    aliases: list[str],
    value_pattern: str,
    *,
    optional_tax_rate: bool = False,
    conflicting_aliases: tuple[str, ...] = (),
) -> str:
    tax_rate_pattern = r"(?:\s+[0-9.]+%)?" if optional_tax_rate else ""
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = (
            rf"(?<![A-Za-z0-9])(?P<label>{_alias_pattern(alias)}){tax_rate_pattern}"
            rf"(?:\s*:\s*|\s+)({value_pattern})"
        )
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            target_start = match.start("label") - line_start
            target_end = match.end("label") - line_start
            line = text[line_start:line_end]
            contained_in_another_label = any(
                blocker.start() <= target_start and blocker.end() >= target_end
                for conflicting_alias in conflicting_aliases
                for blocker in re.finditer(
                    _alias_pattern(conflicting_alias), line, flags=re.IGNORECASE
                )
            )
            if not contained_in_another_label:
                return match.group(2).strip()
    raise ValueError("Required invoice field not found for configured aliases")


def _normalized_label(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _line_matches_alias(line: str, aliases: list[str], *, starts: bool) -> bool:
    normalized_line = _normalized_label(line)
    normalized_aliases = (_normalized_label(alias) for alias in aliases)
    if starts:
        return any(normalized_line.startswith(alias) for alias in normalized_aliases)
    return any(alias in normalized_line for alias in normalized_aliases)


def _parse_line_items(text: str, config: dict[str, Any]) -> list[LineItem]:
    start_aliases = config.get("start_aliases", [])
    end_aliases = config.get("end_aliases", [])
    ignore_aliases = config.get("ignore_aliases", [])
    lines = [line.strip() for line in text.splitlines()]
    start_index = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if _line_matches_alias(line, start_aliases, starts=False)
        ),
        None,
    )
    if start_index is None:
        return []

    items: list[LineItem] = []
    for row in lines[start_index:]:
        if _line_matches_alias(row, end_aliases, starts=True):
            break
        columns: list[str] = []
        if "|" in row:
            columns = [column.strip() for column in row.split("|")]
        if len(columns) == 4:
            items.append(
                LineItem(
                    description=columns[0],
                    quantity=Decimal(columns[1].replace(",", "")),
                    unit_price=Decimal(columns[2].replace(",", "")),
                    amount=Decimal(columns[3].replace(",", "")),
                )
            )
            continue

        malaysian_row = re.fullmatch(
            r"\d+\s+\S+\s+(.+?)\s+([0-9][0-9,.]*)\s+[A-Za-z]+\s+"
            r"([0-9][0-9,.]*)\s+(?:-|[0-9][0-9,.]*%?)\s+"
            r"(?:-|[0-9][0-9,.]*)\s+([0-9][0-9,.]*)",
            row,
        )
        simple_row = re.fullmatch(
            r"(.+?)\s+([0-9,.]+)\s+([0-9,.]+)\s+([0-9,.]+)", row
        )
        match = malaysian_row or simple_row
        if match:
            description, quantity, unit_price, amount = match.groups()
            items.append(
                LineItem(
                    description=description,
                    quantity=Decimal(quantity.replace(",", "")),
                    unit_price=Decimal(unit_price.replace(",", "")),
                    amount=Decimal(amount.replace(",", "")),
                )
            )
            continue

        if (
            items
            and row
            and ":" not in row
            and not _line_matches_alias(row, ignore_aliases, starts=True)
        ):
            items[-1] = replace(
                items[-1], description=f"{items[-1].description} {row}"
            )
    return items


def _has_blank_labeled_value(text: str, aliases: list[str]) -> bool:
    return any(
        re.search(
            rf"(?im){_alias_pattern(alias)}\s*:?[\s.+-]*$",
            text,
        )
        is not None
        for alias in aliases
    )


def extract_invoice(
    text: str, *, alias_config_path: Path | None = None
) -> Invoice:
    """Extract invoice data from OCR text."""
    aliases, line_item_config = _load_parser_config(alias_config_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    missing_fields: list[str] = []
    field_failures: dict[str, str] = {}
    warnings: list[str] = []

    try:
        supplier = _label(text, aliases["supplier"], r"[^\r\n]+")
    except ValueError:
        if lines:
            supplier = lines[0]
        else:
            supplier = ""
            missing_fields.append("supplier")
            field_failures["supplier"] = "The OCR text contained no supplier line."

    extracted_values: dict[str, Any] = {}
    aliases_from_other_fields = {
        field: tuple(
            alias
            for other_field, configured_aliases in aliases.items()
            if other_field != field
            for alias in configured_aliases
        )
        for field in aliases
    }
    field_extractors = {
        "invoice_number": lambda: _label(
            text,
            aliases["invoice_number"],
            r"[^\r\n]+",
            conflicting_aliases=aliases_from_other_fields["invoice_number"],
        ).rstrip(" ."),
        "invoice_date": lambda: date.fromisoformat(
            "-".join(
                reversed(
                    _label(
                        text,
                        aliases["invoice_date"],
                        r"\d{1,2}/\d{1,2}/\d{4}",
                        conflicting_aliases=aliases_from_other_fields["invoice_date"],
                    ).split("/")
                )
            )
        ),
        "currency": lambda: _label(
            text,
            aliases["currency"],
            r"[A-Z]{3}",
            conflicting_aliases=aliases_from_other_fields["currency"],
        ).upper(),
        "subtotal": lambda: Decimal(
            _label(
                text,
                aliases["subtotal"],
                r"[0-9][0-9,.]*",
                conflicting_aliases=aliases_from_other_fields["subtotal"],
            ).replace(",", "")
        ),
        "sst": lambda: Decimal(
            _label(
                text,
                aliases["sst"],
                r"[0-9][0-9,.]*",
                optional_tax_rate=True,
                conflicting_aliases=aliases_from_other_fields["sst"],
            ).replace(",", "")
        ),
        "total_amount": lambda: Decimal(
            _label(
                text,
                aliases["total"],
                r"[0-9][0-9,.]*",
                conflicting_aliases=aliases_from_other_fields["total"],
            ).replace(",", "")
        ),
    }
    for field_name, extractor in field_extractors.items():
        try:
            extracted_values[field_name] = extractor()
        except (ValueError, ArithmeticError):
            missing_fields.append(field_name)
            field_failures[field_name] = (
                "No configured alias was followed by a value in the expected format."
            )

    if (
        "sst" in missing_fields
        and "subtotal" in extracted_values
        and "total_amount" in extracted_values
        and extracted_values["subtotal"] == extracted_values["total_amount"]
        and _has_blank_labeled_value(text, aliases["sst"])
    ):
        extracted_values["sst"] = Decimal("0.00")
        missing_fields.remove("sst")
        field_failures.pop("sst", None)
        warnings.append(
            "SST was derived as 0.00 because the printed tax value was blank and "
            "subtotal equals total amount."
        )

    items = _parse_line_items(text, line_item_config)

    if not items:
        missing_fields.append("line_items")
        field_failures["line_items"] = (
            "No supported line-item rows were found after a configured table header."
        )
    if missing_fields:
        raise ExtractionError(tuple(missing_fields), field_failures)

    subtotal = extracted_values["subtotal"]
    sst = extracted_values["sst"]
    total_amount = extracted_values["total_amount"]
    if abs((subtotal + sst) - total_amount) > Decimal("0.01"):
        raise ValueError("Invoice total does not equal subtotal plus SST")

    return Invoice(
        supplier=supplier,
        invoice_number=extracted_values["invoice_number"],
        invoice_date=extracted_values["invoice_date"],
        currency=extracted_values["currency"],
        subtotal=subtotal,
        sst=sst,
        total_amount=total_amount,
        line_items=tuple(items),
        warnings=tuple(warnings),
    )
