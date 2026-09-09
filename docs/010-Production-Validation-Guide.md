# Production Validation Guide

## Purpose

Production validation is the unattended, local, read-only coordinator around
the existing OCR, canonical JSON, snapshot validation, and SQLAccXLSnMDBImp
Get File 3 writer. It creates evidence and files for a human operator; it does
not connect to SQL Account or perform an accounting write.

## Default folder layout

```text
incoming/                         real PDF intake
production/<run_id>/<STATE>/      per-run state artifacts
quarantine/                       unstable or unsupported inputs
archive/                          preserved source/history material
output/production-history/         immutable reports and resume index
diagnostics/                      sanitized technical diagnostics
```

Each run is unique. A processed invoice appears under exactly one of `READY`,
`FAILED`, `REVIEW`, or `DUPLICATE`. A state manifest is authoritative for the
production projection; prior run folders are never overwritten.

## One-shot and watch operation

```powershell
$env:PYTHONPATH = "src"
ai-sql-production --once
ai-sql-production --watch --poll-seconds 30
```

The default is one scan. The watch mode repeats the same deterministic scan.
Only physical `.pdf` files are eligible. A file must be readable and stable
for the configured stability interval before processing.

## State outcomes

- `READY`: extraction, current snapshots, arithmetic, review, and Get File 3
  template checks pass; both Excel files exist.
- `REVIEW`: extraction completed but a mapping, correction, or human approval
  is outstanding.
- `FAILED`: OCR, required-field extraction, arithmetic, template, storage, or
  unexpected processing failed. An exception report explains the action.
- `DUPLICATE`: SHA-256 or the complete business-key tuple matched a prior
  invoice. The report names every matching key and prior artifact.

Duplicate keys are SHA-256, Invoice Number, Supplier, Invoice Date, and Total
Amount. Missing keys never compare equal. The resume index records the source
path and hash, so a completed source is not reprocessed after restart while a
second file with the same hash is reported as `DUPLICATE`.

## Reports and audit

Each run writes `production_report.json` and `production_dashboard.md` under a
timestamped history directory and updates the current
`output/production-history/production_dashboard.md` projection. The dashboard
contains total invoices, all four state counts, supplier/tax/GL/currency
coverage, missing mappings, average processing time, and run history.

Per-invoice manifests preserve source filename, relative path, SHA-256,
processing timestamp, parser version, snapshot version, validation version,
import-package version, and review status. Accuracy is reported as
`not_measurable` until a reviewed ground-truth set exists; completeness,
confidence coverage, mapping coverage, corrections, arithmetic, template, and
ReadyForImport are measurable proxies.

## Safety and recovery

The coordinator is local-only and never writes to SQL Account. It does not use
SQL Account API, database access, desktop automation, or UI posting. Reports
are append-only. A restart consults the resume index and existing state
manifests before processing. Configuration is editable in
`config/production_validation.json`; tests use temporary paths and controlled
clocks rather than real invoices.

## Troubleshooting

- `FAILED` with `OCR_FAILURE`: inspect the local OCR commands and retry after
  correcting the runtime.
- `FAILED` with `MISSING_FIELD`: inspect the extraction report; no placeholder
  values are inserted.
- `REVIEW` with a mapping mismatch: update the local snapshot or correct the
  invoice during human review.
- `DUPLICATE`: inspect the prior run and matching keys before any operator
  disposition.
- Empty dashboard coverage: no processed invoice supplied that mapping
  denominator, so the metric is intentionally null rather than zero.

