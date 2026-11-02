#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Bounded offline Steam/Lutris metadata adapters; no installers or downloads."""
from contextlib import closing
from itertools import islice
from pathlib import Path
import argparse
import json
import math
import os
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preferences

SLUG = 'game-shelf'
PREFERENCE_SCHEMA = {
    'view': {'type':'enum', 'default':'all', 'label':'Show', 'choices':['all','favorites','recent']},
    'collection': {'type':'string', 'default':'', 'label':'Personal collection (empty = all)', 'maxLength':256},
    'provider': {'type':'enum', 'default':'all', 'label':'Provider', 'choices':['all','steam','lutris-native','lutris-flatpak']},
    'installed': {'type':'enum', 'default':'installed', 'label':'Installed state', 'choices':['installed','all','not-installed']},
}


def preference_metadata(rows=None):
    prefs = preferences.read(SLUG, PREFERENCE_SCHEMA)
    if rows is not None:
        view, collection = prefs['options']['view'], prefs['options']['collection']
        if view != 'all':
            members = prefs[view if view == 'favorites' else 'recent']
            rows[:] = [row for row in rows if row['id'] in members]
            if view == 'recent':
                rows.sort(key=lambda row: members.index(row['id']))
        if collection:
            rows[:] = [row for row in rows if row['id'] in prefs['collections'].get(collection, [])]
            for row in rows:
                row['collection'] = collection
    for row in rows or []:
        if row['id'] in prefs['favorites']:
            row['favorite'] = True
    return {'preferences': prefs, 'settingsSchema': PREFERENCE_SCHEMA}


def bounded_read(path, limit=524288):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Metadata must be a regular file.')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Metadata exceeds the supported byte limit.')
    return raw


def plain(value, limit=160):
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return ''
    return value.strip()[:limit]


def vdf(path):
    text = bounded_read(path).decode('utf-8-sig')
    pattern = re.compile(r'\s+|//[^\n]*|"(?:\\["\\]|[^"\\])*"|[{}]')
    tokens, pos = [], 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match:
            raise ValueError('Unsupported VDF syntax.')
        token = match.group()
        pos = match.end()
        if token.isspace() or token.startswith('//'):
            continue
        if len(token) > 4098 or len(tokens) >= 65536:
            raise ValueError('VDF token limit exceeded.')
        tokens.append(token)
    cursor = 0
    def object_value(depth=0):
        nonlocal cursor
        if depth > 16:
            raise ValueError('VDF nesting limit exceeded.')
        out = {}
        while cursor < len(tokens):
            token = tokens[cursor]
            if token == '}':
                if depth == 0:
                    raise ValueError('Unexpected VDF closing brace.')
                cursor += 1
                return out
            if not token.startswith('"'):
                raise ValueError('Expected a VDF key.')
            key = re.sub(r'\\(["\\])', r'\1', token[1:-1]).lower()
            cursor += 1
            if key in out or cursor == len(tokens):
                raise ValueError('Duplicate or incomplete VDF field.')
            value = tokens[cursor]
            cursor += 1
            if value == '{':
                value = object_value(depth + 1)
            elif value.startswith('"'):
                value = re.sub(r'\\(["\\])', r'\1', value[1:-1])
            else:
                raise ValueError('Expected a VDF value.')
            out[key] = value
        if depth:
            raise ValueError('Unclosed VDF object.')
        return out
    return object_value()


def data_home():
    value = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))
    return value if value.is_absolute() else Path.home()/'.local/share'


