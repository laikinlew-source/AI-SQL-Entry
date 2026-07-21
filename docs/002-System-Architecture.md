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

## Folder responsibilities

| Folder | Responsibility |
| --- | --- |
| `docs/` | Approved project vision, architecture, workflow, and future design documentation. |
| `incoming/` | User-controlled intake location. Contains files not yet claimed for processing. |
| `processing/` | Working area for claimed originals and their in-progress artifacts. |
| `completed/` | Approved originals and complete, reviewed artifact sets. |
| `error/` | Failed or rejected originals, available artifacts, and a recorded failure reason. |
| `samples/` | Non-sensitive example documents and expected outputs for development and testing. |
| `src/` | Future Python application source. It remains empty during the documentation phase. |
| `tests/` | Future automated tests and fixtures. It remains empty during the documentation phase. |
| `data/images/` | Derived page images or managed image working data that is not itself a lifecycle root. |
| `data/json/` | Structured JSON working data or shared schema-related data that is not yet archived with a completed/error artifact set. |
| `data/logs/` | Local audit and operational logs. Runtime log contents are excluded from Git. |

The lifecycle folders are authoritative for document state. `data/` supports processing but must not become an untracked alternate source of truth.

## Document lifecycle

The permitted high-level state flow is:

`incoming` -> `processing` -> `awaiting_review` -> `completed`

A failure or reviewer rejection may transition an item from `processing` or `awaiting_review` to `error`. The logical `awaiting_review` state remains represented within the document's processing metadata in `processing/`; no additional top-level folder is required for Version 1.

Each transition must:

1. Confirm the current state.
2. Confirm that the full artifact set has a unique destination.
3. Write or update the state record.
4. Move files using an atomic rename on the same volume where practical.
5. Record success or failure in the audit log.

If an atomic move is unavailable, the implementation must copy to a temporary destination, verify the copy, rename it into place, and only then remove the source. Partial destination files must not be treated as complete.

## Artifact model

Each document receives a stable, filesystem-safe `document_id`. Its artifact set contains, as applicable:

- The unmodified original file.
- A manifest containing source filename, content hash, detected format, page count, timestamps, and current state.
- Rendered page images with deterministic page numbering.
- Raw provider output when required for diagnosis and permitted by local retention rules.
- Normalized, versioned structured JSON.
- Validation findings.
- Human corrections and approval or rejection record.
- Error details when processing does not complete.

Artifacts must use collision-resistant paths and must not depend on the original filename being unique.

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

The schema must distinguish missing, unreadable, not applicable, and low-confidence values. Future SQL Account mapping is outside the Version 1 schema boundary.

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
