# Native Window Visibility Diagnosis

**Review date:** 2026-09-09  
**Scope:** read-only diagnosis of the installed SQL Account desktop process and
the Codex native-app control surface. No SQL Account data was opened,
exported, edited, imported, or posted.

## Executive conclusion

The current discovery blocker is at two separate layers:

1. **SQL Account window state:** the SQL Account process is running in the
   active user session, but its main form is minimized and positioned outside
   the visible desktop bounds. It is therefore not an interactable foreground
   window in the current desktop state.
2. **Codex native-app bridge:** the available CUA surface reports no native
   applications (apps: []). The alternate native bridge is not configured
   (Trusted RPC service is not configured: sky), and the exposed CUA object does
   not provide listApps.

Restoring the SQL Account window is necessary for any UI discovery, but it is
not sufficient by itself: the native-app bridge must also expose the interactive
Windows desktop. The evidence does not indicate that SQL Account needs a
database connection or a write-capable API for the requested read-only export
work.

## Evidence collected

### Process and session

**Evidence class: VERIFIED-LOCAL**

- SQLACC.exe is running and responding.
- The SQL Account process and the Codex shell are both in Windows session 2.
- The session is the active RDP session for the signed-in user.
- The process reports a current executable version newer than the version
  recorded in earlier discovery notes. Version-sensitive UI behavior must be
  revalidated after the window/bridge is available.

This rules out a simple “wrong Windows session” explanation. It does not prove
that every desktop-isolation boundary is shared by the Codex native bridge.

### Window placement

**Evidence class: VERIFIED-LOCAL**

- Top-level window enumeration finds SQL Account's Delphi/VCL main form class
  (TMainForm).
- The main form is marked visible by Windows but is currently minimized.
- Its current rectangle is far outside the visible desktop; its saved normal
  rectangle is a normal on-screen rectangle.
- The process-reported TApplication handle is zero-sized and is not a useful
  automation target in this state.
- The foreground window belongs to the Codex desktop process, not SQL Account.

The application is therefore present but not currently discoverable as a usable
foreground form. This is a window-state problem, not evidence of missing
business data.

### Codex/CUA surface

**Evidence class: VERIFIED-LOCAL**

- cua.getState() returns browser surfaces only and apps: [].
- The documented alternate sky bridge cannot initialize because its trusted RPC
  service is not configured.
- cua.listApps() is not exposed by the current runtime.
- No native-app UI action was attempted after these checks; no coordinates or
  guessed controls were used.

Consequently, this runtime cannot currently attach to the SQL Account native
window, even though the process exists in the active Windows session.

## Hypothesis matrix

| Hypothesis | Result | Evidence and implication |
| --- | --- | --- |
| Codex runtime/native bridge unavailable | **Confirmed primary blocker** | No native apps are exposed; alternate trusted RPC bridge is not configured. |
| SQL Account is not running | **Rejected** | Responding SQLACC.exe process is present. |
| SQL Account is in a different Windows session | **Rejected for the tested process** | SQL Account and the Codex shell share session 2. |
| SQL Account window is hidden/minimized/off-screen | **Confirmed contributing blocker** | Main form is minimized and outside the visible desktop. |
| Windows UI Automation is disabled | **Unknown** | Cannot test safely until a native-app bridge exposes the window. |
| Permission model prevents all inspection | **Not primary** | Process/window metadata is readable; service inventory is restricted but is not needed for UI discovery. |
| SQL Account technology is incompatible | **Not supported by evidence** | Earlier UIA discovery observed a usable SQL Account hierarchy; current failure occurs before UIA attachment. |
| SQL Account API/service is required | **Rejected for this milestone** | Official file export and API GET are separate supported paths; neither requires database writes. |

## Supported read-only interaction paths

### 1. Official XML export utility

**Evidence class: VERIFIED-VENDOR**

SQL Account's official [XML Import & Export Guide](https://docs.sql.com.my/sqlacc/miscellaneous/import-export-guide)
documents Fast XML Export for master data and transactions. The utility is
the strongest supported bulk-export path when the required master-data records
are available in its export list. It is file-based and can be consumed without
database access.

### 2. Built-in application export

**Evidence class: UNKNOWN until live dialog verification**

