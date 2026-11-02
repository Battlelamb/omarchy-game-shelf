# Backend source and asset notice

The backend and tests are original GPL-3.0-only code implementing narrowly ported behavior after source review. No HyDE script is executed or vendored at runtime. Each backend is independent and uses Python standard-library modules and existing system CLI tools only.

## Reviewed HyDE lineage

The v0.3.0 preference/collection/provider filters and validated folder-opening logic are original GPL-3.0-only additions using the standard library and existing helpers. No new donor code, game art, client binary or online catalogue was added.

Repository: https://github.com/HyDE-Project/HyDE

Pinned commit: `fa2fd57afc7203b1b5653d3271f3a57ea3873f97`. Upstream repository license is GNU GPL version 3; this does not determine individual dataset/font/image rights.

- `Configs/.local/lib/hyde/gamelauncher.sh` — SHA-256 `d6b2a9a4035a65e7274ce878eea3049cea3fe4ab717e84283073262d64a9bea9`
- `Configs/.local/lib/hyde/gamelauncher/catalog.py` — SHA-256 `33316c9c9bbc816e509698767c69e541376763bfd23780498f220e2d16b09483`
- `Configs/.local/lib/hyde/gamelauncher/steam.py` — SHA-256 `72f2390c6fede664ec0bbd413ed3aac7d7ff1e637136a1d2edcbaa17ac961f66`
- `Configs/.local/lib/hyde/gamelauncher/lutris.py` — SHA-256 `5ec41b3f282d69d0e5e192a9240e458d854332085da0dbf7000de7b347e1d34a`

Behavior carried over: separate Steam and Lutris catalogues, known native/Flatpak metadata roots, installed app manifests, local artwork lookup and namespaced identities. Shell command strings, eval, Rofi markup, network icon requests, requests dependency, generic recursive database scans and arbitrary --db paths were excluded. VDF parsing, SQLite validation and literal argv dispatch are newly written.

The numeric Lutris URI contract was independently checked in upstream Lutris v0.5.19 `lutris/gui/application.py` (lines 117–120): `lutris:rungameid/numerical-id`. That source was inspected only; no Lutris code is bundled. Steam uses a numeric `steam://rungameid/<appid>` request. No game/client binaries or copyrighted cover art are distributed. Local artwork paths are discovered only on the user's machine; no downloads, caches or copies are made.

Tests create synthetic desktop entries, manifests and SQLite databases in fake HOME. The tiny one-pixel raster fixture is test data, not a real application/game asset. Backend action receipts prove literal argv and helper acknowledgement through private executable shims, not live clipboard ownership or actual app/game startup.
