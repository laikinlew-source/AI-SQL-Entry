# Production Validation Design

**Status:** Approved design, pending implementation
**Scope:** AI-SQL-Entry Version 1 production-validation milestone
**Design date:** 2026-09-09

## 1. Purpose

This milestone adds a deterministic production coordinator around the existing
PDF/OCR parser, canonical JSON, local master-data snapshots, validation rules,
and SQLAccXLSnMDBImp Get File 3 package writer. It makes the file-based
workflow safe to run unattended while keeping SQL Account completely
read-only.

The coordinator is orchestration only. It does not replace the existing OCR,
parser, canonical data model, snapshot provider, arithmetic validator, template
validator, or workbook writer.

## 2. Non-goals and safety boundary

The implementation must not:

- connect to a SQL Account database or API;
- automate SQL Account, Windows UI, or desktop controls;
- post, import, or modify accounting data;
- invent invoice fields, mappings, confidence, or accuracy measurements;
- add a cloud service, message broker, database, or runtime dependency;
- change the existing canonical JSON or SQL Account workbook contracts.

The only side effects are local files, local reports, local snapshot reads, and
existing read-only snapshot/report generation.

## 3. Production folder contract

The project root is the default configuration base. All paths are configurable
and may be absolute or project-relative after resolution.

```text
incoming/                         Real invoice intake (PDF only)
production/                       Per-run state artifacts
  <run_id>/
    READY/<document_id>/
    REVIEW/<document_id>/
    FAILED/<document_id>/
    DUPLICATE/<document_id>/
quarantine/                       Unprocessable/non-PDF or unstable files
archive/                          Preserved source and prior artifacts
output/production-history/        Immutable run reports and resume index
diagnostics/                      Sanitized technical diagnostics
```

Each run uses a UTC timestamp plus a collision-safe suffix, for example
`20260909T041530Z-a1b2c3d4`. A run directory is created with exclusive
creation; existing run directories are never reused or overwritten.

The state directory is the lifecycle projection for the processed invoice. The
canonical JSON and all generated reports for that invoice live under exactly
one of `READY`, `REVIEW`, `FAILED`, or `DUPLICATE`. `archive/` is a preservation
location for source files and historical artifacts, not a second lifecycle
state. Files that are not eligible invoices (for example, non-PDF files or
files that remain unstable) may be quarantined and are not counted as
processed invoices.

## 4. File lifecycle and state authority

The coordinator records one immutable outcome per source content hash. The
state field in the per-invoice manifest is authoritative:

```text
stable PDF
    -> extraction and canonicalization
    -> duplicate check
    -> snapshot mapping and arithmetic validation
    -> human-review gate
    -> template/package validation
    -> exactly one of READY | REVIEW | FAILED | DUPLICATE
```

State meanings:

- `READY`: required extraction, current snapshots, arithmetic, review, and
  Get File 3 template checks pass; both XLSX files are present.
- `REVIEW`: processing completed but a human decision or correction is still
  required, including unresolved warnings not permitted to pass.
- `FAILED`: processing or validation failed and an exception report explains
  the failure. Retryability is recorded separately.
- `DUPLICATE`: the source matches an earlier source by one or more duplicate
  keys. No import package is generated for the duplicate.

The coordinator never silently transitions a completed state in place. A retry
creates a new run artifact and references the prior attempt; the prior state
remains readable. A duplicate outcome is terminal for that source hash unless
an operator explicitly reprocesses it through existing duplicate controls.

## 5. Intake, stability, and resume

The one-shot runner scans `incoming/` recursively for physical `.pdf` files,
case-insensitively. The polling runner repeats the same scan at the configured
interval. A file is eligible only after its size and modification time remain
unchanged for the configured stability window and the file can be opened for
read.

Every eligible file is hashed before processing. The resume index under
`output/production-history/` records source hash, source path, document ID,
latest run, state, and artifact path. The index is updated atomically after the
per-invoice manifest and reports are durable. On restart:

- a hash with a terminal state is skipped unless explicit retry is requested;
- a hash with an incomplete run is reconciled from its manifest and either
  completed or safely marked failed;
- a changed file is a new source hash and is processed independently;
- no completed invoice is processed a second time by default.

The coordinator never uses a time-only filename or source filename as identity.
SHA-256 is the primary identity.

## 6. Duplicate protection

Duplicate detection compares the current invoice with prior canonical and
production manifests using all available keys:

- exact source SHA-256;
- normalized invoice number;
- normalized supplier name;
- ISO invoice date;
- decimal total amount.

