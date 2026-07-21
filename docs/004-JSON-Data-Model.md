# AI-SQL-Entry Version 1 Canonical JSON Data Model

## Purpose and scope

This document defines schema version `1.0.0` of the canonical JSON payload for one processed business document. The payload covers the document's source, lifecycle, extracted business values, validation, human review, audit references, and terminal error state.

JSON is the canonical Version 1 output. It is the durable boundary between local document processing and any future integration phase. It is not a SQL Account import format and contains no SQL Account-specific identifiers or automation state.

The rules in this document are normative for Version 1. An implementation schema may add mechanical constraints, but it must not weaken the preservation, review, privacy, or scope boundaries defined here and in documents 001 through 003.

## Design principles

1. **Canonical JSON:** Each processed document has one canonical JSON payload that travels with its artifact set.
2. **Explicit schema version:** Every persisted payload contains `schema_version`. Version 1 begins at `1.0.0`.
3. **Separated value layers:** Original machine output, normalized machine output, and human-reviewed values remain distinct. Review never overwrites or removes extraction evidence.
4. **Explicit value state:** Business fields use `value_status`; `null` alone never means missing, unreadable, not applicable, uncertain, or empty.
5. **Decimal-safe precision:** Monetary values and quantities that require precision are JSON strings, not binary floating-point numbers.
6. **Traceable provenance:** Extracted business values identify their source page, source location when available, extractor, confidence, and extraction time.
7. **Human authority:** The reviewed layer records acceptance or correction, while preserving what the extractor produced.
8. **Stable references:** Validation findings, correction records, and audit references identify fields with RFC 6901 JSON Pointer paths.
9. **Lean technical metadata:** System-generated metadata such as identifiers, lifecycle state, hashes, and system timestamps is represented directly rather than wrapped in extraction envelopes.
10. **Local-only privacy:** The model contains local artifact references and local extractor metadata only. It does not include cloud processing or automatic mailbox/messaging integration state.

## Common conventions

### Timestamps

All persisted timestamps use RFC 3339 UTC strings with a `Z` suffix, for example `2026-07-21T04:15:30Z`. A user interface may display local time without changing the stored value.

### JSON Pointer

Field references use RFC 6901 JSON Pointer syntax. Examples are:

- `/document_details/document_number`
- `/financial_summary/tax`
- `/line_items/0/quantity`
- `/parties/issuer/tax_number`

The empty string refers to the payload root. Array positions are zero-based. Persisted references must escape `~` as `~0` and `/` as `~1` when those characters occur in property names.

### Decimal strings

Decimal-safe values use a plain base-10 string such as `"10"`, `"2.500"`, `"475.00"`, or `"-5.00"`. Scientific notation, grouping separators, and currency symbols are not allowed in normalized decimal strings. The raw source text remains available in `extracted.raw_value`.

### Money

A normalized or reviewed monetary value uses:

```json
{
  "value": "475.00",
  "currency": "MYR"
}
```

`value` is a decimal string. `currency` is an uppercase ISO 4217 code when known. If the source currency is unknown, the surrounding field's `value_status` must communicate uncertainty and the currency may be `null`; `null` must not be the only indicator of the condition.

### Value status

Every extracted business-value envelope has one of these `value_status` values:

| Value | Meaning |
| --- | --- |
| `present` | A usable source value was found and normalized. |
| `missing` | The field was expected or sought but no source value was found. |
| `unreadable` | The source appears to contain the field, but it cannot be read reliably. |
| `not_applicable` | The field does not apply to this document or document type. |
| `uncertain` | A candidate value exists, but ambiguity or confidence prevents treating it as present. |
| `empty` | The source explicitly shows the field with no value. |

For `missing`, `unreadable`, `not_applicable`, or `empty`, `normalized_value` is normally `null`; the explicit status carries the meaning. For `uncertain`, `normalized_value` may contain the best candidate, but consumers must not treat it as accepted fact.

## Canonical field envelope

The field envelope applies primarily to business values read or inferred from the source document. It does not wrap `schema_version`, `document_id`, `lifecycle_status`, hashes, system timestamps, artifact paths, processing-stage records, or similar technical metadata.

```json
{
  "value_status": "present",
  "extracted": {
    "raw_value": "RM 492.00",
    "normalized_value": {
      "value": "492.00",
      "currency": "MYR"
    },
    "confidence": 0.98,
    "source_page": 1,
    "source_location": {
      "type": "bounding_box",
      "coordinate_space": "normalized",
      "x": 0.72,
      "y": 0.84,
      "width": 0.19,
      "height": 0.04
    },
    "extractor": {
      "name": "LocalVisionOCR",
      "version": "1.4.0"
    },
    "extracted_at": "2026-07-21T04:15:30Z"
  },
  "reviewed": {
    "status": "accepted",
    "value": {
      "value": "492.00",
      "currency": "MYR"
    },
    "reviewer": {
      "reviewer_id": "local-user-01",
      "display_name": "Example Reviewer"
    },
    "reviewed_at": "2026-07-21T04:22:00Z",
    "reason": null,
    "notes": null
  }
}
```

### Extracted layer

