# Game Shelf: v0.2.1 candidate validation

## Current v0.2.1 compact selected-detail fix

The compact detail viewport follows its content height up to a bounded 64px token instead of fixing it at 40px. Long metadata still scrolls; backend/controller/bounded-process bytes are unchanged. All runtime URLs advance to v0.2.1 to avoid reusing the already-loaded v0.2.0 component URL.

Fresh private native Qt regression reproduced the old clipping with representative JetBrains Mono 14px body / 13px small typography: 43px of title/body/padding did not fit in 40px. The corrected template passed title plus one complete body line, three preset choices, action/footer containment and real long-text scrolling checks at 680×520 and 640×480 cards, also at a 640×480 output. Default typography was checked separately. This is fixture-backed software-rendered native geometry/pixel evidence, not a new live desktop/backend action qualification or certification of every font/scale. With production preset descriptions and status text, all three tiles fit at 680×520; smaller layouts can require native list scrolling. Each choice was reached and fully shown using native keyboard input at 640×480 cards and outputs; simultaneous visibility of all three full tiles is not claimed there.

Scoped exact-tree independent review and refreshed illustrative preview checks passed. Sealing, source-export verification and live v0.2.1 integration are recorded separately. The earlier suite totals below are historical v0.2.0 evidence, not fresh v0.2.1 suite claims.

## Historical v0.2.0 qualification

Release gate: **passed for the scoped offline candidate**. Live v0.2.0 integration, hosted CI and publication are separate gates.

The release preserves backend, controller and bounded-process semantics while moving the installed entry point to a new versioned URL. Its own offline Node/Python/native tests, package validation and the all-nine native wide/compact/actual-backend bridge gates must pass on the exact candidate before sealing. Counts and source hashes come from fresh parsed receipts, not an estimate.

Historical v0.1.0 integration covered native UI/catalogues plus actual clipboard Copy, Steam menu startup, calculator launch, theme/wallpaper Apply/Restore, palette export/quarantine Restore, runtime motion/layout Restore and timed GPU shader recovery. Those are **historical checks**, not retroactive v0.2.0 GUI coverage. Shader empty-state and native wallpaper hardlink bookkeeping fixes are retained with their regression tests.

Not a full security audit. Every app/game, long soak, fractional scaling/RTL/IME/full accessibility, screen-lock races, all outputs, upgrades under active external actions, physical power loss and hosted CI remain unqualified unless separately recorded. Other profile retints/remote theme propagation were excluded from prior theme tests. The earlier whole-shell resource gate remains **failed**; this UI revision makes no speedup/FPS/steady-state resource claim.

No raw desktop captures, private window titles, raw clipboard content, provider logs, process traces or credentials belong in public release assets. Private bench captures stay outside the public source export. Optional public preview assets are withheld unless rights and content are checked.

## Recorded v0.2.0 offline coverage

The exact nine-tool candidate passed 315 Node tests, 333 backend tests and 207 native subprocess checks across its packages; the separate native wide/compact UI suite passed 590 checks, and the actual-backend/private-UI bridge passed 62 cases. Same-process old/new/rollback loading passed 93 assertions across nine sequences (27 component loads). These suite counts overlap in exercised behavior and are not a single performance or security score. Runtime hashes bind the checks to the candidate; later documentation/preview corrections do not acquire retroactive GUI coverage.

The exporter and component workflow passed scoped independent review. Each source archive must still be checked against its committed file inventory, modes and bytes, including its actual archived full licence, before delivery. Hosted component CI has not run; see [CI.md](CI.md) for its deliberately narrower scope. Public previews are native Qt captures with clearly labelled illustrative catalogues, not live provider/action evidence; see [PREVIEW.md](PREVIEW.md).

## Fresh v0.2.1 receipts

Nine sanctioned offline package suites passed 315 Node, 333 backend and 207 native-process checks. The targeted compact-detail native regression passed 504 checks; the separate real-preset keyboard run passed 504. The actual-backend/private-handler bridge passed 62 cases; same-private-process 0.2.0 → 0.2.1 → 0.2.0 loading passed 93 assertions. These separate suites overlap in behavior. Native pixel checks restored the previously clipped body line without changing its visible prefix. All 27 backend/controller/process blobs remain byte-identical. Refreshed illustrative previews passed 90 native checks and exact decoded-pixel/source matching. Hosted CI remains unrun.

Live v0.2.1 UI upgrade and rendered-catalogue checks also passed for all nine installed plugins without restarting the shell. Selected detail text was readable in the three preset panels, Palette Studio completed its catalogue, and the original workspace and observed configuration/effects/process state were preserved. This adds UI/upgrade coverage, not a new live action, universal rollback, font-design legal clearance, hosted CI, resource or long-soak certification. Small preset layouts retain keyboard/list scrolling.
