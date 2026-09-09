# SQL Account Knowledge Base

This directory is the permanent, reusable record of SQL Account discovery for
AI-SQL-Entry. It distinguishes facts verified from the installed application,
facts verified from official vendor documentation, and items that remain
unknown. It must be updated when a new SQL Account version, export format, or
workflow is observed.

## Current recommendation

Use a read-only, file-based boundary for Version 1:

1. Obtain Supplier, Tax Code, GL Account, and Currency exports from SQL Account
   using an official built-in export or an officially supported read-only API.
2. Place the files in `incoming/master-data`.
3. Let `ai-sql-master-data-acquire` discover, validate, normalize, back up, and
   replace all four local JSON snapshots only after every dataset passes.
4. Re-run readiness against every canonical invoice and preserve a timestamped
   report history.

Direct database access, SQL Account UI posting, and API writes remain out of
scope. The project never treats an inferred field or an unverified UI behavior
as an implementation contract.

## Documents

| Document | Purpose |
| --- | --- |
| [001-environment-and-capabilities.md](001-environment-and-capabilities.md) | Installed version, evidence sources, menu/navigation findings, and automation limits |
| [002-read-only-export-methods.md](002-read-only-export-methods.md) | Export-method inventory, comparison, and recommendation |
| [003-import-workflow-and-limitations.md](003-import-workflow-and-limitations.md) | Official Get File 3 import boundary and safe workflow diagrams |
| [004-discovery-blocker-and-next-action.md](004-discovery-blocker-and-next-action.md) | Current blocker, alternatives, smallest user action, and troubleshooting |

## Evidence policy

- `VERIFIED-LOCAL` means observed from the installed process, files, or
  accessibility evidence on this machine.
- `VERIFIED-VENDOR` means supported by an official SQL Account source already
  recorded in the repository.
- `INFERRED` means plausible but not an implementation contract.
- `UNKNOWN` means not yet observed or not safely testable.

Sensitive company data, credentials, API keys, database contents, and exported
business records must not be copied into this knowledge base.

Last reviewed: 2026-09-09