def steam_roots():
    home = Path.home()
    initial = [data_home()/'Steam', home/'.steam/steam', home/'.steam/root',
               home/'.var/app/com.valvesoftware.Steam/.local/share/Steam']
    roots = []
    for root in initial:
        if root.is_dir() and root.resolve() not in roots:
            roots.append(root.resolve())
    extras = []
    for root in roots:
        try:
            libraries = vdf(root/'steamapps/libraryfolders.vdf').get('libraryfolders', {})
            if not isinstance(libraries, dict):
                continue
            for key, value in list(libraries.items())[:32]:
                if not re.fullmatch(r'[0-9]{1,3}', key):
                    continue
                name = value.get('path') if isinstance(value, dict) else value
                if isinstance(name, str) and plain(name, 512) == name and len(name) <= 512:
                    candidate = Path(name)
                    if candidate.is_absolute() and candidate.is_dir():
                        extras.append(candidate.resolve())
        except (OSError, ValueError, UnicodeError):
            continue
    return list(dict.fromkeys(roots + extras))[:16]


def local_image(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 24 <= info.st_size <= 8388608:
                return None
            raw = stream.read(65536)
        width = height = 0
        if raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[12:16] == b'IHDR':
            width, height = int.from_bytes(raw[16:20]), int.from_bytes(raw[20:24])
        elif raw.startswith(b'\xff\xd8'):
            pos = 2
            while pos + 8 < len(raw) and raw[pos] == 255:
                marker = raw[pos+1]
                if marker == 255:
                    pos += 1
                    continue
                length = int.from_bytes(raw[pos+2:pos+4])
                if length < 2:
                    break
                if marker in (192,193,194):
                    height, width = int.from_bytes(raw[pos+5:pos+7]), int.from_bytes(raw[pos+7:pos+9])
                    break
                pos += length + 2
        resolved = str(path.resolve())
        if 0 < width <= 4096 and 0 < height <= 4096 and len(resolved) <= 512:
            return resolved
    except (OSError, ValueError):
        return None
    return None


def steam_cover(ident, roots):
    names = ('library_600x900', 'library_capsule', 'library_hero', 'header')
    for name in names:
        for root in roots:
            cache = root/'appcache/librarycache'
            folders = [cache/ident]
            try:
                with os.scandir(cache/ident) as entries:
                    folders += [Path(e.path) for e in islice(entries, 16) if e.is_dir(follow_symlinks=False)]
            except OSError:
                folders = [cache/ident]
            for folder in [cache] + folders:
                for ext in ('.jpg', '.png', '.jpeg'):
                    candidate = folder/((ident+'_' if folder == cache else '')+name+ext)
                    image = local_image(candidate)
                    if image:
                        return image
    return None


def lutris_cover(provider, slug):
    root = data_home()/'lutris' if provider == 'native' else Path.home()/'.var/app/net.lutris.Lutris/data/lutris'
    for folder in ('coverart', 'banners', 'icons'):
        for ext in ('.jpg','.png','.jpeg'):
            image = local_image(root/folder/(slug+ext))
            if image:
                return image
    return None


def steam_rows(with_previews=True, with_folders=False, include_uninstalled=False):
    rows, seen, skipped, budget = [], set(), 0, 2048
    roots = steam_roots()
    for root in roots:
        try:
            with os.scandir(root/'steamapps') as entries:
                paths = sorted((Path(e.path) for e in islice(entries, 4096) if re.fullmatch(r'appmanifest_[1-9][0-9]{0,9}\.acf', e.name)))
        except OSError:
            continue
        for path in paths[:budget]:
            budget -= 1
            try:
                values = vdf(path).get('appstate')
                if not isinstance(values, dict):
                    raise ValueError('Missing AppState.')
                ident = values.get('appid', '')
                name = plain(values.get('name'))
                component = values.get('installdir', '')
                state = values.get('stateflags', '')
                if not isinstance(ident, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', ident) or int(ident) > 4294967295:
                    raise ValueError('Invalid Steam AppID.')
                if path.name != f'appmanifest_{ident}.acf' or not name:
                    raise ValueError('Inconsistent Steam record.')
                if not isinstance(component, str) or not component or plain(component) != component or component in ('.','..') or '/' in component or '\\' in component:
                    raise ValueError('Invalid install directory.')
                install = root/'steamapps/common'/component
                if not isinstance(state, str) or not re.fullmatch(r'[0-9]{1,10}', state):
                    raise ValueError('Invalid installed-state metadata.')
                installed = bool(int(state) & 4) and install.is_dir()
                if not installed and not include_uninstalled:
                    continue
                if not install.resolve().is_relative_to((root/'steamapps/common').resolve()):
                    raise ValueError('Install directory escapes the Steam library.')
                if ident in seen:
                    continue
                seen.add(ident)
                row = {'id':'steam:'+ident, 'label':name, 'detail':f'Steam · AppID {ident} · {component}', 'provider':'steam', 'installed':installed}
                if with_folders:
                    row['_folder'] = str(install.resolve())
                image = steam_cover(ident, roots) if with_previews else None
                if image:
                    row['preview'] = image
                rows.append(row)
            except (OSError, ValueError, UnicodeError):
                skipped += 1
        if budget == 0:
            break
    return rows, skipped


def lutris_rows(with_previews=True, with_folders=False, include_uninstalled=False):
    locations = [('native', data_home()/'lutris/pga.db'),
                 ('flatpak', Path.home()/'.var/app/net.lutris.Lutris/data/lutris/pga.db')]
    rows, notes = [], []
    for provider, path in locations:
        if not path.exists():
            continue
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > 33554432:
                raise ValueError('Lutris database unreadable or exceeds 32 MiB limit.')
            # Immutable avoids creating WAL/SHM files; refresh after the client checkpoints.
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1', uri=True, timeout=0.2)) as conn:
                conn.execute('PRAGMA query_only=ON')
                conn.execute('PRAGMA trusted_schema=OFF')
                conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1048576)
                conn.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 32)
                fuel = [0]
                def progress():
                    fuel[0] += 1
                    return int(fuel[0] > 100)
                conn.set_progress_handler(progress, 1000)
                columns = {r[1] for r in conn.execute('PRAGMA table_info(games)')}
                if not {'id','name','slug','runner','installed'} <= columns:
                    raise ValueError('Lutris database schema unsupported; required installed-game fields are missing.')
                directory = next((c for c in ('directory','prefix','path') if c in columns), None)
                selected = f'CASE WHEN length({directory})<=512 THEN {directory} ELSE NULL END' if directory else "''"
                state_filter = 'installed IN (0,1)' if include_uninstalled else 'installed=1'
                query = 'SELECT id,name,slug,runner,'+selected+',installed FROM games WHERE '+state_filter+' AND typeof(installed)=\'integer\' AND typeof(id)=\'integer\' AND id>0 AND id<=2147483647 AND length(name) BETWEEN 1 AND 160 AND length(slug) BETWEEN 1 AND 96 AND length(runner) BETWEEN 1 AND 64 ORDER BY id LIMIT 1024'
                records = list(conn.execute(query))
            seen = set()
            for ident, name, slug, runner, directory, installed in records:
                if ident in seen or not plain(name) or not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,95}', slug) or not plain(runner,64):
                    continue
                seen.add(ident)
                detail = f'Lutris ({provider}) · ID {ident} · {slug} · {runner}'
                if plain(directory):
                    detail += ' · '+plain(directory)
                row = {'id':f'lutris:{provider}:{ident}', 'label':name, 'detail':detail[:500], 'provider':'lutris-'+provider, 'installed':bool(installed)}
                if with_folders and isinstance(directory, str) and plain(directory, 512) == directory:
                    folder = Path(directory)
                    if folder.is_absolute() and folder.is_dir():
                        folder = folder.resolve()
                        if folder != Path('/'):
                            row['_folder'] = str(folder)
                image = lutris_cover(provider, slug) if with_previews else None
                if image:
                    row['preview'] = image
                rows.append(row)
        except ValueError as error:
            notes.append(str(error))
        except (OSError, sqlite3.Error):
            notes.append('Lutris database unreadable; close the client, checkpoint it and refresh.')
    return rows, notes


