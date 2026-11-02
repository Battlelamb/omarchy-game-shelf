# SPDX-License-Identifier: GPL-3.0-only
"""Private locked preferences; IDs never authorize external actions.

New writes: at most 128 KiB aggregate compact UTF-8 JSON, in addition to field
limits (not a Cartesian-maximum guarantee). Legacy reads remain bounded to
16 MiB and fully validated, so explicit Reset can shrink old valid stores.
An overbudget update never replaces existing bytes; recovery is independent.
"""
import contextlib
import copy
import fcntl
import json
import os
import re
import secrets
import stat
import time
import unicodedata

MAX_BYTES = 16 * 1024 * 1024
WRITE_BYTES = 128 * 1024
REPLY_BYTES = 1024 * 1024


def encode_reply(result):
    """Encode below the transport cap; never turn confirmed success into failure.

    Catalogues (rows) fail closed on overflow. An ok:true command may omit only
    its optional preference snapshot, retaining the status with a plain warning.
    Domain formatters remain responsible for bounding all other reply fields.
    """
    def encode(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    raw = encode(result)
    if len(raw.encode('utf-8')) < REPLY_BYTES:
        return raw
    if isinstance(result, dict) and result.get('ok') is True and 'rows' not in result and 'preferences' in result:
        result = dict(result)
        del result['preferences']
        result['message'] = result.get('message', 'Done') + '; warning: preference snapshot omitted because it exceeds the reply limit'
        raw = encode(result)
        if len(raw.encode('utf-8')) < REPLY_BYTES:
            return raw
    raise ValueError('Reply exceeds the 1 MiB transport limit')


def _text(value, limit, nonempty=False):
    if not isinstance(value, str) or len(value) > limit or (nonempty and not value):
        raise ValueError('Invalid preference text')
    try:
        if len(value.encode('utf-8')) > 4096 or any(unicodedata.category(c) in ('Cc', 'Cs') for c in value):
            raise ValueError('Invalid preference text')
    except UnicodeError:
        raise ValueError('Invalid preference text') from None
    return value


def _ids(value, limit):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError('Too many preference IDs or invalid list')
    result = [_text(item, 256, True) for item in value]
    if len(set(result)) != len(result):
        raise ValueError('Duplicate preference IDs')
    return result


def _option(value, spec):
    kind = spec.get('type')
    if kind == 'enum':
        if not isinstance(value, str) or value not in spec.get('choices', []):
            raise ValueError('Invalid option choice')
        _text(value, 4096)
    elif kind == 'boolean':
        if type(value) is not bool:
            raise ValueError('Option must be boolean')
    elif kind == 'integer':
        if type(value) is not int or not spec.get('minimum', -2147483648) <= value <= spec.get('maximum', 2147483647):
            raise ValueError('Option integer is outside its range')
    elif kind == 'string':
        _text(value, min(4096, spec.get('maxLength', 4096)))
    elif kind == 'string-list':
        if not isinstance(value, list) or len(value) > 32:
            raise ValueError('Option must be a list of at most 32 strings')
        for item in value:
            _text(item, min(4096, spec.get('maxLength', 4096)))
    else:
        raise ValueError('Unsupported option schema')
    return copy.deepcopy(value)


def _options(value, schema):
    if not isinstance(value, dict) or set(value) - set(schema):
        raise ValueError('Unknown preference option')
    return {key: _option(value.get(key, spec['default']), spec) for key, spec in schema.items()}


def _defaults(schema):
    return {'version': 1, 'favorites': [], 'recent': [], 'collections': {}, 'options': _options({}, schema)}


def _validate(value, schema):
    if not isinstance(value, dict) or set(value) != {'version', 'favorites', 'recent', 'collections', 'options'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid preference document')
    groups = value['collections']
    if not isinstance(groups, dict) or len(groups) > 64:
        raise ValueError('Invalid preference collections')
    return {'version': 1, 'favorites': _ids(value['favorites'], 512), 'recent': _ids(value['recent'], 32),
            'collections': {_text(name, 256, True): _ids(ids, 512) for name, ids in groups.items()},
            'options': _options(value['options'], schema)}


@contextlib.contextmanager
def _directory(slug, create=False):
    if not isinstance(slug, str) or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug) or len(slug) > 80:
        raise ValueError('Invalid preference plugin name')
    base = os.environ.get('XDG_CONFIG_HOME')
    if not base or not os.path.isabs(base):
        home = os.environ.get('HOME', '')
        if not os.path.isabs(home):
            raise ValueError('Preference HOME must be absolute')
        base = os.path.join(home, '.config')
    parts = [p for p in base.split('/') if p] + ['omarchy', 'lego', slug]
    if any(p in ('.', '..') for p in parts):
        raise ValueError('Invalid preference directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(parts):
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            # The shared omarchy directory also contains unrelated native config.
            if index >= len(parts) - 2:
                info = os.fstat(fd)
                if info.st_uid != os.getuid():
                    raise ValueError('Preference directory has a different owner')
                if create:
                    os.fchmod(fd, 0o700)
                elif info.st_mode & 0o077:
                    raise ValueError('Preference directory is not private')
        yield fd
    except OSError:
        raise ValueError('Cannot safely access preference directory') from None
    finally:
        os.close(fd)


def _regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077:
        raise ValueError('Preference file must be a private owned regular file')
    return info


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate preference key')
        result[key] = value
    return result


def _load(fd, schema):
    if fd is None:
        return _defaults(schema)
    try:
        file = os.open('preferences.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return _defaults(schema)
    except OSError:
        raise ValueError('Cannot safely open preference file') from None
    try:
        info = _regular(file)
        if info.st_size > MAX_BYTES:
            raise ValueError('Preference file is too large')
        with os.fdopen(file, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Preference file is too large')
        after = os.fstat(file)
        if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('Preference file changed while reading')
        return _validate(json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite preference number'))), schema)
    except (UnicodeError, RecursionError, json.JSONDecodeError):
        raise ValueError('Corrupt preference file; preserve or repair it before retrying') from None
    finally:
        os.close(file)


def read(slug, schema):
    with _directory(slug) as fd:
        return _load(fd, schema)


def _update(slug, schema, edit):
    with _directory(slug, True) as fd:
        lock = None
        temp = None
        try:
            lock = os.open('preferences.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
            _regular(lock)
            deadline = time.monotonic() + 3
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError('Preferences are busy; retry shortly')
                    time.sleep(0.01)
            prefs = _validate(edit(_load(fd, schema)), schema)
            raw = json.dumps(prefs, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
            if len(raw) > WRITE_BYTES:
                raise ValueError('Preference document exceeds the 128 KiB aggregate write limit')
            temp = '.preferences-' + secrets.token_hex(16)
            out = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(out, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, 'preferences.json', src_dir_fd=fd, dst_dir_fd=fd)
            temp = None
            os.fsync(fd)
            return prefs
        except OSError:
            raise ValueError('Cannot safely save preferences') from None
        finally:
            if temp is not None:
                os.unlink(temp, dir_fd=fd)
            if lock is not None:
                os.close(lock)


def change(slug, schema, patch):
    if not isinstance(patch, dict) or set(patch) - {'options', 'favorites', 'collections'}:
        raise ValueError('Invalid preference patch')
    patch = copy.deepcopy(patch)
    if 'options' in patch:
        _options(patch['options'], schema)
    def edit(prefs):
        for key, value in patch.items():
            if key == 'options':
                prefs['options'].update(value)
            else:
                prefs[key] = value
        return prefs
    return _update(slug, schema, edit)


def reset(slug, schema):
    return _update(slug, schema, lambda prefs: _defaults(schema))


def toggle(slug, schema, row_id):
    _text(row_id, 256, True)
    def edit(prefs):
        ids = prefs['favorites']
        ids.remove(row_id) if row_id in ids else ids.append(row_id)
        return prefs
    return _update(slug, schema, edit)


def put_collection(slug, schema, name, ids, *, expected_absent=False):
    """Replace one collection, or refuse an existing name under the same lock."""
    name = _text(name, 256, True)
    ids = _ids(ids, 512)
    def edit(prefs):
        if expected_absent and name in prefs['collections']:
            raise ValueError('Collection name already exists; remove it in saved collections first')
        prefs['collections'][name] = ids
        return prefs
    return _update(slug, schema, edit)


def remember(slug, schema, row_id):
    _text(row_id, 256, True)
    def edit(prefs):
        prefs['recent'] = ([row_id] + [value for value in prefs['recent'] if value != row_id])[:32]
        return prefs
    return _update(slug, schema, edit)
