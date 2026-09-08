# AI-SQL-Entry

AI-SQL-Entry is a local supplier-invoice preparation pipeline:

`PDF -> local OCR -> invoice extraction -> canonical JSON -> read-only SQL Account validation -> import-preparation CSVs`

It never writes to SQL Account, its database, API, or user interface. Generated
records remain in `awaiting_review`, and the import manifest explicitly requires
mapping review before use.

## Run locally

Python 3.10 or later, Poppler's `pdftoppm`, and Tesseract OCR with the English
language pack must be installed locally and available on `PATH`:

```powershell
$env:PYTHONPATH = "src"
python -m ai_sql_entry "invoices/invoice.pdf" --output-root outputs
```

Use `--pdftoppm PATH` and `--tesseract PATH` when either executable is not on
`PATH`. No cloud service or network connection is used.

## Configure invoice field aliases

All recognized field labels are stored in
`config/field_aliases.json`. Add another string to the relevant
field's array to support a new label without changing Python code. Matching is
case-insensitive and treats spaces, hyphens, and underscores as optional.

## Configure read-only SQL Account validation

The pipeline reads local JSON snapshots only. It does not connect to an API or
database and cannot modify SQL Account. Enter verified master records in:

- `config/suppliers.json` — `code`, `name`, optional `aliases`, and `active`
- `config/tax_codes.json` — `code`, `tax_amount` (`zero` or `nonzero`), and `active`
- `config/gl_accounts.json` — `code`, `name`, optional `keywords`, optional
  `default`, and `active`
- `config/currencies.json` — `code` and `active`

The committed snapshots are intentionally empty. The validator never invents
master-data codes. Each successful extraction creates
`sql_account_validation_report.json`; `ready_for_sql_import` is `Yes` only when
the supplier, tax code, every line-item GL account, and currency are found.

Populate a snapshot from CSV, Excel (`.xlsx`), or JSON with the separate local
builder:

```powershell
ai-sql-master-data suppliers path\to\suppliers.xlsx --dry-run
ai-sql-master-data suppliers path\to\suppliers.xlsx
```

The first command validates and writes an import-statistics report without
changing the snapshot. A real replacement is atomic and first copies the
existing snapshot to `config/backups/` with a UTC timestamp. Replacement stops
when validation fails, duplicate supplier codes or normalized names are found,
or the imported row count is below 50% of the current snapshot. Override that
floor explicitly with `--min-retention-ratio` when a verified smaller export is
intentional. Use `--sheet` to select a named Excel worksheet and `--report` to
choose the statistics-report path.

Each run creates `outputs/processing/<document_id>/` containing the immutable
original copy, rendered pages, raw OCR text, `canonical.json`, extraction and
SQL Account validation reports, and a `sql_account_import/` preparation package.

Run the automated tests with:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Directory structure

- `docs/` — project documentation
- `incoming/` — newly received inputs awaiting processing
- `processing/` — inputs currently being processed
- `completed/` — successfully processed outputs
- `error/` — inputs or outputs that require investigation
- `samples/` — example inputs and reference material
- `src/` — Python application source
- `tests/` — automated tests and sanitized fixtures
- `data/images/` — image data used by future workflows
- `data/json/` — JSON data used by future workflows
- `data/logs/` — local runtime logs

## Project status

The minimum local extraction, read-only master-data validation, and
import-preparation pipeline is implemented. Human review, approval, and any
actual SQL Account import remain separate future work.

## License

This project is licensed under the MIT License. See `LICENSE` for details.
