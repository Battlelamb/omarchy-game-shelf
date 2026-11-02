# Game Shelf backend · v0.4.0

## Exact CLI

From the checkout root:

```sh
/usr/bin/python3 runtime/0.4.0/backend.py catalog
/usr/bin/python3 runtime/0.4.0/backend.py preferences
/usr/bin/python3 runtime/0.4.0/backend.py preferences --apply --payload '{"options":{"provider":"steam","installed":"all","hideCompatibilityTools":true}}'
/usr/bin/python3 runtime/0.4.0/backend.py preferences --apply --payload '{"collections":{"Evening":["steam:42","lutris:native:7"]},"options":{"collection":"Evening"}}'
/usr/bin/python3 runtime/0.4.0/backend.py preferences --apply --payload '{"reset":true}'
/usr/bin/python3 runtime/0.4.0/backend.py action --id steam:42 --verb launch --apply
/usr/bin/python3 runtime/0.4.0/backend.py action --id steam:42 --verb open-folder --apply
/usr/bin/python3 runtime/0.4.0/backend.py action --id steam:42 --verb favorite --apply
```

Use exact IDs from your own local catalogue; sample IDs above do not assert installed games. These are all commands and verbs. `launch` is primary, `open-folder` and `favorite` secondary. No Restore, store, downloads, installer, arbitrary command/database/root/output path. Actions accept no payload. Catalogue and preference reads are nonmutating; every write/action requires `--apply`. Invalid arguments/fields/IDs/verbs fail with nonzero exit and a single JSON error, never a traceback or provider-output dump. Runtime paths derive from `__file__`, not cwd.

Catalogue output preserves rows/actions/actionLabel/message and adds preferences/settingsSchema. Rows include namespaced `provider`, boolean `installed`, optional `favorite:true`, `collection` and local raster `preview`. Successful favorite/launch actions return updated preferences when persistence succeeds. A zero launch-helper exit is **request acceptance, never proof of game startup or gameplay**. Recent state updates only after this acceptance; a storage error preserves the truthful external result and adds a warning. Opening folders does not add a game to Recent.

## Saved options and personal collections

| Option | Type/default | Values |
|---|---|---|
| `view` | enum, `all` | `all`, `favorites`, `recent` |
| `collection` | string, empty | Exact personal collection name <=256 characters; empty = all |
| `provider` | enum, `all` | `all`, `steam`, `lutris-native`, `lutris-flatpak` |
| `installed` | enum, `installed` | `installed`, `all`, `not-installed` |
| `hideCompatibilityTools` | boolean, `false` | Actual JSON `true` / `false`, not strings or integers |
| `density` | enum, `comfortable` | `comfortable`, `compact` |
| `layout` | enum, `grid` | `grid`, `list` |
| `sortOrder` | enum, `default` | `default`, `name`, `favorites-first` |

The three display enums are saved for the native view to interpret; they do not alter source membership or action dispatch. Old valid stores missing these keys receive the defaults on read without an automatic rewrite. Existing options, favorites, Recent and collections remain intact; Reset includes the new defaults.

Filters intersect before the display cap; Recent retains saved order. `hideCompatibilityTools` is an optional, case-insensitive bounded **name heuristic**, not a game-type database: `^(?:(?:ge-)?proton(?:$|[ 0-9-])|steam linux runtime(?:$|[ -])|steamworks common redistributables$)`. It inspects admitted labels only (<=160 characters), applies to all providers, and does not inspect runner names, execute a client or consult AppID lists. False positives/negatives are possible. Disabled by default, it composes with provider/installed/view/collection filters before row/byte capping; action authorization still uses full fresh installed membership. All/not-installed means known local metadata only, not an online library scan. Unknown personal collection names yield no rows. Favorite membership may include a freshly validated uninstalled local record; launch/open-folder still require the fresh installed membership scan, ignoring display filters. Saving arbitrary IDs never authorizes a client request.

Preference patches accept only options/favorites/collections. Options merge; a supplied favorites list or collections object replaces that whole section. Sole-key `{"reset":true}` resets preferences. Recent/version writes are forbidden. JSON object payload <=16,384 UTF-8 bytes; no duplicate keys, nonfinite numbers, unknown options, wrong types, controls or oversized lists/IDs. Sibling preferences.py enforces private, owned regular-file storage without following symlinks, bounded reads, locking and atomic replace; corruption fails without overwriting it. Reads create nothing. Storage: absolute `$XDG_CONFIG_HOME/omarchy/lego/game-shelf/preferences.json`, otherwise `$HOME/.config/omarchy/lego/game-shelf/preferences.json`. Maximum 512 favorites, 32 recents, 64 collections and 512 IDs per collection; IDs are nonempty control-free strings <=256 characters. Reset affects no game/client data.

