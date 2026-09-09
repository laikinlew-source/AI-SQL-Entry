# Roadmap

## Current milestone: Production validation

- Monitor stable local PDF intake.
- Assign exactly one of `READY`, `FAILED`, `REVIEW`, or `DUPLICATE`.
- Validate against editable local master-data snapshots.
- Produce canonical JSON, evidence reports, and official Get File 3 workbooks.
- Preserve immutable run history, audit provenance, resume state, and dashboards.

## Next milestones

1. UAT with approved real invoices and reviewed ground truth for parser/OCR
   accuracy measurement.
2. Improve extraction rules using confirmed corrections, without automatic alias
   learning or invented values.
3. Evaluate an officially supported SQL Account import handoff after UAT.

## Permanent exclusions

SQL Account database writes, SQL Account UI automation, automatic posting,
cloud deployment, mailbox access, WhatsApp access, and mobile upload remain out
of scope until a separately approved architecture and safety review.
