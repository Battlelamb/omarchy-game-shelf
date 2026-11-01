# Validation

Latest deployment record: [LIVE-QUALIFICATION.md](LIVE-QUALIFICATION.md).

## Historical pre-deployment checkpoint

The following offline record predates live authorization; its not-installed/not-run statements describe that earlier checkpoint.

Not installed, enabled, tagged or published. No window was opened on the live desktop.

## Executed on this package

`env -u PYTHONPATH PATH=/usr/bin bash test.sh`: no-network bubblewrap, fake HOME, cleared environment, private PID/mount namespaces, no live runtime sockets, production providers masked.

| Gate | Result |
|---|---:|
| Controller/actual-handler/receipt/runner checks | 27 passed |
| Python backend tests | 21 passed |
| Installed Qt/Quickshell subprocess cases | 23 passed |
| `omarchy plugin validate .` | exit 0 |
| Package identity/versioned runtime/licence/test files | passed |

The all-nine final rerun reconciles **243 Node + 310 backend + 207 native subprocess = 760 checks**, no skipped/cancelled tests. Those are aggregate counts, not this package's counts. Native helper cases cover byte bounds, Unicode, failures, stubborn-descendant deadlines, owner destruction, cancellation drain, stale callback exclusion and fresh PID receipts. The deliberately missing executable emits its exact expected FailedToStart warning; this is not a warning-free whole-shell claim. The runner pins `/usr/bin/node` and rejects missing full-suite prerequisites; backend-only checks remain available without Node.

## Private native UI and connected backend coverage

All nine real native QML components were separately instantiated under private headless labwc with the installed shell kit. Unicode/model bindings and same-instance retention under the installed host Loader formula pass. No live Wayland/Hyprland sockets were exposed.

A fresh private software-rendered wide/compact UI rerun passes **420/420 checks across all nine** (210 per layout), including contained grid/preview geometry, plain-text labels, filters, controls and fixture-backed action responses. The wide-grid collapse was first reproduced and fixed test-first. These are real native UI surfaces with **synthetic backends and fake compositor metadata**, not live providers, manual keyboard/pointer qualification, real Hyprland or GPU validation.

A separate **62/62-check Node VM actual-QML-handler-to-production-backend-CLI bridge** verifies literal `restore:last` dispatch for six restore-capable backends, receipt ownership and success-only Palette hints without reloading rows/query or decoding again. It uses actual backend code but fake providers; it is **not native GUI coverage**. The 420 and 62 counts are separate aggregate suites, not additional per-package counts.

## Fixes, review and evidence

Preserved RED/GREEN and original-backend/mutation controls cover Unicode, early-stop search, receipt-bound Restore, hidden previews, capability hints, current-wallpaper source races, exclusive Palette publication/previous ownership, interrupted Motion/Workspace/Shader compensation and watchdog handoff, and ambient Node-shim rejection. Unrelated disappeared candidates stay skippable; unknown/unadmitted current wallpaper paths remain non-restorable without broadening trusted roots. Success-only capability hints guarantee the existing rows remain usable; failures cannot grant actions.

Final robustness correction re-review: **passed**, with no remaining security concerns or logic errors in the scoped independent reviews. Earlier connected reviews and approved layout/runner deltas are historical evidence; they do not retroactively cover later code. Read-only final snapshots, exact tested hashes, named logs, negative controls and the sealed local commit are recorded in ignored `release-output/improvements-verification.json`; earlier receipts remain untouched.

Operation-count controls show zero artwork reads during app/game launch-membership checks, no hidden compact preview source, and search stopping at 256 matches. Runtime-only helper cleanup removes unused work without installing a shared daemon. Timing/CPU/RSS samples are **diagnostic only**, with no speedup, FPS or steady-state memory claim. The earlier whole-shell resource gate remains failed (Tailscale/nvidia-smi pollers); this scoped plugin pass neither fixes nor supersedes it.

## Environment and remaining limits

Observed tools: Omarchy 4.5.0rc2-1, Hyprland 0.56.2, Quickshell 0.3.2, Python 3.14.8, Node 26.13.0. Motion/workspace/shader adapters are intentionally pinned to supported Hyprland Lua 0.56.2. Real Lua parsing and fake compositor state are not real compositor/GPU execution.

Not exercised: live install/enable, live providers or IPC, actual clipboard/application/game ownership, real theme/wallpaper effects, shader pixels, live screen-lock races, native RTL/fractional scale/multi-output layout, IME, complete accessibility, FPS/resource soak, upgrades, hosted CI or marketplace publication. Storage/IPC failure, true divergent external edits or killing an independent watchdog can prevent recovery. Cancellation cannot undo an already accepted external action or own deliberately escaped groups. See BACKEND.md for exact limits, including retained Palette quarantine files. No full-security-audit or certification claim.

The recorded config hashes, theme/background link and compositor/shell PIDs remain unchanged. None of the nine is installed or published. Existing Native Overview is outside this local implementation scope and was not modified.
