# Official SQL Account Master-Data Acquisition Methods

**Review date:** 2026-09-09
**Installed build observed:** SQL Account 5.2026.1085.897
**Scope:** read-only acquisition of Supplier, Tax Code, GL Account, and
Currency master data for the local snapshot builder.

This document records the official methods investigated in the requested
priority order. It is an acquisition decision record, not an authorization to
write to SQL Account. No database write, import, posting action, reverse
engineering, or UI automation was performed.

## Safety boundary and evidence classes

- **VERIFIED-LOCAL** — observed from the installed process, registry, files, or
  the current Codex runtime on this computer.
- **VERIFIED-VENDOR** — described by an official SQL Account/eStream source.
- **UNKNOWN** — not safely testable in the current runtime or not specified by
  the vendor documentation reviewed.
- **INFERRED** — a reasonable integration possibility, but not an implementation
  contract until the vendor supplies the current endpoint, schema, or sample.

The project accepts only files or authenticated read-only responses produced by
an official SQL Account mechanism. Direct Firebird/database reads are excluded
even when an official SDK exposes a read-only query helper; any SDK adapter must
use the vendor-supported SDK boundary and keep its output behind the existing
source-independent snapshot builder.

## Executive decision

No fully unattended acquisition path is enabled on this machine today:

- The official REST API is a supported, automatable GET path, but this
  installation has no configured endpoint or credentials and the public API
  material does not publish the four required master-data endpoint contracts.
- The official XML utility explicitly supports master-data export and is the
  safest immediate bulk handoff. Its documented flow is GUI-driven, and no
  supported export command-line switch was found.
- The official SQLAccXLSnMDBImp utility has a documented `-Auto` scheduled
  export mode, but it requires an initial configuration, credentials, and a
  vendor-approved read-only SQL query. The query/schema for all four datasets
  is not documented, so it is not safe to configure automatically now.
- The official SDK Live bridge is the strongest long-term on-premise automation
  candidate, but the SDK package/contract and a Python-compatible runtime are
  not present in the project environment. It must be enabled and validated by
  the vendor before an adapter is implemented.

Accordingly, the recommended sequence is:

1. **Immediate safe acquisition:** use the official XML utility's Fast XML
   Export for the four master datasets and save the result under
   `incoming/master-data`.
2. **Long-term local automation:** obtain the official SDK Live package and
   read-only object/report contract from eStream, then add a narrowly scoped
   acquisition adapter that emits the same files.
3. **Cloud option:** if the company uses SQL Account public/on-premise cloud,
   obtain API entitlement, a read-only credential, and the current master-data
   endpoint contract; implement GET-only retrieval behind the same adapter.
4. **Scheduled file option:** consider SQLAccXLSnMDBImp `-Auto` only after a
   vendor-approved query and a test export prove coverage and stable columns.

## Method 1 — Official SQL Account REST API

### Vendor evidence

