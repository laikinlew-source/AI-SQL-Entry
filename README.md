# AI-SQL-Entry

AI-SQL-Entry is a local supplier-invoice preparation pipeline:

`PDF -> local OCR -> invoice extraction -> canonical JSON -> SQL Account import-preparation CSVs`

It never writes to SQL Account, its database, API, or user interface. Generated
records remain in `awaiting_review`, and the import manifest explicitly requires
mapping review before use.

## Run locally

Python 3.10 or later, Poppler's `pdftoppm`, and Tesseract OCR with the English
language pack must be installed locally and available on `PATH`:

```powershell
$env:PYTHONPATH = "src"
python -m ai_sql_entry invoice.pdf --output-root outputs
```

Use `--pdftoppm PATH` and `--tesseract PATH` when either executable is not on
`PATH`. No cloud service or network connection is used.

## Configure invoice field aliases

All recognized field labels are stored in
`src/ai_sql_entry/invoice_aliases.json`. Add another string to the relevant
field's array to support a new label without changing Python code. Matching is
case-insensitive and treats spaces, hyphens, and underscores as optional.

Each run creates `outputs/processing/<document_id>/` containing the immutable
original copy, rendered pages, raw OCR text, `canonical.json`, and a
`sql_account_import/` preparation package.

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

The minimum local extraction and import-preparation pipeline is implemented.
Human review, approval, and verified vendor-specific SQL Account mapping remain
separate future work.

## License

This project is licensed under the MIT License. See `LICENSE` for details.
