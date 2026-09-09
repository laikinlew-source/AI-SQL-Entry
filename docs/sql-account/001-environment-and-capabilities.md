# SQL Account Environment and Capabilities

**Discovery date:** 2026-09-09 (repository review of evidence captured on
2026-07-23 and current desktop capability check)

## Installed environment

| Item | Finding | Confidence | Evidence |
| --- | --- | --- | --- |
| Product | SQL Account ERP Edition | High | `docs/005-Sprint-1-Discovery-Report.md` |
| Executable | `SQLACC.exe` under the local SQL Account installation root | High | `diagnostics/sql-accounting-discovery/processes.json` |
| Version | `5.2026.1085.897` on the 2026-09-09 recheck; earlier captured evidence was `5.2026.1083.895` | High for the current executable | current executable version resource plus historical diagnostics |
| Architecture | x64 | High | process/version evidence |
| Company window | SQL Account ERP Edition for the configured company database | High | captured UI evidence (company identifier redacted) |
| Firebird server | `5.0.3.1683` x64, running | High | API feasibility discovery |

The current CUA surface exposes no Windows native applications, only the Codex
in-app browser. A current process check found `SQLACC.exe` running from the
expected path, but its native window is not exposed through CUA and has no
usable window title in the shell observation. No new SQL Account window or menu
could therefore be inspected in this turn. This does not invalidate the earlier
captured evidence; it means that a fresh live export action cannot be attempted
automatically now, and old coordinates/selectors must not be reused across the
version change.

## Verified menu and navigation findings

The earlier UI Automation discovery exposed the main SQL Account workspace and
these named module buttons:

`Main Menu → Purchase`

The guarded navigation then reached the Purchase landing page and identified a
visible `Purchase Invoice` tile. A further guarded visual step opened the
Purchase Invoice listing, where a visible `New` button was observed. No `New`
button was clicked, no blank form was opened, and no accounting value was
entered.

The accessible main-screen hierarchy also exposed `Supplier` and `General
Ledger` modules. Their export screens were not opened, so their exact menu
paths remain `UNKNOWN`.

Official vendor usage documentation independently identifies these master-data
locations, but this is documentation evidence rather than a live UI capture:

- `GL → Maintain Account` for GL codes.
- `Supplier → Maintain Supplier` for supplier records.
- `Tools → Maintain Tax` for tax codes.
- `Tools → Maintain Currency` for currency records.

Sources: [Master Data](https://docs.sql.com.my/sqlacc/usage/master-data),
[Tax Code](https://docs.sql.com.my/sqlacc/miscellaneous/tax-code), and
[Tools Guide](https://docs.sql.com.my/sqlacc/usage/tools/guide).

## Version drift control

The executable changed from the historical captured version
`5.2026.1083.895` to `5.2026.1085.897`. Any future UI or file-format discovery
must record the exact executable version and repeat the relevant smoke checks.
The project must not assume that menu positions, accessibility identifiers,
templates, or export columns are stable across this update.

## Installed capability indicators

The SQL Account installation contains these relevant components:

- `SQL.DataImport.bpl`
- `SQL.oodataimport.bpl`
- `cxExportRS37.bpl`
- `SQLAcc.API.bpl`
- `SQL.IW.API.bpl`
- `SQL.IW.API.testcase.bpl`
- `SQLACCSVC.exe` is also present in the install directory, but the only
  similarly named Windows service found (`ACCSvc`) resolves to an Acer Care
  Center executable; it is not evidence of a SQL Account API service.

These prove that import/export/API-related components are installed. They do
not prove a particular Purchase Invoice schema, license entitlement, API
service, or export menu behavior.

## Automation assessment

| Method | Result | Decision |
| --- | --- | --- |
| Microsoft UI Automation | Main window and module names were read successfully in prior discovery; later listing accessibility was unstable | Use for passive discovery only until fresh stability is proven |
| Visual matching | Purchase Invoice tile was detected under one validated 1920×1080 layout | Fallback navigation signal, never the posting mechanism |
| Keyboard shortcuts | Not tested | Do not use as a primary method; focus/state dependent |
| Direct Win32 enumeration | Shell could not see the SQLACC HWND while the CUA helper could | Not reliable in this environment |
| Built-in export | Components indicate capability, but no export dialog was opened | Preferred if verified in a live read-only session |
| Official API GET | Vendor documentation verifies Purchase Invoice GET patterns; local API service is not configured | Best long-term automation candidate, pending entitlement/setup |
| Direct database access | Not attempted | Permanently excluded by project architecture |

## Safety record

The captured discovery performed no accounting create, edit, save, post,
approve, delete, database query, API request, or credential operation. The
only UI actions were guarded navigation to the Purchase area and Purchase
Invoice listing.