The `extracted` object is immutable extraction evidence:

| Field | Responsibility |
| --- | --- |
| `raw_value` | OCR/AI value as produced, before normalization. It may be a string, object, array, or `null` when `value_status` explains absence. |
| `normalized_value` | Typed, normalized machine interpretation. Monetary and precision-sensitive decimal values use strings. |
| `confidence` | Number from `0.0` through `1.0`, or `null` if the extractor cannot supply confidence. |
| `source_page` | One-based page number, or `null` when no page can be identified. |
| `source_location` | Bounding box, polygon, text span, or `null` when unavailable. The coordinate space must be named. |
| `extractor` | Local extractor name and version responsible for this field result. |
| `extracted_at` | UTC extraction timestamp. |

An extracted object may add narrowly scoped provenance such as `evidence` when the field type requires it. Such additions do not replace any required extracted-layer member.

Review operations must not edit, replace, or delete any extracted-layer member.

### Reviewed layer

`reviewed.status` is one of:

- `not_reviewed`
- `accepted`
- `corrected`
- `rejected`

When `accepted`, `reviewed.value` records the accepted value and normally matches `extracted.normalized_value`. When `corrected`, `reviewed.value` contains the human-corrected value and `reason` or `notes` explains the change where appropriate. When `not_reviewed`, review identity, time, and value may be `null`. A rejection may use a `null` reviewed value only when the explicit review status and document-level decision explain the outcome.

`reviewer` contains a stable local identifier and display name when available. Version 1 does not require an identity-management system.

The effective approved value is `reviewed.value` for an accepted or corrected field. Before approval, downstream systems must not infer approval from a normalized value alone.

## Top-level document structure

Every canonical payload contains these top-level members:

| Member | Responsibility |
| --- | --- |
| `schema_version` | Semantic version of this canonical payload contract. Version 1 starts at `1.0.0`. |
| `document_id` | Stable, filesystem-safe, globally unique identifier shared by the original and all artifacts. |
| `document_type` | Field envelope containing classification, confidence, evidence, and review. |
| `lifecycle_status` | Technical state: `incoming`, `processing`, `awaiting_review`, `completed`, or `error`. |
| `source` | Original-file metadata, channel, hash, page count, and artifact references. |
| `processing` | Pipeline version, attempt, stage history, and system timestamps. |
| `parties` | Issuer/supplier, recipient/customer, billing, and delivery party business values. |
| `document_details` | Document numbers, references, dates, currency, and payment terms. |
| `financial_summary` | Document-level monetary totals. |
| `line_items` | Ordered business lines with extracted and reviewed values. |
| `extraction` | Document-level extraction-run metadata and raw-output references. |
| `validation` | Validation status and findings with JSON Pointer field paths. |
| `review` | Document-level review state, decision, corrections, reviewer, and timestamps. |
| `audit_references` | References to local audit events and affected JSON Pointer paths. |
| `error` | `null` for a non-error document, or safe terminal error information. |

Top-level members are retained even when empty or not yet populated so that consumers can validate payload shape consistently.

## Source metadata

`source` is system metadata and is not wrapped in field envelopes. It contains:

| Member | Type and rules |
| --- | --- |
| `original_filename` | Filename as received, including extension. |
| `original_extension` | Lowercase extension including the leading dot, such as `.pdf`. |
| `mime_type` | Detected MIME type, not merely the extension-derived guess. |
| `sha256` | Lowercase 64-character SHA-256 hash of the immutable original bytes. |
| `source_channel` | `manual_copy`, `email_download`, `whatsapp_download`, `scan`, or `mobile_photo`. |
| `received_at` | UTC time at which the stable file was accepted for processing. |
| `page_count` | Positive integer after successful readability/page validation. |
| `original_file_reference` | Artifact-relative path to the immutable original; not an external URL. |
| `rendered_page_references` | Ordered array of artifact-relative page-image references. Empty when rendering was not required. |

The source channel records how the user obtained or placed the file. It does not contain mailbox identifiers, WhatsApp chat data, authentication state, or automatic integration metadata.

## Document classification

`document_type.extracted.normalized_value` and an accepted/corrected `document_type.reviewed.value` use one of:

- `supplier_invoice`
- `purchase_order`
- `delivery_order`
- `quotation`
- `receipt`
- `other`
- `unknown`

Classification confidence uses the standard extracted-layer confidence. The normalized value remains the classification enum string. Evidence, when available, is stored in an optional `extracted.evidence` array or in document-level extraction details. Evidence must be concise and must not duplicate the full document text.

## Parties

`parties` defines four role members:

- `issuer`
- `recipient`
- `billing_party`
- `delivery_party`

Each role has its own `value_status`. A present role may contain field envelopes for:

- `name`
- `registration_number`
- `tax_number`
- `address`
- `phone`
- `email`

No party field is universally required. Requirements depend on document type and validation policy. A non-applicable role may contain only `value_status: "not_applicable"`; it must not be represented by unexplained `null`.

Addresses should normalize into an object with available components such as `lines`, `city`, `state`, `postal_code`, and `country_code`, while preserving the raw printed address in the extracted layer.

## Document details

`document_details` supports field envelopes for:

