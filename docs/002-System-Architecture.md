# AI-SQL-Entry System Architecture

## Architectural intent

Version 1 is a single-machine, local-only Python application organized as a staged document-processing pipeline. The architecture separates file lifecycle management, document normalization, extraction, validation, review, and audit concerns so each can be tested and changed independently.

This document defines responsibilities and boundaries. It does not select a specific AI/OCR model, review framework, database, or PDF/image library; those choices require later implementation plans and must preserve the constraints defined here.

## System boundary

The system begins when a user places a file in `incoming/` and ends when the reviewed original and its artifacts are moved to `completed/`, or when a failed item and its error record are moved to `error/`.

All processing, inference, storage, review, and logging occur on the local Windows machine. Version 1 has no network dependency for document processing and no connection to SQL Account, its database, email services, WhatsApp, or cloud storage.

## Logical components

### 1. Intake monitor

Observes `incoming/` for candidate files. It must tolerate repeated notifications and restarts. Detection alone does not authorize processing.

### 2. File-stability guard

Determines whether a file has finished copying or downloading. It uses repeated size and modification-time observations and confirms that the file can be opened for reading. An unstable or locked file remains in `incoming/` until it is stable or exceeds a documented wait policy.

### 3. Processing coordinator

Assigns a stable document identifier, performs safe lifecycle transitions, and invokes each stage in order. It records stage outcomes and must be restart-safe so an interrupted item can be diagnosed or resumed without duplicate completion.

### 4. Intake validator and duplicate detector

Validates the apparent and actual file type, readability, supported format, page count, and basic structural limits. It calculates a SHA-256 hash of the original bytes as the primary exact-duplicate key. Filename, size, and document metadata may support diagnostics but must not be the sole basis for declaring an exact duplicate.

### 5. Document normalizer

Creates local processing representations without modifying the original. It reads image files with orientation metadata applied and renders PDF pages to page images when required. Multi-page order must be preserved. HEIC is enabled only when a tested local Windows-compatible decoder is available.

### 6. AI/OCR extractor

Uses a locally available AI/OCR capability to classify the document and extract candidate fields, tables, line items, and field-level confidence. Provider-specific responses stay behind an adapter boundary so the normalized extraction result is independent of the chosen local model or OCR engine.

### 7. Structured-data validator

Validates the normalized result against a versioned JSON schema and document-type rules. Checks include required fields, data types, dates, currency, subtotal/tax/total relationships, line-item arithmetic, page coverage, and configured confidence thresholds. Validation issues are findings for review unless they prevent safe processing.

### 8. Human-review interface

Displays the original or rendered pages beside extracted values, confidence, and validation findings. It permits corrections and requires an explicit approve or reject action. Every correction and decision is recorded with timestamp and reviewer identity when available.

### 9. Artifact and lifecycle manager

Keeps the original, rendered pages, structured JSON, validation results, and review record together under one document identifier. It moves the complete artifact set to `completed/` after approval or to `error/` after a terminal failure. It must never silently overwrite an existing artifact set.

### 10. Audit logger

Writes structured local events for detection, state changes, hashes, validation outcomes, review corrections, approval, rejection, and failures. Logs must support troubleshooting without unnecessarily duplicating full document contents or sensitive field values.

## Folder responsibilities and artifact ownership

| Folder | Responsibility |
| --- | --- |
| `docs/` | Approved project vision, architecture, workflow, and future design documentation. |
| `incoming/` | User-controlled intake location. Contains files not yet claimed for processing. |
| `processing/` | Working area for claimed originals and artifacts in either `processing` or `awaiting_review` logical state. |
| `completed/` | Approved originals and complete, reviewed artifact sets. |
| `error/` | Failed or rejected originals, available artifacts, and a recorded failure reason. |
| `samples/` | Non-sensitive example documents and expected outputs for development and testing. |
| `src/` | Future Python application source. It remains empty during the documentation phase. |
| `tests/` | Future automated tests and fixtures. It remains empty during the documentation phase. |
| `data/images/` | Optional shared image cache. It is never the authoritative copy of a document's rendered pages. |
| `data/json/` | Optional shared schema or migration resources. It is never the authoritative canonical payload for a document. |
| `data/logs/` | The single authoritative root for append-only local audit and operational logs. Runtime log contents are excluded from Git. |

