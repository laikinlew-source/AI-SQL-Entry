# Read-Only Export Method Comparison

## Required master data

The acquisition layer needs four complete datasets:

- Suppliers
- Tax Codes
- GL Accounts
- Currencies

Each dataset must be independently identifiable and contain a code plus the
fields needed by the local validator. The local reader accepts CSV, XLSX, and
JSON. SQL Account's actual output format remains a fact to verify rather than
an assumption.

## Available methods

### Official documentation findings

The vendor documents two relevant utilities:

- [XML Import & Export Guide](https://docs.sql.com.my/sqlacc/miscellaneous/import-export-guide)
  describes an external `SQL Financial Accounting Text & XML Import Module V5`
  that exports master files and transactions as XML. Its documented flow is
  `Fast XML Export → choose date/filter → Export → choose location/name → Save`.
- [Excel Import Guide](https://docs.sql.com.my/sqlacc/miscellaneous/acc-xls-mdb-import)
  documents XLS/CSV transaction and master-file import, including the
  `Transactions Data - Get File 3` two-workbook flow. It does not document the
  exact master-data export columns needed by this project.

These are official format/workflow references. Neither page was executed
against the live company in this turn.

### Method A — Built-in SQL Account export

**Status:** `INFERRED`, not live-verified in the current session.

The installed `SQL.DataImport.bpl`, `SQL.oodataimport.bpl`, and `cxExportRS37.bpl`
components provide strong local evidence of data import/export support. Prior
UI discovery exposed `Main Menu`, `Supplier`, `General Ledger`, and `Purchase`,
but did not open a master-data export dialog. Therefore the exact menu labels,
filters, column order, worksheet names, and supported output choices (CSV/XLSX)
are still unknown.

Expected read-only investigation path when a live window is available:

```text
SQL Account main window
  → Supplier / GL / Tools → Maintain Tax / Tools → Maintain Currency
  → built-in Export or Data Export
  → choose XLSX or CSV
  → save one file per master dataset
  → copy files to incoming/master-data
```

No Save/Post/Update action is needed for this path. The export dialog must be
inspected before any click is automated.

### Method B — Official SQL Account API GET

**Status:** `VERIFIED-VENDOR` for documented GET capability; not enabled locally.

Official documentation verifies read-only Purchase Invoice GET patterns and a
50-record request limit. The local installation contains API libraries, but no
API service, configuration, Postman collection, or verified listener was found.
The exact master-data GET endpoints, entitlement, authentication setup, and
least-privilege permissions are not established.

This method is the strongest automation candidate only after a vendor-supported
non-production setup and contract review. No credentials or authenticated
request may be created under the current authorization.

### Method C — Direct SQL/Firebird query

**Status:** `EXCLUDED`.

It would bypass the approved read-only source boundary, depend on undocumented
schema details, and risk locking or exposing accounting data. It is not an
acceptable fallback.

### Method D — Manual export hand-off

**Status:** `IMPLEMENTED` and safe fallback.

An authorized operator exports the four datasets using SQL Account's own UI and
places the files in `incoming/master-data`. The project then performs all
parsing, validation, duplicate checks, backups, snapshot replacement, and
readiness reporting locally. This is the smallest manual step while the live
export dialog remains unavailable to automation.

## Comparison

| Criterion | Built-in export | Official API GET | Direct database | Manual hand-off |
| --- | --- | --- | --- | --- |
| Read-only | Yes if export only | Yes for GET | Technically read-only but unsafe/unsupported | Yes |
| Automation | Potentially high | High after setup | High but prohibited | Low, only four exports |
| Official contract | Needs live verification | Partial; master-data contract unknown | No | Depends on UI export |
| Credentials/service | None | Required and currently absent | DB access required | None for project |
| Version drift risk | Medium | Medium, vendor contract dependent | High | Medium |
| Current readiness | Blocked by unavailable UI | Blocked by entitlement/setup | Not allowed | Ready now when files are supplied |

## Recommendation

1. **Immediate production workflow:** Method D. Ask for only the four exported
   files, keep them local, and let the existing acquisition CLI validate them.
2. **Preferred future automation:** Method A if a live, built-in export dialog
   can be observed and its output contract captured. It avoids credentials and
   server changes.
3. **Long-term integration candidate:** Method B for read-only synchronization
   after vendor entitlement, endpoint, authentication, and audit controls are
   documented.

Do not automate an export click until the actual dialog is visible and the
target file path, format, and scope are freshly verified.
