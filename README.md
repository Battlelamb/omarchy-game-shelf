# Game Shelf

Browse locally installed Steam and Lutris games without replacing their clients.

**Local implementation candidate. Not installed, not published and not yet visually approved.**

## Use after deliberate installation

Requires the Omarchy Quattro shell, its installed Quickshell/Qt APIs, system Python 3 and the backend tools documented in [BACKEND.md](BACKEND.md). This is not a standalone shell. No other Lego plugin is required.

```bash
omarchy plugin add /srv/projects/omarchy-game-shelf --enable
omarchy-shell shell toggle leviathan.game-shelf '{}'
```

These are future install/use commands, not commands run during this task. The plugin is not enabled automatically by building it. No shortcut is created.

Type to search; arrows select; Enter or the primary button explicitly acts. Clicking a card selects it only. Refresh rereads the catalogue; Escape/outside dismiss. Restore/Keep effect are shown only when the backend advertises them. Actions use fresh backend membership, not arbitrary row commands. Backend details and limitations: [BACKEND.md](BACKEND.md).

The interface uses native shell colours, reduced-motion behavior, plain-text labels, translated strings (English fallback), virtualized bounded result grids and local image previews. Full IME/accessibility/theme/multi-output qualification remains unverified until recorded.

## Verify without opening windows

```bash
bash test.sh
```

The runner uses no-network bubblewrap with fake HOME and a cleared environment; Node controller/source-handler checks and Python backend tests use fixtures. Shimmed external-tool tests establish adapter behavior, not real GPU/game/theme success. No `test.sh` command opens an overlay or uses the real clipboard. Native private-session coverage, if performed, is separately recorded in docs/VALIDATION.md.

## Safety

Runs unsandboxed inside the user's existing shell when deliberately installed. Clipboard/app/theme/compositor actions are explicit; inspect their scope in BACKEND.md. No new system packages, login/boot/driver changes, automatic keybinding edits or external services are supplied. The native component stays loaded while enabled to retain in-flight cleanup ownership, but closed overlays do not run their catalogue or lock polling; explicit state-changing actions have bounded ownership and rollback limitations documented by the backend. The stock launcher, emoji picker, notification/clipboard services and wallpaper engine remain independent.

## Disable

```bash
omarchy-shell shell hide leviathan.game-shelf
omarchy plugin disable leviathan.game-shelf
```

Do not remove a checkout containing unsaved changes. Disabling a plugin does not magically undo a previously completed user action; use its Restore capability where supported.

Licence: GPL-3.0-only. Exact source/dataset notices: NOTICE.md and NOTICE.backend.md.