def game_data(with_previews=True, with_folders=False, include_uninstalled=False):
    steam, skipped = steam_rows(with_previews=with_previews, with_folders=with_folders, include_uninstalled=include_uninstalled)
    lutris, notes = lutris_rows(with_previews=with_previews, with_folders=with_folders, include_uninstalled=include_uninstalled)
    rows = steam + lutris
    status = 'Steam client available.' if shutil.which('steam') or flatpak_installed('com.valvesoftware.Steam') else 'Steam client unavailable; metadata only.'
    lutris_status = 'Lutris client available (provider must match the selected database).' if shutil.which('lutris') or flatpak_installed('net.lutris.Lutris') else 'Lutris client unavailable; metadata only.'
    return rows, f'{len(rows)} local game records; {sum(r["installed"] for r in rows)} installed (bounded scan). {status} {lutris_status} {skipped} invalid Steam records skipped. '+ ' '.join(notes)


def displayed_rows(rows):
    out, size = [], 2
    for row in rows:
        amount = len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) + 1
        if len(out) >= 1024 or size + amount > 800000:
            break
        size += amount
        out.append(row)
    return out


def catalog():
    options = preferences.read(SLUG, PREFERENCE_SCHEMA)['options']
    rows, message = game_data(include_uninstalled=options['installed'] != 'installed')
    metadata = preference_metadata(rows)
    provider = metadata['preferences']['options']['provider']
    if provider != 'all':
        rows = [row for row in rows if row['provider'] == provider]
    if options['installed'] == 'not-installed':
        rows = [row for row in rows if not row['installed']]
    shown = displayed_rows(rows)
    if len(shown) < len(rows):
        message += ' Display limited; full scanned membership remains validated for actions.'
    return {**metadata, 'rows':shown,'message':message,'actions':['launch','open-folder','favorite'],'actionLabel':'Launch'}