- `document_number`
- `reference_numbers`
- `issue_date`
- `due_date`
- `delivery_date`
- `purchase_order_number`
- `currency`
- `payment_terms`

Normalized dates use ISO 8601 calendar form `YYYY-MM-DD` when the full date is known. Ambiguous or partial dates use `value_status: "uncertain"` and preserve the raw text. Currency uses an uppercase ISO 4217 code when identified.

`reference_numbers` normalizes to an array whose elements contain a reference `type` and `value`. The entire array remains inside a field envelope so its raw source and review state are retained.

## Financial summary

`financial_summary` supports these monetary field envelopes:

- `subtotal`
- `discount`
- `tax`
- `rounding`
- `shipping_or_additional_charges`
- `grand_total`
- `amount_paid`
- `balance_due`

Every present normalized or reviewed monetary value uses the Money object with `value` and `currency`. Zero is a present value such as `{"value": "0.00", "currency": "MYR"}`; it is not missing or empty.

## Line items

`line_items` is an ordered array. Each element has a technical `line_item_id` and field envelopes for:

- `sequence_number`
- `description`
- `supplier_item_code`
- `quantity`
- `unit_of_measure`
- `unit_price`
- `discount`
- `tax_rate`
- `tax_amount`
- `line_subtotal`
- `line_total`
- `source_page`
- `source_location`
- `confidence`

Precision-sensitive normalized quantities and rates use decimal strings. Monetary line fields use Money objects. `source_location` may normalize to a bounding box or polygon. `confidence` may normalize to a number from `0.0` through `1.0`; it does not replace the confidence stored on each field's extracted layer.

Line items must not contain SQL Account product identifiers, item mappings, alias candidates, learned aliases, or alias-learning state.

## Extraction representation

The field envelope carries field-level extraction evidence. The top-level `extraction` object carries run-level metadata:

- `run_id`
- `status`
- `started_at`
- `completed_at`
- `primary_extractor` with local name and version
- `supporting_extractors` with local names and versions
- `raw_output_references` as artifact-relative paths
- `extracted_field_paths` as JSON Pointer paths

Raw provider output is optional and is stored only when required for diagnosis and permitted by local retention policy. It remains a local artifact reference, not embedded cloud metadata.

## Validation findings

`validation.status` is one of `not_run`, `passed`, `passed_with_warnings`, `failed`, or `blocked`. The object also records `validated_at`, `ruleset_version`, and `findings`.

Finding severity is one of:

- `info`
- `warning`
- `error`
- `blocking`

Each finding contains:

| Member | Responsibility |
| --- | --- |
| `finding_id` | Stable identifier within the document. |
| `severity` | One of the four severity values. |
| `code` | Stable machine-readable rule code. |
| `message` | Safe, actionable human-readable explanation. |
| `field_path` | JSON Pointer to the affected field or nearest relevant object. |
| `expected` | Expected value or rule description, without secrets. |
| `actual` | Observed value needed to explain the finding, minimized where sensitive. |
| `retryable` | Boolean indicating whether rerunning processing may help. |
| `operator_action` | Suggested human action or `null` when none is appropriate. |
| `resolution_status` | `open`, `accepted`, `corrected`, or `dismissed`. |
| `resolved_by_correction_id` | Correction identifier or `null`. |

A `blocking` finding prevents approval until resolved. An `error` requires correction or explicit policy handling. Warnings and information remain visible to the reviewer.

## Human review

The document-level `review` object contains:

- `status`: `not_started`, `in_progress`, `approved`, or `rejected`
- `decision`: `approved`, `rejected`, or `null` before a decision
- `reviewer`: local identity when available
- `started_at`
- `completed_at`
- `notes`
- `corrections`

Each correction contains:

- `correction_id`
- `field_path` as JSON Pointer
- `original_extracted_value`
- `original_normalized_value`
- `corrected_value`
- `reason`
- `reviewer`
- `corrected_at`

The field-level reviewed layer contains the current review result. The document-level correction list records the correction event. Neither may change the extracted layer. A correction path must resolve to a field envelope in the same payload.

Approval is explicit. A payload must not use `lifecycle_status: "completed"` unless `review.status` and `review.decision` are both `approved` and no unresolved blocking finding remains.

## Audit references

`audit_references` links the payload to append-only local audit events without copying entire logs into the canonical JSON. Each entry contains:

- `event_id`
- `event_type`
- `field_path` as JSON Pointer, using the empty string for a document-wide event
- `event_at`
- `log_reference` as an artifact-relative local reference

Audit references must not contain secrets, authentication tokens, full document text, cloud trace identifiers, mailbox state, or WhatsApp state.

## Error representation

For a document without a terminal error, `error` is `null` because `lifecycle_status` and the member name make the absence unambiguous. For `lifecycle_status: "error"`, `error` is an object containing:

- `error_id`
- `category`: `intake`, `unsupported_format`, `unreadable_file`, `duplicate`, `rendering`, `extraction`, `validation`, `review_rejection`, `storage`, or `internal`
- `stage`
- `occurred_at`
- `user_message`: safe and actionable
- `technical_code`: stable diagnostic code
- `technical_message`: minimized diagnostic detail
- `retryable`
- `operator_action`
- `related_field_path` as JSON Pointer or `null`