New preference writes are preflighted under the store lock against an aggregate 128 KiB compact UTF-8 document budget before replacement. Individual list/text maxima do not imply their Cartesian maximum is supported. Legacy valid stores remain bounded to 16 MiB for reads and explicit Reset/recovery; a rejected write leaves the existing file unchanged. Replies use the common UTF-8 encoder below 1 MiB (including the newline, at most 1 MiB); the UI action parser uses the same strict byte ceiling. Oversized optional preference snapshots on successful commands are omitted with a warning, preserving `ok:true`; actual catalogue overflow still fails closed, without truncating saved data. A Recent-save failure likewise warns without reversing confirmed helper/export acceptance.

## Providers and validated folders

**Steam:** reads `$XDG_DATA_HOME/Steam` (absolute, default `~/.local/share/Steam`), `~/.steam/{steam,root}` and the known Flatpak Steam root, plus absolute existing libraries registered in bounded libraryfolders.vdf. Modern path objects and legacy indexed paths work; duplicate AppIDs use root precedence. Appmanifest filename/AppID must match a bounded canonical integer; names, StateFlags and install-directory components are validated, including resolved containment in that library's common directory. Installed means the full-installed state bit and an existing game directory. All/not-installed may include valid partial or absent-directory records, never malformed metadata.

Steam ID: `steam:<appid>`. Native `steam steam://rungameid/<appid>` is preferred; fallback is `flatpak run com.valvesoftware.Steam steam://rungameid/<appid>` only with CLI plus installed metadata marker. Open folder uses the freshly derived existing in-library directory, not a displayed string or payload.

**Lutris:** reads only `$XDG_DATA_HOME/lutris/pga.db` and the known Flatpak `~/.var/app/net.lutris.Lutris/data/lutris/pga.db`. Required games columns: id/name/slug/runner/installed. Installed must be integer 0/1 (default scan admits 1); optional directory, then prefix, then path supplies local folder metadata. SQLite is read-only/immutable/query-only, trusted_schema off, with a progress budget and no WAL/SHM creation. Unsupported/corrupt schemas report status. Immutable reads intentionally ignore uncheckpointed WAL: close/checkpoint the client and refresh.

Lutris IDs are `lutris:native:<id>` / `lutris:flatpak:<id>`. Launch uses numeric `lutris:rungameid/<id>`, never mutable slugs, and cannot substitute native/Flatpak clients. Flatpak uses fixed net.lutris.Lutris with its installed metadata marker. Open folder requires an exact control-free absolute existing directory <=512 characters from that fresh record, resolves it and rejects filesystem root, including symlink aliases. No truncation of an oversized directory is used to authorize opening. Catalogues do not invoke clients.

## Bounds and helper lifecycle

VDF: <=512 KiB, <=65,536 tokens, token <=4098 characters, depth <=16; quoted strings, escaped quotes/backslashes, braces and comments only, with duplicate keys rejected. At most 16 roots, 4096 Steam entries/root, 2048 manifests total, and 1024 admitted SQLite rows/provider; databases <=32 MiB. Display is <=1024 rows within an 800,000-byte row budget. Full scanned membership authorizes actions even beyond display limits. Action scans skip artwork without bypassing validation.

Optional local Steam flat/per-app/one-level-hashed cache covers and Lutris coverart/banners/icons remain supported. PNG/JPEG headers only, <=8 MiB, dimensions <=4096 and preview path <=512 characters; malformed image decoding may still fail. No SVG, fetching, image caches or bundled game art. Final JSON stays below 1 MiB; confirmed actions retain success if an optional snapshot must be omitted.

Helpers use literal argument vectors on normal PATH with discarded stdin/stdout/stderr. `/usr/bin/timeout --signal=KILL 3` is an independent group deadline; a five-second Python wait is backup. A client can partially accept before failure/timeout; cancellation cannot revoke an accepted launch. Successful games intentionally outlive their short request helper. No shell/eval or direct execution of game binaries.

## Offline verification

```sh
TMPDIR="${TMPDIR:?Set TMPDIR to an existing private scratch directory}" env -u PYTHONPATH PATH=/usr/bin /usr/bin/python3 scripts/run-tests.py --backend-only
```

All tests run through the shipped offline bwrap runner: cleared environment, fake HOME, no live sockets/network and production setters masked. Real VDF/SQLite/CLI parsing, private executable shims, folder readback, no-artwork action scans, failed-helper/deadline/descendant tests, preference validation and every shipped Python source compilation are covered. Fixtures establish adapter boundaries, not real installed-client behavior. Earlier release-output/v030-result.json describes v0.3.0 only. Current tests also cover compatibility-name boundaries, provider/installed/favorite/collection composition before display capping, strict boolean persistence/reset and saved-display-schema validation/migration. Native UI, real client integration, upgrade/rollback, hosted CI and publication are separate gates.
