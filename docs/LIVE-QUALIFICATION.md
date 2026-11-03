# Integration coverage

The current 0.4.1 namespace migration has no new live-action or full-shell upgrade/rollback qualification.

Historical v0.2.1 UI checks covered opening and closing real catalogues, the compact selected-detail/font/scrolling fix, and an in-session UI upgrade without a shell restart. They did not establish new clipboard or application/client actions and do not qualify 0.4.1. Earlier v0.2.0 offline UI checks and scoped review passed; its live upgrade was pending at that recorded checkpoint.

Open the current plugin with `omarchy-shell shell summon battlelamb.game-shelf`. The optional **Super+Space → Trigger → Game Shelf** entry is documented in the [README](../README.md); installation adds no shortcut automatically.

See [VALIDATION.md](VALIDATION.md) for test scope and remaining limits, and [BACKEND.md](../BACKEND.md) for bounded data and action behavior. No universal rollback, security audit, long-soak or performance claim.