Canonical JSON is the single authority for logical document state. Lifecycle folders are physical workflow projections. `data/` supports processing but is never an alternate current-state authority.

## Document lifecycle authority

The permitted high-level state flow is:

`incoming` -> `processing` -> `awaiting_review` -> `completed`

A failure or reviewer rejection may transition an item from `processing` or `awaiting_review` to `error`. The logical `awaiting_review` state is physically stored under `processing/`; Version 1 does not add an `awaiting_review/` folder.

`lifecycle_status` in canonical JSON is authoritative. `processing.current_stage` reports execution activity only. Review, validation, error, and duplicate states constrain allowed transitions but do not replace `lifecycle_status`.

| Logical `lifecycle_status` | Physical projection | Required condition |
| --- | --- | --- |
| `incoming` | `incoming/<source-file>`; a minimal sidecar may exist | Stable-file acceptance is not complete. |
| `processing` | `processing/<document_id>/` | The file has been claimed and work is active or recoverable. |
| `awaiting_review` | `processing/<document_id>/` | Extraction is complete enough for human review. |
| `completed` | `completed/<document_id>/` | Explicit approval exists and no active blocking finding or error remains. |
| `error` | `error/<document_id>/` | A terminal failure or rejection record exists and the original remains recoverable. |

Valid transitions are `incoming -> processing`, `processing -> awaiting_review`, `awaiting_review -> completed`, `processing -> error`, and `awaiting_review -> error`. Retry is a recorded new processing attempt from `error -> processing` only when policy and operator disposition permit it. A permitted repeat follows `processing -> awaiting_review -> completed`. All other direct transitions are invalid, including `incoming -> completed`, `processing -> completed`, and any transition out of `completed` without an explicit migration or administrative recovery procedure.

Each transition must use this update order:

1. Confirm the current canonical state and transition preconditions.
2. Write the next canonical payload to a uniquely named temporary file in the current artifact directory; flush it and validate its schema.
3. Atomically replace `canonical.json`, retaining the previous revision until replacement succeeds.
4. Move the complete artifact directory to its projected folder using an atomic rename on the same volume where practical.
5. Append the transition result to the audit log in `data/logs/`.

If an atomic directory move is unavailable, the implementation must copy to a temporary destination, verify content and canonical JSON, rename it into place, and only then remove the source. Partial destinations are never valid projections.

On startup, reconciliation reads every lifecycle directory. A valid `canonical.json` wins over folder location; the coordinator either completes the interrupted move to the canonical state's projection or, if that cannot be done safely, quarantines the artifact set in `error/` with a recovery record. If canonical JSON is missing or invalid, no folder name may promote the document; the set is quarantined for operator recovery. Audit logs and `processing.current_stage` never override canonical state.

## Normative artifact directory model

Each claimed document receives a stable, filesystem-safe `document_id`. The authoritative artifact directory is projected under `processing/`, `completed/`, or `error/` according to canonical state:

```text
<lifecycle-root>/<document_id>/
  canonical.json
  original/<original-filename>
  pages/page-0001.png
  extraction/<run_id>/raw-output.json
  validation/<validation_run_id>.json
  review/events.jsonl
  errors/<error_id>.json
```

The single sources of truth are:

- `canonical.json` for current logical state, current business values, current review state, duplicate disposition, and current validation result.
- `original/` for the immutable original bytes.
- `pages/` for authoritative rendered-page artifacts.
- `extraction/` for immutable raw extraction-run output.
- `validation/` for append-only validation-run supporting records; canonical JSON embeds the reconciled `validation.runs` history and identifies the current run.
- `review/events.jsonl` for append-only review/correction supporting events; canonical JSON embeds the reconciled correction history and authoritative current field review state.
- `data/logs/` for append-only audit and operational logs.
- `errors/` for detailed safe error records; canonical JSON embeds the current terminal error summary.

