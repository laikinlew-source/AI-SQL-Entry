from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_import_package(canonical: dict[str, Any], output_dir: Path) -> None:
    """Write local SQL Account import-preparation files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    supplier = canonical["parties"]["issuer"]["name"]["extracted"][
        "normalized_value"
    ]
    details = canonical["document_details"]
    summary = canonical["financial_summary"]
    invoice_number = details["document_number"]["extracted"]["normalized_value"]
    provenance = [
        canonical["source"]["original_filename"],
        canonical["source"]["source_relative_path"],
        canonical["processing"]["ocr_timestamp"],
        canonical["processing"]["parser_version"],
        canonical["processing"]["processing_status"],
    ]
    provenance_headers = [
        "SourcePdfFilename",
        "SourceRelativePath",
        "OcrTimestamp",
        "ParserVersion",
        "ProcessingStatus",
    ]

    header_path = output_dir / "sql_account_purchase_invoice_header.csv"
    with header_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            provenance_headers + [
                "Supplier",
                "InvoiceNumber",
                "InvoiceDate",
                "Currency",
                "Subtotal",
                "SST",
                "TotalAmount",
            ]
        )
        writer.writerow(
            provenance + [
                supplier,
                invoice_number,
                details["issue_date"]["extracted"]["normalized_value"],
                details["currency"]["extracted"]["normalized_value"],
                summary["subtotal"]["extracted"]["normalized_value"]["value"],
                summary["tax"]["extracted"]["normalized_value"]["value"],
                summary["grand_total"]["extracted"]["normalized_value"]["value"],
            ]
        )

    lines_path = output_dir / "sql_account_purchase_invoice_lines.csv"
    with lines_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            provenance_headers + [
                "InvoiceNumber",
                "LineNumber",
                "Description",
                "Quantity",
                "UnitPrice",
                "Amount",
            ]
        )
        for position, item in enumerate(canonical["line_items"], start=1):
            writer.writerow(
                provenance + [
                    invoice_number,
                    position,
                    item["description"]["extracted"]["normalized_value"],
                    item["quantity"]["extracted"]["normalized_value"],
                    item["unit_price"]["extracted"]["normalized_value"]["value"],
                    item["line_total"]["extracted"]["normalized_value"]["value"],
                ]
            )

    manifest = {
        "format": "sql_account_purchase_invoice_mapping_preview_v1",
        "status": "mapping_review_required",
        "authorized_for_sql_account_write": False,
        "source_schema_version": canonical["schema_version"],
        "document_id": canonical["document_id"],
        "source_pdf_filename": canonical["source"]["original_filename"],
        "source_relative_path": canonical["source"]["source_relative_path"],
        "ocr_timestamp": canonical["processing"]["ocr_timestamp"],
        "parser_version": canonical["processing"]["parser_version"],
        "processing_status": canonical["processing"]["processing_status"],
        "files": [header_path.name, lines_path.name],
        "notice": (
            "The official SQL Account Purchase Invoice import contract is not yet "
            "verified. Review and map these local preparation files before import."
        ),
    }
    (output_dir / "sql_account_import_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
