# Windows Desktop Automation Knowledge Base

This directory records the reusable engineering knowledge for reliable native
Windows desktop automation in AI-SQL-Entry. It is deliberately separate from
business logic and from SQL Account integration.

## Current verdict

The Windows operating system is ready for same-integrity UI Automation:

- Windows UI Automation Core is installed.
- The Codex shell and the target desktop process run in the same active
  interactive session.
- Both processes run at medium integrity, so UIPI is not blocking this
  same-user case.
- The desktop is not locked.

The current blocker is the Codex runtime bridge. The installed Computer Use
packages and signed Windows helper binaries are present, but the trusted Node
REPL service named sky is not registered. Consequently:

- the supported @oai/sky client fails with “Trusted RPC service is not
  configured: sky”;
- the legacy CUA surface exposes browser functions but no native
  listApps function;
- no targetable native application can be selected safely.

This is an environment-owned capability, not a project configuration or
application-code defect. The project must not bypass it by launching helper
executables, guessing window handles, or using terminal-driven UI automation.

## Architecture

The supported Windows path is:

    Codex turn
        -> trusted Node REPL
        -> nodeRepl.rpc("sky", request)
        -> @oai/sky Windows client
        -> codex-computer-use.exe helper
        -> Windows input, UI Automation, and Graphics Capture
        -> one explicitly selected target window

The project integration boundary is intentionally narrow:

    target discovery
        -> stable returned app/window object
        -> read-only observation
        -> one guarded UI action, when authorized
        -> fresh observation and verification

Business extraction, master-data validation, and import-package generation
remain independent of this bridge. A future desktop adapter may deliver files
to the existing intake folders, but it must not contain accounting rules or
database writes.

## Components

| Component | Role | Current state |
| --- | --- | --- |
| Windows UI Automation Core | Microsoft accessibility/client-provider runtime | Installed and loadable |
| Microsoft UI Automation providers | Expose controls and patterns to clients | Availability depends on target app |
| @oai/sky | Supported native desktop client | Installed; blocked by missing trusted service |
| @oai/cua | Legacy/compatibility CUA package | Installed; current surface is browser-only |
| codex-computer-use.exe | Signed Windows helper for input/UIA/capture | Installed; not started because the trusted service is unavailable |
| Codex Node REPL | Host that must expose trusted service registration and approvals | Present, but sky service is not configured |

Microsoft describes UI Automation as the Windows accessibility framework that
lets client applications retrieve UI elements and invoke supported control
patterns. See the [UI Automation overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview)
and [UI Automation clients overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-clientsoverview).

## Setup

### Environment-owned setup

The following must be provided by the Codex desktop runtime, not by this
repository:

1. Enable the Computer Use native Windows capability for the session.
2. Register the trusted Node REPL service named sky.
3. Expose the native-app methods required by the current @oai/sky window API.
4. Provide the app-approval callback required before a helper can use a target.

Setting an environment variable in a project shell is not sufficient. The
trusted RPC registration belongs to the host Node REPL process and cannot be
safely manufactured by project code.

### Windows session prerequisites

- The desktop must be unlocked and interactive.
- Codex and the target application must run in the same user session.
- The target window must be restored and intersect the visible desktop.
- Avoid targeting UAC prompts, the secure desktop, or another user’s session.
- Keep Codex and the target at the same integrity level unless an authorized
  UIAccess deployment has been approved.

Microsoft documents that UI Automation works without UIPI interference when
client and target run at the same medium integrity level. Higher-integrity
targets require a separately trusted UIAccess deployment; do not enable that
for this project by changing security policy. See the [UIPI security guidance](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/security-policy-settings/user-account-control-allow-uiaccess-applications-to-prompt-for-elevation-without-using-the-secure-desktop)
and [UI Automation security overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview).

### Runtime verification

Run the following through the supported Computer Use tool surface, not through
PowerShell UI automation:

1. Import @oai/sky in the trusted Node REPL.
2. Call sky.list_apps().
3. Confirm the result is an array and contains only the intended target.
4. Select exactly one returned window.
5. Capture accessibility state before any action.
6. After each action, capture fresh state and verify the result.

