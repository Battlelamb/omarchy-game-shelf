# Component CI scope

The independent [workflow](../.github/workflows/ci.yml) uses read-only repository permissions, a full-commit-pinned checkout and disabled credential persistence. It runs:

- Package identity checks and Python syntax compilation.
- Node controller/UI/polish, preferences-editor and saved-display contracts.
- Standalone Python preference-store regressions in a cleared, temporary fake HOME.
- Copied-package missing-file controls for the required standalone files.

It installs no plugin and performs no desktop action. It does **not** run domain backend/provider actions, native Qt/process tests, GPU trials, live IPC, full-shell upgrade/rollback, long-soak/resource, accessibility, RTL or scaling qualification. A green component job is not evidence for those.

Check [GitHub Actions](https://github.com/Battlelamb/omarchy-game-shelf/actions/workflows/ci.yml) on the exact published commit for hosted status. Local component results do not establish a GitHub-hosted pass.
