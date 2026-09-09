# Import Workflow, Get File 3 Boundary, and Limitations

## Approved Version 1 workflow

```text
SQL Account built-in export or approved read-only source
        │
        ▼
incoming/master-data/
        │  discover four files
        ▼
reader adapters (CSV / XLSX / JSON)
        │  normalize headers and values
        ▼
source-independent validation
        │  duplicates, required fields, retention floor
        ▼
all four snapshots replaced atomically per file
        │  timestamped backups retained
        ▼
canonical invoice revalidation
        │  supplier / tax / GL / currency
        ▼
timestamped readiness_report.json/.md + summary dashboard
```

The CLI entry point is `ai-sql-master-data-acquire`. A blocked or dry-run
acquisition still revalidates existing canonical invoices against snapshots
currently on disk. No snapshot is replaced unless all four imported datasets
pass validation.

## Official SQL Account import target

The current import-package implementation targets the official
`SQLAccXLSnMDBImp` **Get File 3** workflow and generates exactly:

- `Purchase Invoice Header.xlsx`
- `Purchase Invoice Detail.xlsx`

The workbooks use a stable common key, `dd/mm/yyyy` dates, numeric-only cells,
no thousand separators or currency symbols, UTF-8-compatible text, and
preserved decimal precision. The local template validator checks sheet names,
column names/order, required fields, numeric/date formats, and header/detail
key consistency.

The generated package is file-only. It does not open SQL Account, click an
Import button, click `Post To A/c`, or write to the database.

The vendor's [Excel Import Guide](https://docs.sql.com.my/sqlacc/miscellaneous/acc-xls-mdb-import)
documents the Get File 3 sequence: choose `Get File 3`, select the Excel Header
File, select the Excel Detail File, choose each worksheet, select the common Key
Field, get data, and save the merged file. The same guide identifies `Post To
A/c` as the final accounting action. AI-SQL-Entry intentionally stops before
that action.

## Import methods compared

| Method | Current status | Limitation |
| --- | --- | --- |
| Get File 3 XLSX package | Implemented and validated locally | The final SQL Account import click remains a human-controlled step |
| SQL Account UI data entry | Discovery only | Listing/form accessibility and blank-form contract are not stable |
| Official API POST | Not implemented | Exact Purchase Invoice POST contract and entitlement are unverified |
| Direct database write | Permanently excluded | Violates read-only architecture and accounting safety |

## Workflow limitations

- A source export is not accepted merely because its filename looks correct;
  headers must identify exactly one dataset.
- Ambiguous, malformed, duplicate, or significantly smaller imports block all
  snapshot replacement.
- Existing snapshots are backed up before replacement.
- Empty snapshots cause readiness failures rather than fabricated mappings.
- A successful local package does not mean SQL Account accepted or posted it;
  import validation and posting remain separate human-controlled operations.
- UI automation is layout, DPI, version, and focus sensitive. It is not the
  primary import mechanism.

## Troubleshooting

| Symptom | Safe response |
| --- | --- |
| `No unambiguous export was found` | Ensure exactly one CSV/XLSX/JSON file per dataset and use recognizable headers |
| Snapshot replacement blocked by retention warning | Confirm the export is complete; do not lower the threshold without review |
| Missing supplier/tax/GL/currency | Correct the source export or local mapping; never add placeholders |
| Get File 3 validator failure | Inspect the generated workbook contract; do not import until it passes |
| SQL Account window unavailable to automation | Keep the read-only file hand-off workflow; do not use guessed coordinates |
| API service not found | Stop; licensing/setup and vendor evidence are required before any API work |
