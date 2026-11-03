# Game Shelf validation

## Current 0.4.1 scope

The patch changes the public namespace, current documentation and versioned runtime URL. Backend actions and preference storage are unchanged. Package and Node regressions check public identity, matching namespace/revision, a single runtime tree, stable preference paths and generic machine-path exclusions. Run the shipped offline suite from a checkout with `TMPDIR` set to an existing private scratch directory:

```sh
env -u PYTHONPATH PATH=/usr/bin bash test.sh
```

This document does not claim a completed full 0.4.1 offline suite, hosted CI or live integration. Hosted status must be checked on the exact published commit; [CI scope](CI.md) is narrower than native/backend qualification.

## Historical v0.4.0 offline checks

The shipped `env -u PYTHONPATH bash test.sh` completed with **59 Python passes, 1 explicit skips (60 discovered)** and **58 JavaScript component passes**. Its **23 native subprocess/settings cases** and **five native UI modes** also passed: wide, compact, tall-font and light-theme fixtures, with real Save/reopen/Reset readback and strict query-chip/control containment. These overlapping checks are not one aggregate score or real-provider/full-shell evidence.

Runtime inventory SHA-256: `f869e6e5ba2c7a247d5ba707d251c28cf9a0611a1cca4dd946f1a13abeb04c7e` (sorted compact JSON of relative runtime paths to SHA-256 values). This identifies the original 0.4.0 suite, not 0.4.1. The [unchanged illustrative previews](PREVIEW.md) likewise show 0.4.0, not live actions or a newly qualified runtime.

Earlier baseline failures and the partial 4/9 candidate run remained failed; a later combined offline run passed with unchanged runtime hashes. The timeout harness passed late-fork, separate-session, PID-identity and unrelated-sentinel controls. If orphan ownership cannot be proved, tests stay incomplete/nonzero and abort subsequent cases, relying on the outer sandbox for containment.

## Earlier version checkpoints

This package’s frozen v4 offline `bash test.sh` gate passed **50 Python tests out of 51 discovered** and **51 Node component tests**. 1 explicit skip: the shared Glyph real-CLI case belongs to Glyph Picker only. Package checks and shipped native subprocess/settings/panel checks also completed; those overlapping checks are separate from the Python/Node totals. Native Qt coverage uses offscreen components and adapter fixtures, not a real Omarchy shell or live provider. Runtime hashes still match the tested v4 bytes; these documentation changes do not acquire retroactive GUI coverage.

The historical v0.3.0 full-shell old/new/rollback attempt was **FAILED_TO_RUN: 0/9 qualified**: resource admission blocked launch and the device-free compositor attempt failed before shell startup. Offscreen checks did not replace it. Historical open/populate/close observations are not action or full-shell rollback qualification.

The v0.2.1 compact-detail fix passed native font-metric, containment and long-text scrolling checks, including keyboard access at small sizes. Small layouts may still need scrolling. Earlier v0.1.0 action checks and v0.2.x UI/upgrade checks describe only those versions, not the current namespace or runtime.

## Limits that remain

- Live actions and real-shell old/new/rollback, GPU behavior, live lock races, hotplug, longer resource/soak runs and RTL/IME/accessibility/all-scale behavior remain unqualified for this patch.
- The historical whole-shell resource gate stays failed. Existing anchor-transition warnings remain; no warning-free, universal speedup/FPS/resource or debloat claim.
- Native/offscreen fixtures and illustrative captures are not real-provider or full-shell evidence. Overlapping suite counts are not an aggregate score or a security audit.
- Source publication does not imply a stable release, hosted CI success or marketplace promotion. Keep private captures, paths, clipboard contents and raw provider/process logs out of public reports.