The error object must not store stack traces containing sensitive payloads, secrets, credentials, full OCR text, unnecessary personal data, external service tokens, or machine-specific details that do not help local diagnosis. Detailed stack traces, when required, belong in protected local logs referenced through `audit_references`.

## Complete fictional supplier-invoice example

All names, identifiers, addresses, values, and references below are fictional and exist only to demonstrate the schema. The example includes accepted, corrected, missing, unreadable, and validation-linked values.

```json
{
  "schema_version": "1.0.0",
  "document_id": "019c7d42-6c91-7a31-b257-6e8420f00001",
  "document_type": {
    "value_status": "present",
    "extracted": {
      "raw_value": "TAX INVOICE",
      "normalized_value": "supplier_invoice",
      "confidence": 0.99,
      "source_page": 1,
      "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.05, "width": 0.24, "height": 0.05},
      "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"},
      "evidence": ["title: TAX INVOICE", "supplier and amount-due sections present"],
      "extracted_at": "2026-07-21T04:15:30Z"
    },
    "reviewed": {"status": "accepted", "value": "supplier_invoice", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}
  },
  "lifecycle_status": "completed",
  "source": {
    "original_filename": "Fictional_Meridian_Invoice_INV-2026-0042.pdf",
    "original_extension": ".pdf",
    "mime_type": "application/pdf",
    "sha256": "9a3d9e85c1de3d5694c512869c234bcc5d1f18c0f93417f54ad2c7e7c0a4b812",
    "source_channel": "email_download",
    "received_at": "2026-07-21T04:14:02Z",
    "page_count": 2,
    "original_file_reference": "original/Fictional_Meridian_Invoice_INV-2026-0042.pdf",
    "rendered_page_references": ["pages/page-0001.png", "pages/page-0002.png"]
  },
  "processing": {
    "pipeline_version": "0.1.0",
    "attempt_number": 1,
    "started_at": "2026-07-21T04:14:10Z",
    "completed_at": "2026-07-21T04:23:05Z",
    "current_stage": "completed",
    "stage_history": [
      {"stage": "intake_validation", "started_at": "2026-07-21T04:14:10Z", "completed_at": "2026-07-21T04:14:18Z", "status": "succeeded"},
      {"stage": "rendering", "started_at": "2026-07-21T04:14:18Z", "completed_at": "2026-07-21T04:14:35Z", "status": "succeeded"},
      {"stage": "extraction", "started_at": "2026-07-21T04:14:35Z", "completed_at": "2026-07-21T04:15:30Z", "status": "succeeded"},
      {"stage": "validation", "started_at": "2026-07-21T04:15:30Z", "completed_at": "2026-07-21T04:15:34Z", "status": "completed_with_findings"},
      {"stage": "human_review", "started_at": "2026-07-21T04:18:00Z", "completed_at": "2026-07-21T04:22:00Z", "status": "approved"},
      {"stage": "archival", "started_at": "2026-07-21T04:22:00Z", "completed_at": "2026-07-21T04:23:05Z", "status": "succeeded"}
    ]
  },
  "parties": {
    "issuer": {
      "value_status": "present",
      "name": {"value_status": "present", "extracted": {"raw_value": "Fictional Meridian Office Supplies Sdn. Bhd.", "normalized_value": "Fictional Meridian Office Supplies Sdn. Bhd.", "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.08, "width": 0.46, "height": 0.04}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "Fictional Meridian Office Supplies Sdn. Bhd.", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:00Z", "reason": null, "notes": null}},
      "registration_number": {"value_status": "present", "extracted": {"raw_value": "209999999999", "normalized_value": "209999999999", "confidence": 0.96, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.13, "width": 0.22, "height": 0.02}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "209999999999", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:05Z", "reason": null, "notes": "Fictional registration number."}},
      "tax_number": {"value_status": "unreadable", "extracted": {"raw_value": "TAX: MY-??82?", "normalized_value": null, "confidence": 0.21, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.30, "y": 0.13, "width": 0.20, "height": 0.02}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": null, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:10Z", "reason": "The printed tax number remains unreadable in the source.", "notes": "Accepted as unreadable; not required by the current supplier-invoice rule set."}},
      "address": {"value_status": "present", "extracted": {"raw_value": "18 Example Commerce Park, 50000 Kuala Lumpur, MY", "normalized_value": {"lines": ["18 Example Commerce Park"], "city": "Kuala Lumpur", "state": null, "postal_code": "50000", "country_code": "MY"}, "confidence": 0.97, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.16, "width": 0.45, "height": 0.05}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"lines": ["18 Example Commerce Park"], "city": "Kuala Lumpur", "state": null, "postal_code": "50000", "country_code": "MY"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:15Z", "reason": null, "notes": null}},
      "phone": {"value_status": "missing", "extracted": {"raw_value": null, "normalized_value": null, "confidence": null, "source_page": null, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "not_reviewed", "value": null, "reviewer": null, "reviewed_at": null, "reason": null, "notes": null}},
      "email": {"value_status": "present", "extracted": {"raw_value": "billing@meridian-office.example", "normalized_value": "billing@meridian-office.example", "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.22, "width": 0.32, "height": 0.02}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "billing@meridian-office.example", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:20Z", "reason": null, "notes": "Reserved example domain."}}
    },
    "recipient": {
      "value_status": "present",
      "name": {"value_status": "present", "extracted": {"raw_value": "Fictional Northstar Trading Sdn. Bhd.", "normalized_value": "Fictional Northstar Trading Sdn. Bhd.", "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.29, "width": 0.43, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "Fictional Northstar Trading Sdn. Bhd.", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:25Z", "reason": null, "notes": null}},
      "address": {"value_status": "present", "extracted": {"raw_value": "7 Sample Industrial Road, 43000 Kajang, MY", "normalized_value": {"lines": ["7 Sample Industrial Road"], "city": "Kajang", "state": "Selangor", "postal_code": "43000", "country_code": "MY"}, "confidence": 0.95, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.06, "y": 0.33, "width": 0.39, "height": 0.04}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"lines": ["7 Sample Industrial Road"], "city": "Kajang", "state": "Selangor", "postal_code": "43000", "country_code": "MY"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:30Z", "reason": null, "notes": null}}
    },
    "billing_party": {"value_status": "not_applicable"},
    "delivery_party": {"value_status": "not_applicable"}
  },
  "document_details": {
    "document_number": {"value_status": "present", "extracted": {"raw_value": "INV-2026-0042", "normalized_value": "INV-2026-0042", "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.74, "y": 0.14, "width": 0.18, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "INV-2026-0042", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:35Z", "reason": null, "notes": null}},
    "reference_numbers": {"value_status": "present", "extracted": {"raw_value": "Customer Ref: REF-EXAMPLE-77", "normalized_value": [{"type": "customer_reference", "value": "REF-EXAMPLE-77"}], "confidence": 0.94, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.26, "width": 0.24, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": [{"type": "customer_reference", "value": "REF-EXAMPLE-77"}], "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:40Z", "reason": null, "notes": null}},
    "issue_date": {"value_status": "present", "extracted": {"raw_value": "18/07/2026", "normalized_value": "2026-07-18", "confidence": 0.97, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.75, "y": 0.18, "width": 0.16, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "2026-07-18", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:45Z", "reason": null, "notes": null}},
    "due_date": {"value_status": "missing", "extracted": {"raw_value": null, "normalized_value": null, "confidence": null, "source_page": null, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "not_reviewed", "value": null, "reviewer": null, "reviewed_at": null, "reason": null, "notes": "No due date is printed."}},
    "delivery_date": {"value_status": "not_applicable", "extracted": {"raw_value": null, "normalized_value": null, "confidence": null, "source_page": null, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "not_reviewed", "value": null, "reviewer": null, "reviewed_at": null, "reason": null, "notes": null}},
    "purchase_order_number": {"value_status": "present", "extracted": {"raw_value": "PO-EXAMPLE-1038", "normalized_value": "PO-EXAMPLE-1038", "confidence": 0.96, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.30, "width": 0.24, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "PO-EXAMPLE-1038", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:50Z", "reason": null, "notes": null}},
    "currency": {"value_status": "present", "extracted": {"raw_value": "RM", "normalized_value": "MYR", "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.72, "y": 0.80, "width": 0.05, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "MYR", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:19:55Z", "reason": null, "notes": null}},
    "payment_terms": {"value_status": "present", "extracted": {"raw_value": "Payment within 30 days", "normalized_value": {"description": "Payment within 30 days", "days": 30}, "confidence": 0.93, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.08, "y": 0.72, "width": 0.31, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"description": "Payment within 30 days", "days": 30}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:00Z", "reason": null, "notes": null}}
  },
  "financial_summary": {
    "subtotal": {"value_status": "present", "extracted": {"raw_value": "RM 475.00", "normalized_value": {"value": "475.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.73, "y": 0.58, "width": 0.20, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "475.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:05Z", "reason": null, "notes": null}},
    "discount": {"value_status": "present", "extracted": {"raw_value": "RM 25.00", "normalized_value": {"value": "25.00", "currency": "MYR"}, "confidence": 0.98, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.73, "y": 0.62, "width": 0.20, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "25.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:10Z", "reason": null, "notes": null}},
    "tax": {"value_status": "present", "extracted": {"raw_value": "RM 21.00", "normalized_value": {"value": "21.00", "currency": "MYR"}, "confidence": 0.72, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.73, "y": 0.66, "width": 0.20, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "corrected", "value": {"value": "27.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:10Z", "reason": "The OCR confused the printed digit 7 with 1; line tax amounts total MYR 27.00.", "notes": "Corrected against the visible source and arithmetic."}},
    "rounding": {"value_status": "present", "extracted": {"raw_value": "RM 0.00", "normalized_value": {"value": "0.00", "currency": "MYR"}, "confidence": 0.98, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.73, "y": 0.70, "width": 0.20, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "0.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:15Z", "reason": null, "notes": null}},
    "shipping_or_additional_charges": {"value_status": "present", "extracted": {"raw_value": "Delivery RM 15.00", "normalized_value": {"value": "15.00", "currency": "MYR"}, "confidence": 0.97, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.74, "width": 0.25, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "15.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:20Z", "reason": null, "notes": null}},
    "grand_total": {"value_status": "present", "extracted": {"raw_value": "TOTAL RM 492.00", "normalized_value": {"value": "492.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.70, "y": 0.79, "width": 0.23, "height": 0.04}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "492.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:20Z", "reason": null, "notes": null}},
    "amount_paid": {"value_status": "present", "extracted": {"raw_value": "Paid RM 0.00", "normalized_value": {"value": "0.00", "currency": "MYR"}, "confidence": 0.96, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.73, "y": 0.84, "width": 0.20, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "0.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:25Z", "reason": null, "notes": null}},
    "balance_due": {"value_status": "present", "extracted": {"raw_value": "BALANCE RM 492.00", "normalized_value": {"value": "492.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.70, "y": 0.88, "width": 0.23, "height": 0.04}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "492.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:30Z", "reason": null, "notes": null}}
  },
  "line_items": [
    {
      "line_item_id": "line-001",
      "sequence_number": {"value_status": "present", "extracted": {"raw_value": "1", "normalized_value": 1, "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.48, "width": 0.03, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 1, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:25Z", "reason": null, "notes": null}},
      "description": {"value_status": "present", "extracted": {"raw_value": "A4 Copy Paper, 80gsm", "normalized_value": "A4 Copy Paper, 80 gsm", "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.10, "y": 0.48, "width": 0.35, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "A4 Copy Paper, 80 gsm", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:30Z", "reason": null, "notes": null}},
      "supplier_item_code": {"value_status": "present", "extracted": {"raw_value": "PAPER-A4-80", "normalized_value": "PAPER-A4-80", "confidence": 0.96, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.46, "y": 0.48, "width": 0.15, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "PAPER-A4-80", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:35Z", "reason": null, "notes": null}},
      "quantity": {"value_status": "present", "extracted": {"raw_value": "10", "normalized_value": "10", "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.62, "y": 0.48, "width": 0.05, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "10", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:40Z", "reason": null, "notes": null}},
      "unit_of_measure": {"value_status": "present", "extracted": {"raw_value": "REAM", "normalized_value": "ream", "confidence": 0.97, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.48, "width": 0.06, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "ream", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:45Z", "reason": null, "notes": null}},
      "unit_price": {"value_status": "present", "extracted": {"raw_value": "18.50", "normalized_value": {"value": "18.50", "currency": "MYR"}, "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.75, "y": 0.48, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "18.50", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:50Z", "reason": null, "notes": null}},
      "discount": {"value_status": "present", "extracted": {"raw_value": "5.00", "normalized_value": {"value": "5.00", "currency": "MYR"}, "confidence": 0.96, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.83, "y": 0.48, "width": 0.06, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "5.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:20:55Z", "reason": null, "notes": null}},
      "tax_rate": {"value_status": "present", "extracted": {"raw_value": "6%", "normalized_value": "6.00", "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.90, "y": 0.48, "width": 0.04, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "6.00", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:00Z", "reason": null, "notes": "Percent."}},
      "tax_amount": {"value_status": "present", "extracted": {"raw_value": "10.80", "normalized_value": {"value": "10.80", "currency": "MYR"}, "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.84, "y": 0.52, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "10.80", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:05Z", "reason": null, "notes": null}},
      "line_subtotal": {"value_status": "present", "extracted": {"raw_value": "185.00", "normalized_value": {"value": "185.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.91, "y": 0.52, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "185.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:10Z", "reason": null, "notes": "Before discount and tax."}},
      "line_total": {"value_status": "present", "extracted": {"raw_value": "190.80", "normalized_value": {"value": "190.80", "currency": "MYR"}, "confidence": 0.99, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.91, "y": 0.56, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "190.80", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:15Z", "reason": null, "notes": "After discount and tax."}},
      "source_page": {"value_status": "present", "extracted": {"raw_value": "1", "normalized_value": 1, "confidence": 1.0, "source_page": 1, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 1, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:20Z", "reason": null, "notes": null}},
      "source_location": {"value_status": "present", "extracted": {"raw_value": null, "normalized_value": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.47, "width": 0.93, "height": 0.10}, "confidence": 0.98, "source_page": 1, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.47, "width": 0.93, "height": 0.10}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.47, "width": 0.93, "height": 0.10}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:25Z", "reason": null, "notes": null}},
      "confidence": {"value_status": "present", "extracted": {"raw_value": null, "normalized_value": 0.98, "confidence": 1.0, "source_page": 1, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 0.98, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:30Z", "reason": null, "notes": "Aggregate confidence for line 1."}}
    },
    {
      "line_item_id": "line-002",
      "sequence_number": {"value_status": "present", "extracted": {"raw_value": "2", "normalized_value": 2, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.12, "width": 0.03, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 2, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:35Z", "reason": null, "notes": null}},
      "description": {"value_status": "present", "extracted": {"raw_value": "Fictional Laser Toner Cartridge", "normalized_value": "Fictional Laser Toner Cartridge", "confidence": 0.97, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.10, "y": 0.12, "width": 0.35, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "Fictional Laser Toner Cartridge", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:40Z", "reason": null, "notes": null}},
      "supplier_item_code": {"value_status": "present", "extracted": {"raw_value": "TONER-EX-42", "normalized_value": "TONER-EX-42", "confidence": 0.95, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.46, "y": 0.12, "width": 0.15, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "TONER-EX-42", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:45Z", "reason": null, "notes": null}},
      "quantity": {"value_status": "present", "extracted": {"raw_value": "2", "normalized_value": "2", "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.62, "y": 0.12, "width": 0.05, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "2", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:50Z", "reason": null, "notes": null}},
      "unit_of_measure": {"value_status": "present", "extracted": {"raw_value": "UNIT", "normalized_value": "unit", "confidence": 0.98, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.68, "y": 0.12, "width": 0.06, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "unit", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:21:55Z", "reason": null, "notes": null}},
      "unit_price": {"value_status": "present", "extracted": {"raw_value": "145.00", "normalized_value": {"value": "145.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.75, "y": 0.12, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "145.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}},
      "discount": {"value_status": "present", "extracted": {"raw_value": "20.00", "normalized_value": {"value": "20.00", "currency": "MYR"}, "confidence": 0.97, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.83, "y": 0.12, "width": 0.06, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "20.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}},
      "tax_rate": {"value_status": "present", "extracted": {"raw_value": "6%", "normalized_value": "6.00", "confidence": 0.98, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.90, "y": 0.12, "width": 0.04, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": "6.00", "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": "Percent."}},
      "tax_amount": {"value_status": "present", "extracted": {"raw_value": "16.20", "normalized_value": {"value": "16.20", "currency": "MYR"}, "confidence": 0.98, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.84, "y": 0.16, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "16.20", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}},
      "line_subtotal": {"value_status": "present", "extracted": {"raw_value": "290.00", "normalized_value": {"value": "290.00", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.91, "y": 0.16, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "290.00", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": "Before discount and tax."}},
      "line_total": {"value_status": "present", "extracted": {"raw_value": "286.20", "normalized_value": {"value": "286.20", "currency": "MYR"}, "confidence": 0.99, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.91, "y": 0.20, "width": 0.07, "height": 0.03}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"value": "286.20", "currency": "MYR"}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": "After discount and tax."}},
      "source_page": {"value_status": "present", "extracted": {"raw_value": "2", "normalized_value": 2, "confidence": 1.0, "source_page": 2, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 2, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}},
      "source_location": {"value_status": "present", "extracted": {"raw_value": null, "normalized_value": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.11, "width": 0.93, "height": 0.10}, "confidence": 0.97, "source_page": 2, "source_location": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.11, "width": 0.93, "height": 0.10}, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": {"type": "bounding_box", "coordinate_space": "normalized", "x": 0.05, "y": 0.11, "width": 0.93, "height": 0.10}, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": null}},
      "confidence": {"value_status": "present", "extracted": {"raw_value": null, "normalized_value": 0.97, "confidence": 1.0, "source_page": 2, "source_location": null, "extractor": {"name": "LocalVisionOCR", "version": "1.4.0"}, "extracted_at": "2026-07-21T04:15:30Z"}, "reviewed": {"status": "accepted", "value": 0.97, "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"}, "reviewed_at": "2026-07-21T04:22:00Z", "reason": null, "notes": "Aggregate confidence for line 2."}}
    }
  ],
  "extraction": {
    "run_id": "extract-run-example-0001",
    "status": "succeeded",
    "started_at": "2026-07-21T04:14:35Z",
    "completed_at": "2026-07-21T04:15:30Z",
    "primary_extractor": {"name": "LocalVisionOCR", "version": "1.4.0"},
    "supporting_extractors": [{"name": "LocalPdfText", "version": "0.9.2"}],
    "raw_output_references": ["extraction/raw-output.json"],
    "extracted_field_paths": ["/document_type", "/parties/issuer/name", "/parties/issuer/tax_number", "/document_details/document_number", "/document_details/due_date", "/financial_summary/tax", "/financial_summary/grand_total", "/line_items/0", "/line_items/1"]
  },
  "validation": {
    "status": "passed_with_warnings",
    "validated_at": "2026-07-21T04:21:40Z",
    "ruleset_version": "supplier-invoice-1.0.0",
    "findings": [
      {
        "finding_id": "finding-001",
        "severity": "error",
        "code": "FINANCIAL.TAX_TOTAL_MISMATCH",
        "message": "The extracted tax does not equal the sum of line-item tax amounts.",
        "field_path": "/financial_summary/tax",
        "expected": {"rule": "sum(line_items[*].tax_amount)", "value": {"value": "27.00", "currency": "MYR"}},
        "actual": {"value": "21.00", "currency": "MYR"},
        "retryable": false,
        "operator_action": "Check the printed tax total and correct the field if required.",
        "resolution_status": "corrected",
        "resolved_by_correction_id": "correction-001"
      },
      {
        "finding_id": "finding-002",
        "severity": "warning",
        "code": "PARTY.TAX_NUMBER_UNREADABLE",
        "message": "The issuer tax number is visible but unreadable.",
        "field_path": "/parties/issuer/tax_number",
        "expected": "Readable tax number when present",
        "actual": "Unreadable source text",
        "retryable": false,
        "operator_action": "Confirm whether the tax number is required for this document workflow.",
        "resolution_status": "accepted",
        "resolved_by_correction_id": null
      }
    ]
  },
  "review": {
    "status": "approved",
    "decision": "approved",
    "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"},
    "started_at": "2026-07-21T04:18:00Z",
    "completed_at": "2026-07-21T04:22:00Z",
    "notes": "Fictional example approved after correcting the tax total.",
    "corrections": [
      {
        "correction_id": "correction-001",
        "field_path": "/financial_summary/tax",
        "original_extracted_value": "RM 21.00",
        "original_normalized_value": {"value": "21.00", "currency": "MYR"},
        "corrected_value": {"value": "27.00", "currency": "MYR"},
        "reason": "The OCR confused the printed digit 7 with 1; line-item tax amounts total MYR 27.00.",
        "reviewer": {"reviewer_id": "local-user-01", "display_name": "Example Reviewer"},
        "corrected_at": "2026-07-21T04:21:10Z"
      }
    ]
  },
  "audit_references": [
    {"event_id": "audit-example-001", "event_type": "document_received", "field_path": "", "event_at": "2026-07-21T04:14:02Z", "log_reference": "logs/audit-2026-07-21.jsonl#event=audit-example-001"},
    {"event_id": "audit-example-002", "event_type": "field_corrected", "field_path": "/financial_summary/tax", "event_at": "2026-07-21T04:21:10Z", "log_reference": "logs/audit-2026-07-21.jsonl#event=audit-example-002"},
    {"event_id": "audit-example-003", "event_type": "document_approved", "field_path": "", "event_at": "2026-07-21T04:22:00Z", "log_reference": "logs/audit-2026-07-21.jsonl#event=audit-example-003"}
  ],
  "error": null
}
```