def flatpak_installed(appid):
    locations = [data_home()/'flatpak/app'/appid/'current/active/metadata',
                 Path('/var/lib/flatpak/app')/appid/'current/active/metadata']
    return shutil.which('flatpak') and any(p.is_file() for p in locations)


def launch_argv(ident):
    if ident.startswith('steam:'):
        uri = 'steam://rungameid/'+ident.split(':')[1]
        if shutil.which('steam'):
            return ['steam', uri]
        if flatpak_installed('com.valvesoftware.Steam'):
            return ['flatpak', 'run', 'com.valvesoftware.Steam', uri]
        raise ValueError('Steam client unavailable; install it separately to launch this game.')
    _, provider, number = ident.split(':')
    uri = 'lutris:rungameid/'+number
    if provider == 'native' and shutil.which('lutris'):
        return ['lutris', uri]
    if provider == 'flatpak' and flatpak_installed('net.lutris.Lutris'):
        return ['flatpak', 'run', 'net.lutris.Lutris', uri]
    raise ValueError('Matching Lutris client unavailable; native and Flatpak databases cannot be interchanged.')


def run_helper(argv):
    executable = shutil.which(argv[0])
    if not executable:
        raise ValueError('Selected game client is unavailable; configure it separately.')
    # A separate deadline survives cancellation/destruction of the QML-owned backend.
    with subprocess.Popen(['/usr/bin/timeout', '--signal=KILL', '3', executable, *argv[1:]], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True) as proc:
        try:
            code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise ValueError('Client timed out; launch request completion is unconfirmed.') from None
    if code in (124, -signal.SIGKILL):
        raise ValueError('Helper timed out; request completion is unconfirmed.')
    if code != 0:
        raise ValueError(f'Client rejected the request (exit {code}); check the client separately.')


