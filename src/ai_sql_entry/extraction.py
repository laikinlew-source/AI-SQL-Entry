from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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


def _label(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if match is None:
        raise ValueError(f"Required invoice field not found: {pattern}")
    return match.group(1).strip()


def extract_invoice(text: str) -> Invoice:
    """Extract invoice data from OCR text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    supplier = lines[0]
    invoice_number = _label(text, r"^Invoice\s*(?:No|Number)\s*:\s*(.+)$")
    invoice_date = date.fromisoformat(
        "-".join(reversed(_label(text, r"^Invoice\s*Date\s*:\s*(\d{2}/\d{2}/\d{4})$").split("/")))
    )
    currency = _label(text, r"^Currency\s*:\s*([A-Z]{3})$").upper()
    subtotal = Decimal(_label(text, r"^Subtotal\s*:\s*([0-9,.]+)$").replace(",", ""))
    sst = Decimal(_label(text, r"^SST(?:\s+[0-9.]+%)?\s*:\s*([0-9,.]+)$").replace(",", ""))
    total_amount = Decimal(
        _label(text, r"^Total\s*Amount\s*:\s*([0-9,.]+)$").replace(",", "")
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