## Schema evolution

`schema_version` follows semantic versioning as `MAJOR.MINOR.PATCH`.

### Patch versions

A patch version clarifies documentation or tightens a constraint without changing the valid data shape or meaning. A `1.0.x` consumer must not require migration solely because of a patch update.

### Minor versions

A minor version makes backward-compatible additions within the same major version. Examples include adding an optional top-level member, optional field-envelope metadata, a new non-breaking validation finding member, or a new enum value only where consumers are required to handle unknown values safely.

Version 1 consumers must:

- Accept later `1.x` payloads when all required `1.0.0` members remain compatible.
- Ignore unknown optional members while preserving them during read-modify-write operations where practical.
- Fail safely with an explicit compatibility error when an unknown enum changes processing safety or approval meaning.

### Major versions

A major version is required for breaking changes, including removing or renaming members, changing member types, changing JSON Pointer targets, altering lifecycle or approval semantics, changing decimal or Money representation, or changing the meaning of existing enum values.

Major-version migration requires an explicit design decision covering:

- Source and target schema versions.
- Deterministic transformation rules.
- Fields that cannot be transformed without human input.
- Validation before and after migration.
- Audit evidence of who or what performed the migration.
- Rollback or preservation strategy.

### Older completed artifacts

Completed and error artifacts remain stored in the schema version with which they were finalized. They are not rewritten silently. Readers must dispatch by `schema_version` and retain support for older completed artifacts, or use an explicit, audited migration that preserves the original JSON alongside the migrated copy. The original completed payload remains readable evidence even after a newer schema becomes current.

