# Game Shelf backend

## Operations and providers

Primary verb: `launch`. Steam and Lutris adapters are independent and optional. Readable metadata remains visible when its client is absent; launch then fails with a useful message. No installation, account access, cloud endpoint or client invocation occurs during catalogue discovery.

Steam roots: `$XDG_DATA_HOME/Steam` (default `$HOME/.local/share/Steam`), `$HOME/.steam/{steam,root}`, and the known Flatpak Steam data root. Only extra absolute local libraries registered in their bounded `steamapps/libraryfolders.vdf` are followed. Both modern path objects and legacy indexed paths work. A genuine appmanifest must have matching numeric filename/AppID, a fully-installed state bit, valid name and a present in-library common/install directory. Partial/uninstalled entries are excluded. Duplicate AppIDs merge by root precedence. Stable IDs are `steam:<appid>`; launch is native `steam steam://rungameid/<appid>` or fixed installed Flatpak Steam fallback.

Lutris reads only native `$XDG_DATA_HOME/lutris/pga.db` and the known Flatpak `~/.var/app/net.lutris.Lutris/data/lutris/pga.db`. Supported schema is a `games` table containing id/name/slug/runner/installed; optional directory/prefix/path supplies details. Only installed, bounded valid rows are shown. SQLite is read-only/immutable/query-only with trusted_schema off, a progress budget, 32 MiB database limit and no WAL/SHM creation. Unsupported/corrupt schemas report status; no guessed fallback SQL or arbitrary --db path is supported.

Stable IDs are `lutris:native:<id>` or `lutris:flatpak:<id>`, so equal numeric IDs in different databases never collide. Launch uses numeric `lutris:rungameid/<id>`, not the mutable slug. Native and Flatpak databases cannot be substituted: the selected provider must have its own client. Flatpak invocation uses only fixed application IDs and requires an installed application metadata marker plus existing flatpak CLI. Provider launch identifiers come only from fresh known membership.

Action membership uses `game_data(with_previews=False)`, propagated through the existing Steam and Lutris row builders. Only optional artwork discovery is skipped; roots, bounds, installed-state validation, provider identity and fresh full membership are unchanged. Normal catalogues retain previews.

## Bounds, artwork and limitations

VDF input <=512 KiB, token length <=4098, <=65,536 tokens and depth <=16; quoted strings, braces, escaped quotes/backslashes and // comments are supported. Duplicate fields, invalid syntax and unknown grammar fail the record. Up to 16 roots, 4,096 directory entries per Steam root, 2,048 manifests total; Lutris reads at most 1,024 matching rows per provider with bounded field lengths. The catalogue emits at most 1,024 rows within an 800,000-byte row budget and tells the user when display is limited; full scanned membership validates actions.

Details include real game name, provider, numeric ID, Steam install-directory component or Lutris slug/runner/available directory metadata. Steam flat, per-app and one-level hashed library-cache artwork and Lutris coverart/banners/icons are discovered locally. PNG/JPEG raster headers are checked (<=8 MiB, dimensions <=4096, path <=512); corrupt images may still fail actual decoding. No SVG, remote fetching, new cache files or image redistribution occurs.

Lutris immutable reads deliberately ignore an uncheckpointed WAL: close/checkpoint the client and refresh to see the latest changes. Only the explicit pga.db schema above is supported; binary Steam appinfo, arbitrary game launch commands, standalone game executables and generic recursive library/database scans are excluded. A zero client exit confirms request acceptance only; actual running-game state is not checked. A slow client can time out after partially accepting a launch. Optional-provider/Flatpak behavior is exercised with test shims, not actual installed clients.

## CLI and safety contract

Run with `/usr/bin/python3 runtime/0.2.1/backend.py catalog`, or `action --id <exact-known-id> --verb <primary-verb> --apply`. The catalogue is read-only. Runtime/data paths derive from `__file__`, never cwd. One bounded JSON object is emitted; errors are JSON with nonzero exit and no traceback/provider output. Unknown IDs/verbs, missing `--apply`, unavailable providers, nonzero helper exits and deadlines fail closed. Selection is checked against fresh full bounded membership, not the displayed list. **No restore operation is supported or advertised**: copying and launching do not have a meaningful reversible restore.

Actions use literal argument vectors, no shell/eval, no execution of commands from displayed metadata. Helpers are found on normal PATH (tests replace it with a private shim directory); their stdin/stdout/stderr are discarded. GNU `/usr/bin/timeout --signal=KILL 3` supplies an independent process-group deadline even if the QML-owned backend is killed; a five-second Python wait is backup. An already-successful app launch/clipboard ownership can intentionally outlive its short helper. Cancelling after dispatch cannot revoke an accepted action. A timeout does not prove that the request had no effect.

Success means a completed helper exited zero and accepted the request. It is **not proof of actual app/game startup or live clipboard ownership**. The latter require an explicitly authorized native session test. No clients, fonts, packages or dependencies are installed; no bindings, themes, configs, services or live IPC are changed by this implementation task.

## Tests and receipts

From this project's root, use the shipped offline runner with TMPDIR naming an existing approved private scratch directory:

```sh
TMPDIR="${TMPDIR:?Set TMPDIR to an existing private scratch directory}" env -u PYTHONPATH PATH=/usr/bin /usr/bin/python3 scripts/run-tests.py --backend-only
```

The shipped runner invokes `/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v` inside bwrap, with `--unshare-all --clearenv`, read-only `/usr` and source, fake HOME, private proc/dev/tmp/run, no network, no live HOME, display, Hyprland or session bus. It masks production theme/background/shell setters and streams results without creating receipts. No package installation or GUI is involved. The isolation test verifies loopback-only networking, an unreachable external test address, absent live paths/sockets and cleared session variables.

The private `release-output/run-backend-tests.py` runner and ignored `release-output/` receipts below are historical development evidence, not shipped files or prerequisites for the public test command.

Feature-specific RED/GREEN receipts are immutable under ignored `release-output/`; earlier failed runs are retained, not overwritten. Tests run real parsers and CLI entry points against synthetic local files/SQLite and literal executable shims. They cover selected metadata, helper acknowledgement and observable argv logs, malformed/oversized/nonregular inputs, missing clients, revalidation, unknown selections and deadline failure. The cancellation test checks an actual TERM-ignoring descendant becomes non-running after its backend is terminated. Shims establish the adapter boundary only, not genuine client integration. `release-output/backend-result.json` records counted methods, final receipt and exact source hashes. UI/package/README integration remains parent-owned.

Final backend receipt: `final-backend-clean-GREEN.txt`: **20 test methods passed, zero failures/errors, no warnings**.

Artwork-work correction: `release-output/ponytail-fixes-1793557673318497712/{RED.log,GREEN.log,completion.json}` records strict RED→GREEN with **21 methods passing** in `env -u PYTHONPATH /usr/bin/python3 scripts/run-tests.py --backend-only`. A Python audit hook counts actual raster-file open attempts (including missing files) in fresh backend subprocesses, without replacing filesystem reads. The mixed Steam/native-Lutris/Flatpak-Lutris fixture retains 30 catalogue artwork opens and all three valid previews; each of nine valid/rejected actions drops to zero artwork opens. Literal provider-specific shim argv remains unchanged; changed Steam/Lutris installed state, removed Flatpak markers and invalid IDs still fail closed. These are operation counts, not measured latency or real game startup.
