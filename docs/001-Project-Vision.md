# AI-SQL-Entry Project Vision

## Purpose

AI-SQL-Entry is a local document-processing and human-review system for documents that will eventually be entered into SQL Account. It reduces repetitive data preparation while keeping a person responsible for checking and approving every extracted record.

Version 1 stops at an approved, structured output. It does not enter data into SQL Account or modify any SQL Account database.

## Project goals

Version 1 aims to:

1. Provide one dependable folder-based intake point for business documents collected from common sources.
2. Preserve every original document while creating traceable processing artifacts.
3. Extract useful accounting data from PDFs and images through locally operated AI/OCR capabilities.
4. Validate extracted fields, totals, line items, and confidence before review.
5. Give a human reviewer a clear way to correct and approve extracted data.
6. Produce structured, versioned JSON suitable for a future SQL Account integration phase.
7. Make every state change, validation result, correction, approval, and failure auditable.
8. Handle duplicates and failures safely without silently losing or overwriting files.

## Version 1 users

The primary users are accounts and administrative staff who collect supplier and purchasing documents and prepare them for entry into SQL Account. A technical maintainer may configure, operate, and troubleshoot the local installation.

## Version 1 scope

### Input sources

Files enter the system only when they are placed in `incoming/`. They may originate from:

- Mobile phone photos.
- Email attachments that a user has manually downloaded.
- WhatsApp files that a user has manually downloaded or saved.
- Scanned documents.
- Files manually copied into the intake folder.

Version 1 does not connect to an email mailbox or WhatsApp account.

### Supported file formats

- PDF
- JPG
- JPEG
- PNG
- HEIC when a dependable local decoder is available on the target Windows installation

If HEIC support is unavailable, the system must reject the file safely, retain it in the error workflow, and explain that conversion to a supported format is required. HEIC support must never rely on an undeclared cloud conversion service.

### Document types

Version 1 may process:

- Supplier invoices.
- Purchase orders.
- Delivery orders.
- Quotations.
- Receipts.
- Other documents intended for later entry into SQL Account.

The system may classify a document as `other` or `unknown` when it cannot assign a supported type confidently. A human reviewer remains responsible for confirming the type and extracted values.

### Processing workflow

For each detected file, Version 1 will:

1. Detect the file in `incoming/`.
2. Confirm that copying or downloading has finished before opening or moving it.
3. Move the file safely into `processing/` without overwriting another file.
4. Validate its type, readability, page count, and duplicate status.
5. Render PDF pages as images when required by the extraction process.
6. Use local AI/OCR to extract structured document data.
7. Preserve the original and create structured JSON plus necessary processing artifacts.
8. Validate required fields, totals, line items, and field-level confidence.
9. Present extracted values and validation findings for human review and correction.
10. After explicit approval, move the original and related artifacts to `completed/`.
11. On failure, move the original and available artifacts to `error/` and record a useful reason.

### Required capabilities

Version 1 includes:

- Local-only processing and storage.
- Folder-based intake and lifecycle management.
- PDF and image processing.
- Multi-page document support.
- Structured, versioned JSON output.
- Human review, correction, and explicit approval.
- Audit logging.
- Duplicate detection.
- Safe, recoverable error handling.

## Explicitly out of scope for Version 1

Version 1 must not include:

- Automatic entry into SQL Account.
- Direct modification of the SQL Account database.
- SQL Account user-interface automation.
- Product alias learning or self-training from corrections.
- Automatic email mailbox access.
- Automatic WhatsApp access.
- A mobile upload application.
- Cloud deployment or cloud-based document processing.

These exclusions are architectural boundaries, not items to implement partially or hide behind disabled defaults.

## Operating principles

- **Human accountability:** AI/OCR output is a proposal. Only explicit human approval marks a document complete.
- **Original preservation:** The original file is never edited. Derived images, JSON, and review data are separate artifacts.
- **Local privacy:** Document content, extracted data, models, logs, and review activity remain on the local system.
- **Safe state transitions:** A document belongs to one lifecycle state at a time, and transitions are recorded.
- **No silent loss:** A failure produces an error record and retains enough material for diagnosis and reprocessing.
- **Traceability:** All artifacts share a stable document identifier and can be traced back to the source file.
- **Conservative automation:** Low-confidence, inconsistent, or ambiguous values are surfaced to the reviewer rather than guessed.

## Version 1 success criteria

Version 1 is successful when a user can place a supported document in `incoming/`, review a locally extracted structured record, correct it where necessary, approve it, and find the original plus related artifacts in `completed/`. Failed or unsupported documents must be retained in `error/` with an understandable reason. Reprocessing or duplicate intake must not silently overwrite existing work.

## Terminology

- **SQL Account:** The external accounting product for which documents are being prepared. It is not integrated in Version 1.
- **Document:** One source file and all pages it contains.
- **Artifact:** A derived file such as a rendered page image, structured JSON record, validation report, or review record.
- **Approval:** An explicit human decision that the reviewed structured data is ready for a future entry process.
- **Duplicate:** A file whose content matches a previously known document, primarily determined through a cryptographic content hash.
- **Extraction status:** The immutable state observed by AI/OCR for a source business value, recorded as `value_status`.
- **Effective status:** The current usability of a business value after human review; it is derived rather than independently stored.
- **Logical lifecycle state:** The authoritative document state recorded in canonical JSON. Lifecycle folders are physical projections of that state.

## Production validation extension

The local production coordinator is a safe orchestration layer around the
Version 1 pipeline. It monitors stable PDFs, records immutable run history, and
projects each processed invoice into exactly one of `READY`, `FAILED`,
`REVIEW`, or `DUPLICATE`. It does not expand Version 1 into SQL Account
integration: it generates evidence and official import files only and never
writes to SQL Account.