Separate validation and review records support audit history and never compete with canonical JSON for current state.

Each artifact set contains, as applicable:

- The unmodified original file.
- An optional integrity manifest containing source filename, content hash, detected format, page count, and timestamps. It is supporting metadata and never carries authoritative current state.
- Rendered page images with deterministic page numbering.
- Raw provider output when required for diagnosis and permitted by local retention rules.
- Normalized, versioned structured JSON.
- Validation findings.
- Human corrections and approval or rejection record.
- Error details when processing does not complete.

Artifacts must use collision-resistant paths and must not depend on the original filename being unique.

## Local retention and sensitive-data policy

- Immutable originals, canonical JSON, review history, validation history, and audit evidence are retained for the deployment-configured business/legal duration approved by the operator. Version 1 does not invent a statutory period.
- Rendered pages and raw OCR output default to the same duration as their document unless the operator approves a shorter local retention rule that preserves auditability.
- Error artifacts are retained until resolved and then follow the approved document retention rule.
- Temporary files use unique names, remain inside the relevant artifact directory where possible, and are deleted after successful atomic replacement. Startup recovery removes abandoned temporary files only after confirming they are not the sole recoverable copy.
- Secrets and credentials are never stored in document artifacts, JSON, review history, or audit logs. Local extractor configuration stores only non-secret fingerprints.
- Deletion requires explicit operator authorization, applies to a resolved artifact set, and emits an audit event. Automated deletion is disabled until a retention configuration and deletion authority are approved.
- Cleanup failure is safe: retain the file, record the failure, and never delete the last verified original or canonical payload.

## Structured JSON boundary

The normalized JSON is the principal Version 1 output. At minimum, it should be able to represent:

- Schema version and document identifier.
- Source and processing metadata.
- Document type and classification confidence.
- Supplier or issuer details.
- Document numbers and relevant dates.
- Currency, subtotal, tax, adjustments, and total.
- Line items, quantities, units, descriptions, unit prices, tax, and amounts.
- Field-level source location and confidence where available.
- Validation findings and overall review status.
- Human corrections and approval metadata.

The schema must distinguish `missing`, `unreadable`, `uncertain`, `not_applicable`, `empty`, and `not_yet_processed` values. Future SQL Account mapping is outside the Version 1 schema boundary.

## Error handling and recovery

Errors are categorized as intake, unsupported format, unreadable/corrupt file, duplicate, rendering, extraction, validation, review rejection, storage, or unexpected internal failure. Every terminal error record must include the document identifier, stage, timestamp, safe human-readable reason, technical detail for maintainers, and whether retry is appropriate.

The original file must remain recoverable. Failures must not leave the same document active in two lifecycle folders. Startup recovery must detect abandoned processing state and reconcile it conservatively rather than restarting all work blindly.

## Security and privacy boundaries

- Documents and extracted data stay on the local machine.
- No document data may be sent to a cloud AI/OCR or conversion service.
- Logs avoid full sensitive values unless explicitly required for diagnosis.
- Secrets and machine-specific configuration are never committed to Git.
- Generated artifacts inherit access controls appropriate for accounting documents.
- Review actions should identify the local reviewer when practical, without creating a Version 1 identity-management system.

## Quality attributes

The architecture prioritizes data preservation, traceability, deterministic state transitions, idempotent processing, clear recovery, and testability over throughput. Version 1 may process documents sequentially if that produces safer behavior; parallel processing is not a requirement.

## Production validation projection

The production coordinator is an independent local orchestration component.
Its default roots are `incoming/`, `production/`, `quarantine/`, `archive/`,
`output/production-history/`, and `diagnostics/`. Each run has a unique
timestamped directory and each processed invoice has exactly one production
state: `READY`, `FAILED`, `REVIEW`, or `DUPLICATE`.

The coordinator reuses the existing pipeline, snapshot provider, validation,
and Get File 3 writer. SHA-256 plus the invoice-number, supplier, invoice-date,
and total-amount business tuple explain duplicate decisions. Resume state is
append-only and path-aware. Dashboards are evidence projections; they do not
override canonical JSON and never write to SQL Account.
