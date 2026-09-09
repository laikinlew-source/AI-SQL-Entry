# Native Windows Automation Runtime Diagnosis

**Review date:** 2026-09-09
**Evidence type:** read-only local inspection and supported Computer Use
client probes. No application UI was clicked, typed into, or modified.

## Reproduction

The failure is reproducible in a fresh Computer Use JavaScript session:

1. Import the installed @oai/sky package.
2. Call sky.list_apps().
3. The call fails with:

       Trusted RPC service is not configured: sky

The compatibility CUA surface can be queried, but it returns browser surfaces
only:

    { apps: [], browsers: [...] }

The same surface does not expose the documented native listApps method.

This is a deterministic runtime capability failure, not intermittent target-app
behavior.

## Local evidence

### Installed bridge packages

**Evidence class: VERIFIED-LOCAL**

- @oai/sky version 0.6.26 is installed.
- @oai/cua version 0.2.4 is installed.
- The Windows helper binary is present in the package.
- Authenticode validation reports a valid signature from OpenAI OpCo, LLC.
- No helper process named codex-computer-use or sky is running during the
  failed probe.
- A Codex computer-use named pipe exists, but its presence does not make the
  sky RPC service available to this Node REPL.

The helper is therefore installed but not reached through the supported client
path. The project must not start it directly.

### Node REPL capabilities

**Evidence class: VERIFIED-LOCAL**

The current trusted Node REPL exposes:

- rpc: function
- request metadata and normal REPL output helpers

It does not expose the configuration/native-pipe/launch-service hooks required
to manufacture a trusted desktop service from project code. Calling rpc for
sky returns the trusted-service error above.

The process, user, and machine values for NODE_REPL_TRUSTED_SERVICES are
unset. This is evidence of missing host registration; setting that variable
from a project shell would not create the host-side RPC implementation and is
not an approved fix.

### Windows prerequisites

**Evidence class: VERIFIED-LOCAL**

- Windows 10 Pro 64-bit, build 26200.
- UIAutomationCore.dll is present in System32.
- The Codex shell and the target desktop process share the active session.
- Both inspected processes run at medium integrity.
- The interactive RDP session is active.
- No lock-screen process is active in that session.
- UAC is enabled with normal secure-desktop prompting.

These facts rule out a missing UIA runtime, a different user session, a
locked-desktop condition, and a same-user UIPI mismatch as the primary cause.

## Component-boundary diagnosis

| Boundary | Observed state | Conclusion |
| --- | --- | --- |
| Windows UIA runtime | UIAutomationCore.dll present | OS prerequisite is present |
| Target process/session | Active process in the same interactive session | Session mismatch is not primary |
| Process integrity | Codex and target both medium | UIPI is not blocking this case |
| @oai/sky package | Installed and signed | Package is present |
| Windows helper | Installed but not running during probe | Helper is downstream of failed host registration |
| Node REPL rpc | Function exists | Transport entry point exists |
| Trusted sky registration | Missing; rpc call rejected | **Definitive failure boundary** |
| Native app enumeration | apps empty / listApps absent | No safe target selection possible |

## Root cause

The missing capability is the **trusted Codex Node REPL registration for the
sky native Windows Computer Use service**. The current runtime exposes browser
automation but not the native desktop service required by @oai/sky.

The installed helper binary, Windows UIA runtime, current session, and process
integrity are not the failing components.

## Why this cannot be fixed in project code

The trust boundary is intentionally host-owned:

- the RPC service is injected into the Codex Node REPL;
- app approval callbacks are also host-owned;
- the @oai/sky client refuses to operate without that trusted channel;
- manually setting environment variables, importing private modules, or
  launching the helper would bypass the intended security boundary.

No repository change can safely register a new trusted service in the already
running Codex host. The only local resolution is an environment/runtime
configuration change that enables the native Computer Use capability.

## Official technology assessment

Microsoft UI Automation is the officially supported Windows accessibility
technology for retrieving UI elements and invoking control patterns. It is
appropriate for this project because it separates semantic controls from
screen coordinates and supports Win32, Windows Forms, and WPF providers.

The preferred deployment is therefore:

    Codex trusted sky service
        -> @oai/sky
        -> Microsoft UI Automation and guarded input

Adding pywinauto, custom Win32 SendInput, or a second accessibility bridge would
not resolve the missing Codex trust registration. It would create a new
installation, approval, maintenance, and security surface. It is not
implemented.

## Resolution options

### Option A — enable the native Computer Use runtime

An environment owner enables or restarts the Codex native Windows capability so
that the Node REPL registers sky. This is the recommended option because it
preserves the supported bridge, app approvals, and UIA/screenshot safeguards.

### Option B — continue through files

Use official read-only exports and the existing project intake/snapshot
pipeline. This requires no desktop automation and keeps production processing
available while the runtime capability is repaired.

### Option C — separately approved automation host

If the Codex native capability cannot be enabled, an administrator could deploy
an isolated Microsoft UI Automation client with explicit signing, permissions,
session handling, and test coverage. This is a new infrastructure project, not
a local workaround, and should be considered only after Option A is exhausted.

## Minimal external action

The smallest action needed for native discovery is to enable/restart the
Codex Computer Use native Windows capability for the current interactive
session. No Windows security setting, UAC policy, or SQL Account setting should
be changed.

If the environment does not offer that capability, the safe fallback is to
place official export files into the project's intake folder and continue with
file processing.

## Maintenance checklist

Record these checks after every runtime or Windows upgrade:

- @oai/sky and @oai/cua package versions;
- helper signature status;
- presence of the trusted sky service;
- result of sky.list_apps();
- session and integrity relationship;
- target-window visibility and accessibility-tree quality;
- exact error text for any failed call.

Never record credentials, company names, invoice data, absolute user paths, or
raw screenshots in this knowledge base.

## Status

**Definitive conclusion:** the current limitation is a missing Codex trusted
desktop bridge registration, with no evidence of a Windows UIA, permission,
session, or target-process defect. It cannot be repaired safely from
AI-SQL-Entry repository code. The next action is to enable the environment-owned
native capability; until then, the file-based workflow remains the supported
fallback.
