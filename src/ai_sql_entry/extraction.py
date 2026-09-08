from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any


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


_REQUIRED_ALIAS_FIELDS = {
    "supplier",
    "invoice_number",
    "invoice_date",
    "currency",
    "subtotal",
    "sst",
    "total",
}


def _load_aliases(alias_config_path: Path | None) -> dict[str, list[str]]:
    if alias_config_path is None:
        config_text = (
            resources.files("ai_sql_entry")
            .joinpath("invoice_aliases.json")
            .read_text(encoding="utf-8")
        )
    else:
        config_text = alias_config_path.read_text(encoding="utf-8")
    aliases: Any = json.loads(config_text)
    if not isinstance(aliases, dict) or set(aliases) != _REQUIRED_ALIAS_FIELDS:
        raise ValueError("Alias configuration must define every supported field")
    if any(
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value.strip() for value in values)
        for values in aliases.values()
    ):
        raise ValueError("Every alias field must contain non-empty strings")
    return aliases


def _alias_pattern(alias: str) -> str:
    normalized = re.sub(r"[\s_-]+", "", alias)
    return r"[\s_-]*".join(re.escape(character) for character in normalized)


def _label(
    text: str,
    aliases: list[str],
    value_pattern: str,
    *,
    optional_tax_rate: bool = False,
) -> str:
    label_pattern = "|".join(
        _alias_pattern(alias) for alias in sorted(aliases, key=len, reverse=True)
    )
    tax_rate_pattern = r"(?:\s+[0-9.]+%)?" if optional_tax_rate else ""
    pattern = (
        rf"(?<![A-Za-z0-9])(?:{label_pattern}){tax_rate_pattern}"
        rf"\s*:\s*({value_pattern})"
    )
    for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        line_start = text.rfind("\n", 0, match.start()) + 1
        prefix = text[line_start : match.start()].strip()
        if not prefix or ":" in prefix:
            return match.group(1).strip()
    raise ValueError("Required invoice field not found for configured aliases")


def extract_invoice(
    text: str, *, alias_config_path: Path | None = None
) -> Invoice:
    """Extract invoice data from OCR text."""
    aliases = _load_aliases(alias_config_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    try:
        supplier = _label(text, aliases["supplier"], r"[^\r\n]+")
    except ValueError:
        supplier = lines[0]
    invoice_number = _label(text, aliases["invoice_number"], r"[^\r\n]+")
    invoice_date_text = _label(
        text, aliases["invoice_date"], r"\d{1,2}/\d{1,2}/\d{4}"
    )
    invoice_date = date.fromisoformat(
        "-".join(reversed(invoice_date_text.split("/")))
    )
    currency = _label(text, aliases["currency"], r"[A-Z]{3}").upper()
    subtotal = Decimal(
        _label(text, aliases["subtotal"], r"[0-9][0-9,.]*").replace(",", "")
    )
    sst = Decimal(
        _label(
            text,
            aliases["sst"],
            r"[0-9][0-9,.]*",
            optional_tax_rate=True,
        ).replace(",", "")
    )
    total_amount = Decimal(
        _label(text, aliases["total"], r"[0-9][0-9,.]*").replace(",", "")
    )

    item_lines = text.split("ITEMS", 1)[1].split("Subtotal:", 1)[0]
    items = []
    for row in item_lines.splitlines():
        if "|" in row:
            columns = [column.strip() for column in row.split("|")]
        else:
            match = re.fullmatch(
                r"(.+?)\s+([0-9,.]+)\s+([0-9,.]+)\s+([0-9,.]+)",
                row.strip(),
            )
            columns = list(match.groups()) if match else []
        if len(columns) != 4:
            continue
        items.append(
            LineItem(
                description=columns[0],
                quantity=Decimal(columns[1].replace(",", "")),
                unit_price=Decimal(columns[2].replace(",", "")),
                amount=Decimal(columns[3].replace(",", "")),
            )
        )

    if not items:
        raise ValueError("Required invoice line item not found")
    if abs((subtotal + sst) - total_amount) > Decimal("0.01"):
        raise ValueError("Invoice total does not equal subtotal plus SST")

    return Invoice(
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        subtotal=subtotal,
        sst=sst,
        total_amount=total_amount,
        line_items=tuple(items),
    )
