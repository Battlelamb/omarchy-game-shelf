# Game Shelf: v0.2.0 validation

Release gate: **passed for the scoped offline candidate**. Live v0.2.0 integration, hosted CI and publication are separate gates.

The release preserves backend, controller and bounded-process semantics while moving the installed entry point to a new versioned URL. Its own offline Node/Python/native tests, package validation and the all-nine native wide/compact/actual-backend bridge gates must pass on the exact candidate before sealing. Counts and source hashes come from fresh parsed receipts, not an estimate.

Historical v0.1.0 integration covered native UI/catalogues plus actual clipboard Copy, Steam menu startup, calculator launch, theme/wallpaper Apply/Restore, palette export/quarantine Restore, runtime motion/layout Restore and timed GPU shader recovery. Those are **historical checks**, not retroactive v0.2.0 GUI coverage. Shader empty-state and native wallpaper hardlink bookkeeping fixes are retained with their regression tests.

Not a full security audit. Every app/game, long soak, fractional scaling/RTL/IME/full accessibility, screen-lock races, all outputs, upgrades under active external actions, physical power loss and hosted CI remain unqualified unless separately recorded. Other profile retints/remote theme propagation were excluded from prior theme tests. The earlier whole-shell resource gate remains **failed**; this UI revision makes no speedup/FPS/steady-state resource claim.

No raw desktop captures, private window titles, raw clipboard content, provider logs, process traces or credentials belong in public release assets. Private bench captures stay outside the public source export. Optional public preview assets are withheld unless rights and content are checked.

## Recorded v0.2.0 offline coverage

The exact nine-tool candidate passed 315 Node tests, 333 backend tests and 207 native subprocess checks across its packages; the separate native wide/compact UI suite passed 590 checks, and the actual-backend/private-UI bridge passed 62 cases. Same-process old/new/rollback loading passed 93 assertions across nine sequences (27 component loads). These suite counts overlap in exercised behavior and are not a single performance or security score. Runtime hashes bind the checks to the candidate; later documentation/preview corrections do not acquire retroactive GUI coverage.

The exporter and component workflow passed scoped independent review. Each source archive must still be checked against its committed file inventory, modes and bytes, including its actual archived full licence, before delivery. Hosted component CI has not run; see [CI.md](CI.md) for its deliberately narrower scope. Public previews are native Qt captures with clearly labelled illustrative catalogues, not live provider/action evidence; see [PREVIEW.md](PREVIEW.md).
