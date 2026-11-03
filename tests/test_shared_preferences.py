"""Run explicitly in the offline shared harness, never backend discovery."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from shared_paths import PREFERENCES as MODULE
SCHEMA = {'style': {'type': 'enum', 'default': 'muted', 'choices': ['muted', 'vibrant'], 'label': 'Style'}}

class PreferencesContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'shared preference helper is implemented')
        spec = importlib.util.spec_from_file_location('preferences', MODULE)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['XDG_CONFIG_HOME'] = self.tmp.name

    def test_targeted_collection_capture_preserves_other_names_under_lock(self):
        self.assertTrue(callable(getattr(self.p, 'put_collection', None)), 'locked targeted collection API exists')
        self.p.change('safe', {}, {'collections': {'Keep': ['old']}})
        children=[]
        for i in range(12):
            pid=os.fork()
            if pid==0:
                try:
                    self.p.put_collection('safe', {}, 'Capture '+str(i), [str(i)])
                except Exception:
                    os._exit(1)
                os._exit(0)
            children.append(pid)
        for pid in children:
            self.assertEqual(os.waitpid(pid,0)[1],0)
        expected={'Keep':['old'], **{'Capture '+str(i):[str(i)] for i in range(12)}}
        self.assertEqual(self.p.read('safe', {})['collections'], expected)

    def test_expected_absent_collection_is_checked_inside_locked_edit(self):
        from unittest.mock import patch
        self.p.change('safe', {}, {'favorites':['keep'], 'collections':{'Other':['old']}})
        original = self.p._update
        target = Path(self.tmp.name)/'omarchy/lego/safe/preferences.json'
        acknowledged = []
        def concurrent_save(slug, schema, edit):
            def save(prefs):
                prefs['collections']['Same'] = ['acknowledged']
                return prefs
            original(slug, schema, save)
            acknowledged.append(target.read_bytes())
            return original(slug, schema, edit)
        with patch.object(self.p, '_update', concurrent_save):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                self.p.put_collection('safe', {}, 'Same', ['stale'], expected_absent=True)
        self.assertEqual(len(acknowledged), 1)
        self.assertEqual(target.read_bytes(), acknowledged[0])
        prefs = self.p.put_collection('safe', {}, 'New', ['new'], expected_absent=True)
        self.assertEqual(prefs['collections'], {'Other':['old'], 'Same':['acknowledged'], 'New':['new']})
        prefs = self.p.put_collection('safe', {}, 'Same', ['replacement'])
        self.assertEqual(prefs['collections']['Same'], ['replacement'])
        self.assertEqual(prefs['favorites'], ['keep'])
        before = target.read_bytes()
        for name, ids in [('', []), ('Bad', ['duplicate']*2)]:
            with self.assertRaises(ValueError):
                self.p.put_collection('safe', {}, name, ids, expected_absent=True)
            self.assertEqual(target.read_bytes(), before)

    def test_reply_omits_only_optional_snapshot_without_falsifying_confirmed_action(self):
        self.assertTrue(callable(getattr(self.p, 'encode_reply', None)), 'bounded reply API exists')
        import json
        self.p.change('legacy', {}, {})
        target=Path(self.tmp.name)/'omarchy/lego/legacy/preferences.json'
        prefs=self.p.read('legacy', {})
        prefs['collections']={str(i):[str(j)+'😀'*250 for j in range(400)] for i in range(3)}
        raw=json.dumps(prefs,ensure_ascii=False,separators=(',', ':')).encode()
        self.assertGreater(len(raw),1200000)
        target.write_bytes(raw)  # Supported old-form store; not a new overbudget write.
        legacy=self.p.read('legacy', {})
        source={'ok':True,'message':'Copied','preferences':legacy}
        encoded=self.p.encode_reply(source)
        result=json.loads(encoded)
        self.assertLess(len(encoded.encode()),1048576)
        self.assertIs(result['ok'],True)
        self.assertIn('Copied',result['message'])
        self.assertIn('warning',result['message'].lower())
        self.assertNotIn('preferences',result)
        self.assertIn('preferences',source)
        self.assertEqual(target.read_bytes(),raw)
        with self.assertRaises(ValueError):
            self.p.encode_reply({'rows':[], 'preferences':legacy})
        with self.assertRaises(ValueError):
            self.p.encode_reply({'ok':True,'message':'Done','detail':'界'*1048576})
        self.assertEqual(self.p.reset('legacy', {})['collections'],{})

    def test_new_write_aggregate_budget_rejects_without_mutating_bytes(self):
        self.p.change('safe', {}, {'favorites':['old']})
        target=Path(self.tmp.name)/'omarchy/lego/safe/preferences.json'
        before=target.read_bytes()
        # Every field is individually valid; the supported aggregate is smaller.
        groups={'Work':[str(i)+'😀'*250 for i in range(140)]}
        with self.assertRaisesRegex(ValueError, '128 KiB'):
            self.p.change('safe', {}, {'collections':groups})
        self.assertEqual(target.read_bytes(),before)
        ids=[('desktop-'+str(i)+'x'*165+'.desktop') for i in range(400)]
        result=self.p.change('safe', {}, {'favorites':ids})
        self.assertEqual(len(result['favorites']),400)
        result=self.p.change('safe', {}, {'collections':{'Work':['界'*100+str(i) for i in range(100)]}})
        self.assertGreater(target.stat().st_size,104000)
        self.assertLess(target.stat().st_size,131072)
        self.assertEqual(self.p.read('safe', {}),result)

    def test_unicode_codepoint_boundaries_match_native_and_node(self):
        for value in ['😀'*129, '😀'*256, 'A'*255+'😀']:
            prefs=self.p.change('unicode', {}, {'collections':{value:[value]}})
            self.assertEqual(prefs['collections'][value],[value])
        for value in ['😀'*257, 'A'*256+'😀', '\ud800', '\udc00', 'a\u0085', 'a\n']:
            with self.assertRaises(ValueError):
                self.p.change('unicode', {}, {'collections':{value:[]}})

    def test_legacy_confirmed_clipboard_action_through_real_cli_keeps_status(self):
        import json
        import subprocess
        from shared_paths import ROOT
        package=ROOT if (ROOT/'manifest.json').is_file() else ROOT/'candidates/omarchy-glyph-picker'
        runtime=(package/json.loads((package/'manifest.json').read_text())['entryPoints']['overlay']).parent
        if (ROOT/'manifest.json').is_file() and json.loads((ROOT/'manifest.json').read_text())['id']!='battlelamb.glyph-picker':
            self.skipTest('glyph real-CLI integration belongs to Glyph Picker only')
        backend=runtime/'backend.py'
        def call(*args,env=None):
            run=subprocess.run(['/usr/bin/python3',str(backend),*args],capture_output=True,env=env,timeout=10)
            self.assertLess(len(run.stdout),1048576)
            return run,json.loads(run.stdout)
        _,metadata=call('preferences')
        schema=metadata['settingsSchema']
        run,catalog=call('catalog')
        self.assertEqual(run.returncode,0)
        row=catalog['rows'][0]
        self.p.change('glyph-picker',schema,{})
        target=Path(self.tmp.name)/'omarchy/lego/glyph-picker/preferences.json'
        prefs=self.p.read('glyph-picker',schema)
        prefs['collections']={str(i):[str(j)+'😀'*250 for j in range(400)] for i in range(3)}
        raw=json.dumps(prefs,ensure_ascii=False,separators=(',', ':')).encode()
        self.assertGreater(len(raw),1200000)
        target.write_bytes(raw)
        self.assertEqual(self.p.read('glyph-picker',schema),prefs)
        shim=Path(self.tmp.name)/'bin';shim.mkdir()
        marker=Path(self.tmp.name)/'clipboard-accepted.json'
        helper=shim/'wl-copy'
        helper.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text(json.dumps(sys.argv[1:]))\n')
        helper.chmod(0o700)
        env=dict(os.environ,PATH=str(shim)+':/usr/bin')
        run,result=call('action','--id',row['id'],'--verb','copy','--apply',env=env)
        self.assertEqual(run.returncode,0)
        self.assertIs(result['ok'],True)
        self.assertIn('accepted',result['message'])
        self.assertIn('warning',result['message'].lower())
        self.assertEqual(json.loads(marker.read_text())[-1],row['glyph'])
        if Path('/evidence').is_dir():
            import hashlib
            Path('/evidence/legacy-preferences.json').write_bytes(raw)
            receipt={'fixture_bytes':len(raw),'fixture_sha256':hashlib.sha256(raw).hexdigest(),'validated_legacy_read':True,'action_exit':run.returncode,'action_reply':result,'action_stdout_bytes':len(run.stdout),'clipboard_helper_argv':json.loads(marker.read_text()),'before_reset_store_unchanged':target.read_bytes()==raw}
            Path('/evidence/legacy-confirmed-action.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
        self.assertEqual(target.read_bytes(),raw)
        run,result=call('catalog')
        self.assertEqual(run.returncode,1)
        self.assertIs(result['ok'],False)
        self.assertEqual(target.read_bytes(),raw)
        run,result=call('preferences','--payload','{"reset":true}','--apply')
        self.assertEqual(run.returncode,0)
        self.assertEqual(result['preferences']['collections'],{})
        self.assertLess(target.stat().st_size,131072)

    def test_defaults_read_without_creating_storage(self):
        self.assertEqual(self.p.read('glyph-picker', SCHEMA), {'version': 1, 'favorites': [], 'recent': [], 'collections': {}, 'options': {'style': 'muted'}})
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_atomic_change_toggle_remember_reset_and_private_modes(self):
        for name in ['change', 'toggle', 'remember', 'reset']:
            self.assertTrue(callable(getattr(self.p, name, None)), name + ' is implemented')
        result = self.p.change('glyph-picker', SCHEMA, {'options': {'style': 'vibrant'}, 'favorites': ['one'], 'collections': {'Work': ['one']}})
        self.assertEqual(result['options']['style'], 'vibrant')
        self.assertEqual(self.p.toggle('glyph-picker', SCHEMA, 'two')['favorites'], ['one', 'two'])
        self.assertEqual(self.p.toggle('glyph-picker', SCHEMA, 'one')['favorites'], ['two'])
        for value in ['one', 'two', 'one']:
            result = self.p.remember('glyph-picker', SCHEMA, value)
        self.assertEqual(result['recent'], ['one', 'two'])
        target = Path(self.tmp.name) / 'omarchy/lego/glyph-picker/preferences.json'
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.p.read('glyph-picker', SCHEMA), result)
        self.assertEqual(self.p.reset('glyph-picker', SCHEMA)['options'], {'style': 'muted'})

    def test_untrusted_patch_is_rejected_without_touching_existing_bytes(self):
        self.p.change('glyph-picker', SCHEMA, {'favorites': ['safe']})
        target = Path(self.tmp.name) / 'omarchy/lego/glyph-picker/preferences.json'
        before = target.read_bytes()
        for patch in [{'recent': []}, {'version': 2}, {'options': {'unknown': True}}, {'options': {'style': 'bad'}}, {'favorites': ['a\n']}, {'favorites': ['x'] * 513}, {'collections': {'': ['x']}}, {'options': []}]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    self.p.change('glyph-picker', SCHEMA, patch)
                self.assertEqual(target.read_bytes(), before)

    def test_corrupt_and_symlink_files_never_overwritten_even_by_reset(self):
        self.p.change('glyph-picker', SCHEMA, {})
        target = Path(self.tmp.name) / 'omarchy/lego/glyph-picker/preferences.json'
        for raw in [b'{bad', b'{"version":1,"version":1}', b'x' * 1048577]:
            target.write_bytes(raw)
            for call in [self.p.read, self.p.reset]:
                with self.assertRaises(ValueError):
                    call('glyph-picker', SCHEMA)
                self.assertEqual(target.read_bytes(), raw)
        target.unlink()
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('untouched')
        target.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.p.reset('glyph-picker', SCHEMA)
        self.assertEqual(outside.read_text(), 'untouched')

    def test_all_option_types_and_bounds(self):
        schema = {
            'n': {'type': 'integer', 'default': 2, 'minimum': 1, 'maximum': 9},
            'b': {'type': 'boolean', 'default': False},
            's': {'type': 'string', 'default': '', 'maxLength': 4},
            'list': {'type': 'string-list', 'default': []}}
        changed = self.p.change('all-types', schema, {'options': {'n': 9, 'b': True, 's': '界🙂', 'list': ['/home/test/Pictures']}})
        self.assertEqual(changed['options']['s'], '界🙂')
        for key, values in {'n': [True, 0, 10, 1.2, float('nan')], 'b': [0, 'true'], 's': ['12345', 'bad\n', '\ud800'], 'list': [['x'] * 33, ['界' * 1366], [True]]}.items():
            for value in values:
                with self.assertRaises(ValueError):
                    self.p.change('all-types', schema, {'options': {key: value}})
        changed['options']['list'].append('external mutation')
        self.assertEqual(len(self.p.read('all-types', schema)['options']['list']), 1)

    def test_relative_xdg_falls_back_to_home_and_slug_cannot_escape(self):
        os.environ['HOME'] = self.tmp.name
        os.environ['XDG_CONFIG_HOME'] = 'relative'
        self.p.change('safe-slug', {}, {})
        self.assertTrue((Path(self.tmp.name) / '.config/omarchy/lego/safe-slug/preferences.json').is_file())
        for slug in ['../outside', '/absolute', 'bad/name', '', 'x' * 81]:
            with self.assertRaises(ValueError):
                self.p.read(slug, {})

    def test_directory_symlink_fifo_and_hardlink_are_rejected(self):
        base=Path(self.tmp.name)
        (base/'omarchy').symlink_to(base/'outside')
        with self.assertRaises(ValueError):
            self.p.change('safe', {}, {})
        (base/'omarchy').unlink()
        self.p.change('safe', {}, {})
        target=base/'omarchy/lego/safe/preferences.json'
        target.unlink()
        os.mkfifo(target, 0o600)
        with self.assertRaises(ValueError):
            self.p.read('safe', {})
        target.unlink()
        other=base/'other';other.write_text('{}');other.chmod(0o600)
        os.link(other,target)
        with self.assertRaises(ValueError):
            self.p.reset('safe', {})
        self.assertEqual(other.read_text(), '{}')

    def test_concurrent_locked_toggles_preserve_every_update(self):
        children=[]
        for i in range(12):
            pid=os.fork()
            if pid==0:
                try:
                    self.p.toggle('concurrent', {}, str(i))
                except Exception:
                    os._exit(1)
                os._exit(0)
            children.append(pid)
        for pid in children:
            self.assertEqual(os.waitpid(pid,0)[1],0)
        self.assertEqual(set(self.p.read('concurrent', {})['favorites']), {str(i) for i in range(12)})

    def test_reset_preserves_journals_and_custom_presets(self):
        self.p.change('safe', {}, {'favorites':['one']})
        directory=Path(self.tmp.name)/'omarchy/lego/safe'
        for name in ['custom-presets.json','recovery-journal.json']:
            (directory/name).write_text('keep me')
        self.p.reset('safe', {})
        for name in ['custom-presets.json','recovery-journal.json']:
            self.assertEqual((directory/name).read_text(), 'keep me')

    def test_existing_shared_omarchy_directory_is_not_chmodded_or_rejected(self):
        shared=Path(self.tmp.name)/'omarchy'
        shared.mkdir(mode=0o755)
        shared.chmod(0o755)
        self.assertEqual(self.p.read('safe', {})['favorites'], [])
        self.assertEqual(list(shared.iterdir()), [])
        self.p.change('safe', {}, {})
        self.assertEqual(shared.stat().st_mode & 0o777, 0o755)
        self.assertEqual((shared/'lego/safe').stat().st_mode & 0o777, 0o700)

if __name__ == '__main__':
    unittest.main(verbosity=2)