The installed application contains export/import components, and official SQL
Account documentation describes Excel/CSV-oriented workflows. The exact
read-only export buttons and column layouts for the current build have not been
verified because the native window is not exposed. No assumption about a menu
or output schema should be encoded until a real export file is inspected.

### 3. Official SQL Account API GET

**Evidence class: VERIFIED-VENDOR for capability; UNKNOWN for local enablement**

The official [SQL Account API FAQ](https://docs.sql.com.my/sqlacc/integration/sql-account-api/faq)
documents authenticated read-only GET operations. Local discovery found no
confirmed API service endpoint, credentials, or enabled listener. Enabling the
API requires product configuration/licensing and credentials, so it is not an
immediate substitute for a file export.

### Excluded paths

- Direct Firebird/database reads: excluded by project policy and unnecessary for
  the supported export boundary.
- Clipboard/Excel import and Post To A/c: official import/write operations,
  not read-only acquisition. See
  [003-import-workflow-and-limitations.md](003-import-workflow-and-limitations.md).
- Third-party import/export utilities: not preferred while an official export
  path is available.

## Integration decision

The existing project boundary remains correct:

    official SQL Account file export or API GET
        -> incoming/master-data
        -> snapshot builder
        -> validation/readiness reports

The reader and business validation layers remain independent of the acquisition
source. If a future native UI adapter is added, it should only deliver files
into incoming/master-data; it must not post transactions or modify SQL Account.

Microsoft UI Automation is the preferred discovery technology if the Codex
native bridge becomes available. It can inspect window/control properties
without database access and is better suited than screen coordinates for a
Delphi/VCL application. A future adapter should use stable control properties
where present, validate the process/session/window before every action, and stop
before any import or posting command. It must not be introduced as a second
business-logic path.

## Blocker resolution options

### Option A — restore native desktop visibility (recommended for automation)

Restore the SQL Account main window in the active desktop session, then enable
or reconnect the Codex native Windows bridge that exposes apps. This keeps
discovery automatable and allows safe inspection of the current export dialogs.
The exact bridge setting is environment-owned; no project code can enable the
missing trusted RPC service.

### Option B — perform a minimal read-only export handoff

Use SQL Account's documented export function to save the four master-data files
(Supplier, Tax Code, GL Account, Currency) into the project's
incoming/master-data folder. The project can then validate, snapshot, and
rerun invoice readiness without any UI automation or database access.

### Option C — enable the official API

An authorized administrator or SQL Account vendor support must enable/licence the
API and provide a read-only credential. The project can then implement a GET
adapter against the documented API while keeping the same source-independent
snapshot builder. This is the most scalable long-term path but has the largest
external prerequisite.

## Smallest required human action

No user action is required to preserve the current read-only architecture. To
continue native UI discovery, the smallest action is:

1. Restore SQL Account from the Windows taskbar or Alt+Tab so its main form is
   on-screen in the active session.
2. Enable the Codex/Computer Use native Windows capability if the environment
   exposes it; this is a runtime setting, not a SQL Account data change.

If that capability cannot be enabled, save the four official export files to
incoming/master-data; no other manual research is needed.

## Reusable troubleshooting checklist

1. Confirm the SQL Account process is responding and in the same interactive
   session as the automation runtime.
2. Confirm the main form is not minimized and its screen rectangle intersects
   the visible desktop.
3. Confirm the native bridge reports at least one native application before
   attempting UIA discovery.
4. If apps remains empty, do not guess coordinates or use screen automation;
   switch to the file handoff or API enablement path.
5. Record the SQL Account build again after any upgrade; UI hierarchy and export
   dialogs are version-sensitive.

## Status

- **Definitive technical conclusion:** current failure is the combination of an
  off-screen/minimized SQL Account main form and an unavailable Codex native-app
  bridge. It is not a SQL Account database requirement.
- **Safe work that can continue now:** file-based snapshot building and
  readiness validation once official exports are placed in incoming/master-data.
- **Not safe/possible in the current runtime:** native UI discovery or automated
  export clicks.
- **Next milestone already prepared:** verify the environment-owned native
  bridge/window restore, then inspect the exact current-build export dialogs; if
  unavailable, consume a minimal official export handoff.