The duplicate report lists every matching key, the prior document/run ID, and
comparison values. A SHA-256 match is exact. A composite business-key match is
probable but still fail-closed as `DUPLICATE` until an operator chooses the
existing duplicate disposition. Missing business keys do not match; the report
records that the key was unavailable rather than treating missing values as
equal.

## 7. Existing module integration

The coordinator calls existing modules through narrow adapters:

1. `process_invoice_pdf` produces canonical JSON, the extraction report, and
   existing package/report artifacts in a run-owned temporary location.
2. `JsonSnapshotProvider` loads the four current local snapshots.
3. `validate_invoice` performs source-independent supplier, tax, GL, and
   currency mapping checks.
4. `write_import_package` performs arithmetic, review, and Get File 3 workbook
   generation and validation.
5. The coordinator writes the per-invoice manifest, exception report, and
   audit fields, then publishes the final state directory atomically.

No business rule is duplicated in the coordinator. If an adapter cannot load a
canonical artifact or snapshot, the invoice becomes `FAILED` with an
operator-actionable exception.

## 8. Exception reports

Every non-READY outcome has a JSON exception report. Findings use stable codes
and JSON Pointer paths when a source field exists. Required categories are:

- `OCR_FAILURE`;
- `MISSING_FIELD`;
- `SUPPLIER_MISMATCH`;
- `TAX_MISMATCH`;
- `GL_MISMATCH`;
- `CURRENCY_MISMATCH`;
- `ARITHMETIC_MISMATCH`;
- `DUPLICATE`;
- `MANUAL_REVIEW_REQUIRED`.

Each finding includes category/code, severity, message, field path or null,
source value when safe, retryability, operator action, and originating report
reference. Technical details are sanitized and must not include OCR stderr,
credentials, secrets, or unnecessary invoice content.

## 9. Audit trail and provenance

The per-invoice manifest and every generated report carry:

- source filename and project-relative source path;
- source SHA-256;
- processing timestamp and run ID;
- parser version;
- snapshot version(s), taken from the validated local snapshot schema and
  recorded as a deterministic combined fingerprint;
- validation version;
- import-package version;
- lifecycle state and review status;
- canonical/report/package artifact references.

These values are copied from existing artifacts or deterministic configuration
fingerprints; they are never fabricated as business data.

## 10. Production dashboard and run history

Each run writes immutable `production_report.json`,
`production_dashboard.md`, and per-invoice manifests under
`output/production-history/<run_id>/`. The dashboard includes total invoices,
READY/REVIEW/FAILED/DUPLICATE counts, supplier/tax/GL/currency coverage,
missing mappings by category, average processing time, and prior run references.

Coverage is the percentage of processed invoices (excluding quarantined
non-invoices) with a found mapping. A metric is `null` with an explanatory
reason when its denominator is zero. Run history is append-only and never
overwritten. `production_dashboard.md` is a current summary projection; its
timestamped source reports remain authoritative.

## 11. Accuracy and measurement rules

The coordinator reports measurable proxies, not unsupported claims:

- extraction completeness and line-item coverage;
- OCR confidence coverage and mean confidence only when all scored fields have
  confidence;
- parser/review correction rate for reviewed fields;
- mapping coverage per master-data category;
- arithmetic and template pass rates;
- ReadyForImport rate.

True OCR or parser accuracy is `not_measurable` until a reviewed ground-truth
set is supplied. Reviewer corrections are an improvement signal, never an
accuracy claim without a declared reference set.

## 12. Configuration

`config/production_validation.json` is the editable default configuration. It
contains folder paths for all production roots, stability window, polling
interval, supported extensions, duplicate/retry policy, processing-time and
coverage thresholds, and snapshot/validation/package version identifiers.

The loader validates the configuration, applies safe defaults, and rejects
unknown lifecycle states or negative intervals. Tests pass explicit temporary
directories and clocks; they never depend on the real OneDrive paths.

## 13. Deterministic testing

Tests are written before implementation and use temporary directories,
controlled timestamps, the repository's fake OCR commands, and local JSON
snapshots. Coverage includes folder creation, exclusive run IDs, stable-file
filtering, quarantine, every terminal state and exception category, duplicate
reasons, resume after interruption, audit provenance, dashboard counts and
history, fail-closed workbook generation, configuration validation, and no
external SQL Account/UI/database/network calls.

## 14. Future compatibility

The coordinator depends on source-independent interfaces for invoice processing,
master-data lookup, and import-package generation. A future official API or
desktop/file adapter can implement those interfaces without changing lifecycle,
duplicate, exception, audit, resume, or dashboard business rules. The default
implementation remains local JSON snapshots and file generation.