def payload_object(raw):
    if len(raw.encode('utf-8')) > 16384:
        raise ValueError('Payload exceeds 16384 UTF-8 bytes.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate payload key.')
            result[key] = value
        return result
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite payload number.')
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite payload number.')))
    except (json.JSONDecodeError, RecursionError):
        raise ValueError('Payload must be a bounded JSON object.') from None
    if not isinstance(result, dict):
        raise ValueError('Payload must be a JSON object.')
    return result


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('Invalid arguments; use catalog or action --id ID --verb launch --apply.')


def main():
    try:
        parser = Parser(allow_abbrev=False, add_help=False)
        parser.add_argument('command', choices=['catalog', 'action', 'preferences'])
        parser.add_argument('--id')
        parser.add_argument('--verb')
        parser.add_argument('--payload')
        parser.add_argument('--apply', action='store_true')
        args = parser.parse_args()
        if args.command == 'preferences':
            if args.id is not None or args.verb is not None:
                raise ValueError('Preferences do not accept selection arguments.')
            if args.payload is None:
                if args.apply:
                    raise ValueError('Preference writes require a payload.')
                result = {'ok': True, 'message': 'Saved preferences.', **preference_metadata()}
            else:
                if not args.apply:
                    raise ValueError('Explicit --apply is required; nothing changed.')
                patch = payload_object(args.payload)
                if set(patch) == {'reset'} and patch['reset'] is True:
                    prefs = preferences.reset(SLUG, PREFERENCE_SCHEMA)
                else:
                    prefs = preferences.change(SLUG, PREFERENCE_SCHEMA, patch)
                result = {'ok': True, 'message': 'Preferences saved.', 'preferences': prefs, 'settingsSchema': PREFERENCE_SCHEMA}
        elif args.command == 'catalog':
            if args.id is not None or args.verb is not None or args.apply or args.payload is not None:
                raise ValueError('Catalog does not accept action arguments.')
            result = catalog()
        elif args.verb == 'favorite':
            if not args.apply or args.payload is not None:
                raise ValueError('Favorite requires --apply and no payload.')
            known, _ = game_data(with_previews=False, include_uninstalled=True)
            if not any(row['id'] == args.id for row in known):
                raise ValueError('Selection is unknown; refresh the catalogue.')
            result = {'ok': True, 'message': 'Favorite updated.', 'preferences': preferences.toggle(SLUG, PREFERENCE_SCHEMA, args.id)}
        else:
            if args.payload is not None:
                raise ValueError('This action does not accept a payload.')
            if not args.apply:
                raise ValueError('Explicit --apply is required; nothing changed.')
            if args.verb not in ('launch', 'open-folder'):
                raise ValueError('Unsupported action; use launch or open-folder.')
            known, _ = game_data(with_previews=False, with_folders=args.verb == 'open-folder')
            row = next((r for r in known if r['id'] == args.id), None)
            if row is None:
                raise ValueError('Selection is unknown or no longer installed; refresh the catalogue.')
            if args.verb == 'open-folder':
                folder = row.get('_folder')
                if not folder or not Path(folder).is_dir():
                    raise ValueError('No validated existing game folder is available for this selection.')
                run_helper(['xdg-open', folder])
                result = {'ok':True, 'message':'Folder helper accepted the selected game directory.'}
            else:
                run_helper(launch_argv(args.id))
                result = {'ok':True, 'message':'Game client accepted the launch request; game startup is not confirmed.'}
        if args.command == 'action' and args.verb == 'launch':
            try:
                result['preferences'] = preferences.remember(SLUG, PREFERENCE_SCHEMA, args.id)
            except (ValueError, OSError, UnicodeError):
                result['message'] += ' Warning: recent selection could not be saved.'
        code = 0
    except (ValueError, OSError, UnicodeError) as error:
        result = {'ok':False, 'message':str(error)[:240] if isinstance(error, ValueError) else 'Local metadata unavailable; check permissions and refresh.'}
        code = 1
    try:
        text = preferences.encode_reply(result)
    except ValueError:
        text = preferences.encode_reply({'ok': False, 'message': 'Catalogue exceeds the 1 MiB output limit.'})
        code = 1
    print(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