If sky.list_apps() cannot run, stop. Do not construct an app or window from a
process ID, title guess, screenshot coordinate, or stale diagnostic record.

## Limitations

### Runtime limitations

- The current CUA object reports apps: [] and has no listApps method.
- @oai/sky.list_apps() fails before helper startup because trusted RPC service
  sky is not configured.
- The helper package is not a substitute for the missing host registration.
- Browser automation and native desktop automation are separate surfaces.
- A browser tab or browser pipe does not prove that native desktop control is
  available.

### Windows limitations

- UI Automation exposes only what the target provider makes available.
- Custom or owner-drawn controls may expose weak or unstable trees.
- UIPI blocks lower-integrity clients from elevated target windows.
- Secure desktop, lock screen, and other-user sessions are intentionally
  isolated.
- A minimized or off-screen window may exist as a process while remaining
  unusable for safe discovery.

### Project safety limitations

- Do not use PowerShell, Command Prompt, Windows Terminal, Run dialog, or File
  Explorer to drive UI actions.
- Do not launch the Computer Use helper manually.
- Do not bypass trusted-service or app-approval controls.
- Do not change Windows security, privacy, UAC, UIAccess, or accessibility
  policy as a project-side workaround.
- Do not automate accounting posting, database writes, authentication, or
  password dialogs.

## Troubleshooting

| Symptom | Interpretation | Safe response |
| --- | --- | --- |
| sky.list_apps() throws trusted-service error | Host did not register sky RPC | Restart or reconfigure the Codex Computer Use runtime; do not edit project code |
| list_apps returns an empty array | No native target is exposed | Confirm the desktop is unlocked and target is restored; otherwise use file handoff |
| Target process exists but no returned window | Window is minimized, off-screen, another session, or not bridge-visible | Restore it in the active session, then rediscover from the bridge |
| Accessibility tree is empty | Target provider may be weak or the wrong window was selected | Capture a screenshot-backed state and reselect from fresh returned windows |
| Input reports a non-target window | Foreground/layout changed | Re-list windows, activate the returned target, and recapture state |
| Helper times out | Bridge/helper startup or session transport failed | Stop, record the exact error, and retry only after reinitializing the runtime |
| Target runs elevated | UIPI may block interaction | Do not lower security; use an approved matching-integrity/UIAccess deployment |

## Supported alternatives

### Microsoft UI Automation

Microsoft UI Automation is the correct underlying Windows technology for
read-only discovery and control patterns. It is already part of the supported
Computer Use architecture, so the preferred solution is to restore the
@oai/sky bridge rather than add a second automation stack.

### Direct pywinauto or custom Win32 scripts

These can be useful in a separately approved engineering runtime, but they are
not a substitute for the current Codex Computer Use capability. They would
introduce an independent input channel, new installation and permission
requirements, and a larger security surface. They must not be added to this
project merely to bypass the missing trusted service.

### File-based handoff

When native automation is unavailable, use official application exports saved
into the existing intake folders. This preserves read-only behavior and allows
the project to continue validation without UI control.

## Future maintenance

After any Codex, Computer Use, Windows, or target-application upgrade:

1. Re-run the runtime verification sequence.
2. Record package/helper versions and whether sky.list_apps() works.
3. Confirm the helper signature remains valid.
4. Re-check session, integrity, and window-placement assumptions.
5. Revalidate accessibility trees and stable control properties.
6. Keep diagnostics free of company names, credentials, exported records, and
   absolute user paths.

The bridge is an infrastructure dependency. Keep it versioned and observable,
but keep the business pipeline runnable without it through the existing
file-based boundary.

## Current status

- **Resolved locally:** OS/UIA prerequisites, same-session and same-integrity
  checks, and installed helper verification.
- **Not resolvable in repository code:** trusted sky RPC registration in the
  Codex Node REPL.
- **Required external change:** enable/restart the Codex Computer Use native
  Windows capability or use the file-based handoff.
- **Next milestone:** re-run this verification after the environment exposes
  sky.list_apps(), then add only a read-only target-discovery adapter.

Last reviewed: 2026-09-09