- The official [REST API reference](https://wiki.sql.com.my/wiki/Restful_API)
  documents a REST bridge, GET/POST/PUT/DELETE patterns, SigV4 signing, the
  `/agent` endpoint example, pagination/offset, and Python/Node/PHP/C# usage.
- The official [API setup guide](https://docs.sql.com.my/sqlacc/integration/sql-account-api/setup-configuration)
  documents provider credentials and the API-only user behavior when a secret
  key is generated.
- The official [API FAQ](https://docs.sql.com.my/sqlacc/integration/sql-account-api/faq)
  documents authenticated GETs and the 50-record limit. Its published route
  examples are transaction routes such as Purchase Invoice; they are not a
  master-data contract for this project.
- The official [API page](https://sql.com.my/api/) lists supported business
  objects and GET/POST/PUT/DELETE capabilities. A current changelog entry also
  records a Currency API fix, proving that Currency is represented in the API,
  but it does not specify the endpoint or response schema needed here.

### Coverage and assessment

| Dataset | Public endpoint/schema verified? | Read-only GET possible? | Current decision |
| --- | --- | --- | --- |
| Supplier | No | Yes in principle | Requires current vendor contract/Postman collection |
| Tax Code | No | Yes in principle | Requires current vendor contract/Postman collection |
| GL Account | No | Yes in principle | Requires current vendor contract/Postman collection |
| Currency | Object existence indicated by changelog; endpoint/schema not verified | Yes in principle | Requires current vendor contract/Postman collection |

**Local state — VERIFIED-LOCAL:** the installed directory contains API-related
runtime components such as `SQLAcc.API.bpl`, but no configured API listener,
credential, or authenticated endpoint was found. No API call was attempted.
The presence of a DLL/BPL is not proof that an API service is enabled.
The local service inventory found no SQL Account service and no listener on the
common API ports checked; this does not rule out an outbound cloud API, but it
does rule out treating the desktop install as a ready local REST server.

**Why not enabled now:** enabling/licensing the API and obtaining credentials
are external authorization steps. Guessing endpoints or payloads would create
an unsupported contract and could expose sensitive accounting data.

**Decision:** keep an API reader interface in the acquisition boundary, but do
not implement a live adapter until eStream provides the four current GET
contracts (or a current Postman collection) and a sandbox/read-only credential.

## Method 2 — Official XML export

### Vendor evidence

The official [XML Import & Export Guide](https://docs.sql.com.my/sqlacc/miscellaneous/import-export-guide)
documents the external **SQL Financial Accounting Text & XML Import Module V5**
and its **Fast XML Export** flow. The guide explicitly describes exporting
master files and transactions and gives examples including Supplier and
Currency. The official [SQL Text/XML reference](https://wiki.sql.com.my/wiki/SQL_Text_Import)
also describes the external utility and XML export capabilities.

### Coverage and assessment

- **Supplier:** documented as an exportable master category.
- **Currency:** documented as an exportable master category.
- **Tax Code and GL Account:** the public export list does not provide a
  complete, build-specific guarantee for these two categories. They must be
  confirmed in the current Fast XML Export selection or supplied through an
  additional official export.
- **Read-only:** Fast XML Export produces files; it does not import or post
  data. The project must never invoke the utility's import actions.
- **Automation:** the vendor documents the export dialog, destination, and
  filename selection, but no supported XML-export command-line switch was
  found. The documented `SQLAccTxtXMLImp.exe -Auto` switch concerns automatic
  import, not a guaranteed scheduled export.

**Decision:** this is the safest immediate bulk acquisition method. It needs a
one-time operator action because the current Codex runtime cannot expose the
native Windows dialog. The project can then validate the XML, normalize it to
the four local snapshots, back up prior snapshots, and rerun invoice readiness.

## Method 3 — Official command-line or batch export

### SQL Account command-line switches

The official [command-line reference](https://docs.sql.com.my/sqlacc/usage/general/others/command-line)
documents switches for backup, deployment, unit tests, database selection, and
credentials. It does **not** document a Supplier, Tax, GL, or Currency export
switch. A backup is not a master-data export and is not a substitute for this
workflow.

**Decision:** no direct `SQLACC.exe` command-line exporter is available from
the documented interface.

### SQLAccXLSnMDBImp scheduled mode

The official [Excel/CSV import guide](https://docs.sql.com.my/sqlacc/miscellaneous/acc-xls-mdb-import)
documents an **Auto Import** configuration that can run with
`SQLAccXLSnMDBImp.exe -Auto`. With the configured “With Export CSV File” option,
an export folder, date, filename, and SQL query, the utility can create CSV
output on a schedule. This is an official batch-capable path, but it has
important gates:

1. Initial settings and credentials must be configured in the vendor utility.
2. The query is user-supplied; its table/column contract is not published in
   the guide.
3. A bad query could omit records or expose more data than intended.
4. The guide is primarily an import guide; it does not guarantee that one
   configured query covers all four required master datasets.

**Decision:** keep this as a future scheduled-export option only after eStream
approves read-only queries, output columns, and the service account. Do not
create or execute a query automatically in this project.

**Local state — VERIFIED-LOCAL:** the documented default utility directory
`C:\eStream\Utilities` is not present on this machine, so
`SQLAccXLSnMDBImp.exe` is not locally available for a safe dry run.

## Method 4 — Official SDK / integration tools

### Vendor evidence

The official [SQL Accounting linking guide](https://wiki.sql.com.my/wiki/SQL_Accounting_Linking)
compares the supported Restful API, SDK Live, SQLAccXLSnMDBImp, SQL XML, and
SQL Text methods by deployment environment. It identifies the relevant SQL
Account master locations: Supplier, GL Account, Currency, and Tax.

The official [SDK Live reference](https://wiki.sql.com.my/wiki/SDK_Live)
describes a direct live bridge with retrieve/get-info support and automation.
Vendor SDK search material also documents master objects such as `AP_SUPPLIER`
and `TAX`, `LASTMODIFIED` fields, and a read-only GL-account report example
using the vendor's `SQLAcc.BizApp` boundary. These examples establish that a
vendor-supported read-only bridge exists; they do not provide a complete,
version-pinned four-dataset schema for this project.

### Local state and constraints

**VERIFIED-LOCAL:** the installed application contains API and integration
runtime components, but no SDK package/CHM contract or Python COM runtime is
available in the project environment. The COM registration of `SQLAcc.BizApp`
is not treated as permission to probe it: invoking undocumented methods or
queries would violate the no-reverse-engineering boundary.

**Decision:** SDK Live is the best long-term on-premise automation candidate,
provided eStream supplies:

- the SDK package and version compatibility for build 5.2026.1085.897;
- documented read-only object/report names and field mappings for all four
  datasets;
- a read-only service/user permission model;
- a supported Python/COM integration recipe or a vendor-supported helper
  process; and
- a sandbox or test company for deterministic verification.

The future adapter must emit files/responses into the existing acquisition
interface and must not expose posting, import, or update calls to business
logic.

## Method 5 — Built-in SQL Account export menus

### Official locations

Official user documentation places the master data at:

- **Supplier:** Supplier → Maintain Supplier
- **GL Account:** GL → Maintain Account
- **Tax Code:** Tools → Maintain Tax
- **Currency:** Tools → Maintain Currency

These locations are recorded in the vendor [linking guide](https://wiki.sql.com.my/wiki/SQL_Accounting_Linking)
and related official user guides. Exact export button labels, column order, and
current-build output formats were not verified because the native SQL Account
window is not exposed to this Codex runtime.

### Decision

Built-in export is a safe read-only fallback when the XML utility does not
expose a required dataset. It is not a reliable automation contract until one
real export artifact is inspected and its schema is captured in tests. No UI
automation or guessed coordinates are permitted.

## Comparison matrix

| Method | Official | Read-only boundary | Automated now | Coverage certainty | Main blocker | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| REST API GET | Yes | Strong | No | Medium/low for four masters | Entitlement, credential, endpoint contract | Best cloud path after vendor enablement |
| Fast XML Export | Yes | Strong | No in this runtime | Medium; Supplier/Currency documented | Native dialog and Tax/GL selection confirmation | Best immediate bulk handoff |
| SQLACC command line | Yes | Strong for documented switches | No exporter | None for masters | No documented export switch | Reject as direct exporter |
| XLSnMDBImp `-Auto` | Yes | Conditional; query must be SELECT/read-only | Not safely configured | Unknown until query/output tested | Initial setup, credentials, query contract | Future scheduled file path |
| SDK Live | Yes | Strong if restricted to vendor read methods | Not in current project | Medium; objects/examples exist | SDK package, schema, runtime, authorization | Best long-term local path |
| Built-in menus | Yes | Strong | No in this runtime | Medium/low until artifact inspected | Native bridge unavailable | Safe fallback/manual handoff |

## Current blocker and minimum human action

The remaining blocker is enablement, not lack of supported methods:

1. The Codex runtime exposes browser surfaces but no native-app bridge, so it
   cannot safely inspect or click the SQL Account export dialog.
2. No API credential/listener or SDK package/contract is provisioned locally.
3. The official batch utility requires a configured query and credentials that
   are not available to this project.

After the automated investigation above, the smallest safe action is a single
official XML export:

1. Open **SQL Financial Accounting Text & XML Import Module V5**.
2. Choose **Fast XML Export**.
3. Select Supplier, Currency, Tax (if offered), and GL Account (if offered),
   without selecting any import/post action.
4. Save the XML output under
   `D:\OneDrive\Projects\AI-SQL-Entry\incoming\master-data`.

If Fast XML Export does not offer Tax or GL Account in this build, export only
the missing categories from their built-in read-only menus to the same folder.
Do not change SQL Account settings or click **Post To A/c**. Once files exist,
the project can perform all validation, snapshot replacement, backup, and
readiness reporting automatically.

## Implementation guardrails

- The acquisition source is an adapter; snapshot validation and invoice
  mapping remain source-independent.
- Every adapter must be GET/export/read-only and must return provenance,
  source filename or endpoint, retrieval timestamp, and source version.
- A snapshot replacement is transactional: validate all four datasets, create a
  timestamped backup, then replace; otherwise preserve the current snapshot.
- API/SDK credentials and company data never enter this knowledge base or
  committed logs.
- No adapter may expose SQL Account write, import, posting, UI automation, or
  direct database access.
- A real sample artifact is required before locking field mappings. Until then,
  endpoint names, XML tags, and query column names remain UNKNOWN.

## Next engineering action

The next safe action is to obtain one official XML export (or the vendor's
current API/SDK contract), place it in `incoming/master-data`, and run the
existing validation/snapshot builder. The resulting artifact will be used to
capture a versioned schema fixture and to decide whether an SDK/API adapter is
worth implementing before scheduled batch export.
