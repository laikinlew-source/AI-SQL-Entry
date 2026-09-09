# Current Discovery Blocker and Next Action

**Reviewed:** 2026-09-09

## Blocker

Fresh desktop inspection cannot continue because the available computer-use
surface exposes only the Codex in-app browser and no Windows native application
windows. A current process check confirms `SQLACC.exe` is running, but its
native window is not exposed through the available CUA surface and no usable
window title was returned by the shell observation. No new SQL Account window
or menu could therefore be inspected in this turn. The earlier SQL Account
window evidence is historical, and the installed executable has since changed
version; it cannot safely authorize a new export click.

This is a tooling/session visibility blocker, not evidence that SQL Account
lacks export functionality.

## Why it matters

Export menu names, dialog fields, output formats, worksheet names, and column
order are source-contract facts. Guessing them could generate invalid master
snapshots or cause a later SQL Account import failure. The safety rules require
a fresh window and dialog observation before automating any click.

## Options

### Option 1 — Restore native Windows automation visibility

Open SQL Account in the same interactive desktop session where the computer-use
bridge can enumerate Windows apps, then rerun discovery. This enables passive
inspection of menus and dialogs and may allow a guarded built-in export.

**Advantages:** least manual work; captures the authoritative UI; no new
credentials or service configuration.

**Risk:** the bridge may remain unavailable or UIA may still be unstable.

### Option 2 — Minimal manual export hand-off

An authorized user performs the four built-in read-only exports and places the
files in:

the project's `incoming/master-data` directory

No schema research is required from the user. The project detects the files,
validates their headers and values, and reports exact failures.

**Advantages:** immediately unblocks snapshot building; no administrator
permission, API credentials, or accounting write.

**Risk:** the exact UI export contract is not captured until the files arrive.

### Option 3 — Vendor-supported API GET enablement

Obtain written entitlement and an approved non-production API setup, then
implement a read-only adapter after the exact master-data contract is supplied.

**Advantages:** most automatable and repeatable long term.

**Risk:** requires administrator/vendor action, credentials, service setup, and
contract evidence; it is not an immediate path.

## Recommendation

Use Option 1 first if the native bridge can be restored. If it cannot, use
Option 2 as the smallest practical action: provide the four read-only exports.
Keep Option 3 as the planned long-term automation path. No SQL Account database
access, API credential generation, UI posting, or accounting write is needed.

## Exact minimum user action if required

Export these four datasets using SQL Account's built-in read-only export
facility and save one file for each under `incoming/master-data`:

1. Suppliers
2. Tax Codes
3. GL Accounts
4. Currencies

Do not import, save accounting records, post, or change SQL Account settings.
Once the files exist, the project can continue automatically.
