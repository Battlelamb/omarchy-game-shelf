# leviathan.game-shelf: workstation live qualification

Recorded 2026-11-02; local candidate only, not published or marketplace-approved.

Final live qualification: **passed within the scope below**. Independent fix reviews and real Apply/Restore gates passed; earlier failed attempts are retained.

## Executed scope

- Installed/enabled from reviewed local source with exact runtime hashes, no shell/compositor restart.
- Real native wide-layout UI, populated catalogue, search/actions and open/close surface lifetime exercised on DP-2. Initial catalogue observed 13 rows; displayed matches remain capped and palette extraction is budgeted.
- Direct shortcut: **Super+Ctrl+Alt+2** (physical number row). Real input opens this overlay; original Super+D remains Native Overview.
- Offline regression checkpoint: **27 Node, 21 backend, 23 native process cases**; exact run/source/commit receipts are outside Git in release-output and the parent deployment record.

Real Steam handoff booted Darkwood to its rendered main menu, confirmed in a scoped capture. No gameplay or save interaction. Only the test game and newly opened client window were closed; existing Steam stayed running. Lutris is not installed and was not launch-tested. The bounded Steam catalogue includes support/runtime items as well as games.

## Limits and cleanup

Private compact-layout checks are separate from the live wide-layout pass. Native RTL/fractional scaling, all-output combinations, IME/full accessibility, screen-lock races, upgrades, long soak, hostile-media certification, physical power loss and hosted CI remain unqualified. Storage/IPC failure, genuine external edits or killing an independent watchdog can still prevent recovery. Cancellation cannot undo accepted external work or own escaped groups. The earlier whole-shell resource gate remains failed and is not superseded here; no speedup/FPS/steady-state memory claim.

The independent fix reviews, new local commits, installed hashes, actual action/pixel readbacks, restoration records and retained failure logs are in the parent deployment evidence. No raw clipboard data, credentials or recovery material was logged. A game initially appeared on workspace1 during a direct-launch retry and was immediately moved to empty3; its later scoped capture confirms the menu. Isolated Hyprland config-verifier processes segfaulted on both unchanged baseline and candidate; the actual compositor PID1511 and shell stayed alive. Native live reload/configerrors and actual keyboard tests were used, without pretending the offline verifier passed.