## Explicit Version 1 exclusions

The canonical Version 1 model must not contain:

- SQL Account database identifiers, row keys, account codes, or import status.
- SQL Account screen names, control selectors, coordinates, keystrokes, or UI-automation state.
- Product alias-learning state, learned mappings, training labels, or automatic product-match decisions.
- Automatic email mailbox connection, message, folder, credential, or synchronization state.
- Automatic WhatsApp connection, chat, contact, credential, or synchronization state.
- Cloud-service provider, bucket, object, API request, tenant, trace, billing, or deployment metadata.

A manually downloaded email attachment may use `source_channel: "email_download"`, and a manually downloaded WhatsApp file may use `source_channel: "whatsapp_download"`. Those values describe user-mediated provenance only and do not authorize integration state.

## Consistency with the approved architecture

This model implements the documentation boundaries established in documents 001 through 003:

- It is local-only and contains only local artifact and log references.
- It preserves original extraction evidence separately from normalization and review.
- It uses a stable document identifier across source, artifacts, validation, review, and audit.
- It represents multi-page source and rendered-page order explicitly.
- It makes human approval a prerequisite for `completed` lifecycle state.
- It uses SHA-256 for exact duplicate identity without adding alias learning.
- It versions persisted JSON from the first schema.
- It stores money and precision-sensitive quantities as decimal strings.
- It retains safe error and recovery information without secrets or unnecessary sensitive content.
- It does not integrate with SQL Account, email, WhatsApp, mobile upload, cloud processing, or cloud deployment.
