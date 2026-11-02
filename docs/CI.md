# Component CI scope

The independent GitHub Actions workflow uses read-only repository permissions and a full-commit-pinned checkout with credential persistence disabled. It runs the Node controller/UI/polish source-contract tests, the Python package-identity checker, and Python syntax compilation. It installs no plugin and runs no desktop action.

It deliberately does **not** run backend action/provider tests, native Qt checks, the native runner/receipt tests, GPU trials, live IPC, long-soak/resource tests, accessibility, RTL or display scaling. Those require separate local qualification; a green component job is not proof of them.

Hosted CI has not run. The exact component commands are exercised locally in a private offline namespace before sealing; this is not a GitHub-hosted result. After publication, require the real hosted run on the exact published commit before calling hosted CI green.
