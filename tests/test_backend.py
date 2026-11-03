"""CLI tests: real adapters, synthetic local files, isolated executable shims."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / Path(json.loads((ROOT / 'manifest.json').read_text())['entryPoints']['overlay']).parent / 'backend.py'

def child_running(statfile):
    try:
        stat = statfile.read_text()
    except FileNotFoundError:
        return False
    return stat.rpartition(') ')[2].split()[0] not in ('Z','X')

class BackendTests(unittest.TestCase):
    def test_legacy_large_preferences_preserve_confirmed_action_and_usable_reads(self):
        # Seed an old valid store directly: new writes have a smaller aggregate budget.
        self.steam(); self.shim('steam'); selected = 'steam:42'; verb = 'launch'
        prefs = self.cli('preferences')['preferences']
        prefs['collections'] = {'g'+str(g): [str(n).zfill(4)+'x'*252 for n in range(512)] for g in range(9)}
        base = Path(self.env.get('XDG_CONFIG_HOME', str(self.home/'.config')))
        store = base/'omarchy/lego/game-shelf/preferences.json'
        store.parent.mkdir(parents=True, exist_ok=True)
        store.parent.parent.chmod(0o700); store.parent.chmod(0o700)
        raw = json.dumps(prefs, ensure_ascii=False, separators=(',', ':')).encode()
        self.assertGreater(len(raw), 1048576)
        store.write_bytes(raw); store.chmod(0o600)
        result = subprocess.run(['/usr/bin/python3', str(BACKEND), 'action', '--id', selected, '--verb', verb, '--apply'], env=self.env, capture_output=True, timeout=12)
        value = json.loads(result.stdout)
        self.assertTrue(self.calls())
        self.assertEqual(result.returncode, 0, value)
        self.assertTrue(value['ok'], value)
        self.assertIn('warning', value['message'].lower())
        self.assertLessEqual(len(result.stdout), 1048576)
        self.assertNotIn('preferences', value)
        for command in ('preferences',):
            result = subprocess.run(['/usr/bin/python3', str(BACKEND), command], env=self.env, capture_output=True, timeout=12)
            value = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, value)
            self.assertNotIn('preferences', value)
            self.assertIn('warning', value['message'].lower())
            self.assertLessEqual(len(result.stdout), 1048576)
            if command == 'catalog': self.assertIn(selected, [row['id'] for row in value['rows']])
        reset = subprocess.run(['/usr/bin/python3', str(BACKEND), 'preferences', '--apply', '--payload', '{"reset":true}'], env=self.env, capture_output=True, timeout=8)
        self.assertEqual(reset.returncode, 0, reset.stdout)
        self.assertEqual(json.loads(reset.stdout)['preferences']['collections'], {})


    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        self.env = {'HOME':str(self.home), 'PATH':str(self.bin), 'LANG':'C.UTF-8',
                    'TMPDIR':str(self.home), 'PYTHONDONTWRITEBYTECODE':'1'}

    def put(self, rel, text):
        p = self.home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def shim(self, name, rc=0, body=''):
        p = self.bin / name
        p.write_text('#!/usr/bin/python3\nimport os,sys,json,time\nfrom pathlib import Path\n'
                     'p=Path(os.environ["HOME"])/"calls.jsonl"\n'
                     'with p.open("a") as f: f.write(json.dumps({"argv":sys.argv,"stdin":sys.stdin.read()})+"\\n")\n'
                     +body+'\nsys.exit('+str(rc)+')\n')
        p.chmod(0o755)

    def calls(self):
        p = self.home / 'calls.jsonl'
        return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []

    def cli(self, *args, rc=0, artwork_opens=None):
        command = ['/usr/bin/python3',str(BACKEND),*args]
        if artwork_opens is not None:
            command = ['/usr/bin/python3','-c',
                       'import json,os,runpy,sys\n'
                       'opened=[]\n'
                       'def audit(event,args):\n'
                       ' if event == "open" and isinstance(args[0],str) and args[0].endswith((".png",".jpg",".jpeg")): opened.append(args[0])\n'
                       'sys.addaudithook(audit)\n'
                       'sys.argv=sys.argv[1:]\n'
                       'try: runpy.run_path(sys.argv[0],run_name="__main__")\n'
                       'finally: print(json.dumps(len(opened)),file=sys.stderr)\n',str(BACKEND),*args]
        r = subprocess.run(command,cwd='/',env=self.env,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(r.returncode,rc,r.stderr.decode()+r.stdout.decode())
        self.assertTrue(r.stdout.strip(), 'backend must emit JSON')
        self.assertLessEqual(len(r.stdout),1048576)
        self.assertNotIn(b'Traceback',r.stdout+r.stderr)
        if artwork_opens is not None:
            artwork_opens.append(json.loads(r.stderr))
        return json.loads(r.stdout)

    def test_offline_box_is_private(self):
        self.assertEqual(os.environ['HOME'],'/home/test')
        for key in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','HYPRLAND_INSTANCE_SIGNATURE','PYTHONPATH'):
            self.assertNotIn(key,os.environ)
        self.assertEqual(sorted(p.name for p in Path('/home').iterdir()),['test'])
        self.assertFalse(Path('/srv').exists())
        self.assertFalse(Path('/run/user').exists())
        interfaces = Path('/proc/net/dev').read_text().splitlines()[2:]
        self.assertTrue(all(s.strip().startswith('lo:') for s in interfaces))
        with socket.socket() as sock:
            sock.settimeout(.2)
            self.assertNotEqual(sock.connect_ex(('192.0.2.1',443)),0)

    def test_catalog_contract(self):
        result = self.cli('catalog')
        self.assertIsInstance(result['rows'],list)
        self.assertIsInstance(result['message'],str)
        self.assertIn('actions',result)
        self.assertIn('actionLabel',result)
        seen = set()
        for row in result['rows']:
            self.assertEqual(set(row)-{'id','label','detail','preview','color','provider','installed','favorite','collection'},set())
            for key in ('id','label','detail'):
                self.assertIsInstance(row[key],str)
                self.assertTrue(row[key])
                self.assertLessEqual(len(row[key]),512)
            self.assertNotIn(row['id'],seen)
            seen.add(row['id'])
            if row.get('preview'):
                self.assertTrue(Path(row['preview']).is_absolute())
        self.assertEqual(self.calls(),[])

    def steam(self,appid='42',name='Sample Adventure',root=None,state='4',installed=True,body=None):
        root=root or self.home/'.local/share/Steam'
        path=root/'steamapps'/('appmanifest_'+appid+'.acf')
        path.parent.mkdir(parents=True,exist_ok=True)
        text='"AppState" { "appid" "'+appid+'" "name" "'+name+'" "StateFlags" "'+state+'" "installdir" "Game '+appid+'" }'
        path.write_text(body if body is not None else text)
        if installed:
            (path.parent/'common'/('Game '+appid)).mkdir(parents=True,exist_ok=True)
        return path

    def test_steam_catalog_uses_installed_vdf_and_stable_ids(self):
        self.steam()
        result=self.cli('catalog')
        self.assertEqual(len(result['rows']),1)
        row=result['rows'][0]
        self.assertEqual(row['id'],'steam:42')
        self.assertEqual(row['label'],'Sample Adventure')
        self.assertIn('Steam',row['detail'])
        self.assertIn('42',row['detail'])
        self.assertIn('Game 42',row['detail'])
        self.assertIn('unavailable',result['message'].lower())
        self.assertEqual(self.calls(),[])

    def test_steam_follows_only_registered_local_libraries_and_deduplicates(self):
        self.steam()
        extra=self.home/'external library'
        self.steam('43','Other Game',root=extra)
        self.steam('42','Duplicate',root=extra)
        self.put('.local/share/Steam/steamapps/libraryfolders.vdf','"libraryfolders" { "0" { "path" "'+str(extra)+'" } "1" "'+str(extra)+'" }')
        self.steam('99',root=self.home/'not-registered')
        rows=self.cli('catalog')['rows']
        self.assertEqual({r['id'] for r in rows},{'steam:42','steam:43'})
        self.assertEqual(len(rows),2)
        self.assertEqual(next(r['label'] for r in rows if r['id']=='steam:42'),'Sample Adventure')

    def test_steam_native_alias_and_flatpak_roots(self):
        self.steam('45',root=self.home/'.steam/steam')
        self.steam('46',root=self.home/'.var/app/com.valvesoftware.Steam/.local/share/Steam')
        self.assertEqual({r['id'] for r in self.cli('catalog')['rows']},{'steam:45','steam:46'})

    def test_steam_rejects_malformed_duplicate_injected_and_uninstalled_metadata(self):
        bad=[('1','"AppState" { "appid" "1" "appid" "2" "name" "Bad" }'),('2','"AppState" { "appid" "2" "name" "Bad"'),('3','"AppState" { "appid" "999" "name" "Bad" "StateFlags" "4" "installdir" "Game 3" }'),('4','"AppState" { "appid" "4" "name" "Bad" "StateFlags" "4" "installdir" "../../outside" }'),('5','"AppState" { "appid" "$(touch BAD)" "name" "Bad" }')]
        for ident,body in bad:
            self.steam(ident,body=body)
        self.steam('6',state='2')
        self.steam('7',installed=False)
        self.steam('8',body='"AppState" { "appid" "8" "name" "Good \\"quoted\\"" "StateFlags" "4" "installdir" "Game 8" } // trailing comment')
        rows=self.cli('catalog')['rows']
        self.assertEqual([r['id'] for r in rows],['steam:8'])
        self.assertEqual(rows[0]['label'],'Good "quoted"')
        self.assertEqual(self.calls(),[])

    def test_steam_oversize_depth_and_nonregular_inputs_are_skipped(self):
        self.steam('1',body='x'*600000)
        self.steam('2',body='"x" {'*40+'}'*40)
        p=self.steam('3');p.unlink();os.mkfifo(p)
        self.assertEqual(self.cli('catalog')['rows'],[])

    def lutris(self,rows=None,flatpak=False,schema=None):
        rel='.var/app/net.lutris.Lutris/data/lutris/pga.db' if flatpak else '.local/share/lutris/pga.db'
        p=self.home/rel;p.parent.mkdir(parents=True,exist_ok=True)
        from contextlib import closing
        with closing(sqlite3.connect(p)) as conn:
            conn.execute(schema or 'CREATE TABLE games (id INTEGER, name TEXT, slug TEXT, runner TEXT, installed INTEGER, directory TEXT)')
            if schema is None:
                conn.executemany('INSERT INTO games VALUES (?,?,?,?,?,?)', rows or [(7,'Sample Quest','sample-quest','wine',1,'/games/Sample Quest')])
            conn.commit()
        return p

    def test_lutris_reads_installed_rows_readonly_with_provider_identity(self):
        import hashlib
        db=self.lutris(rows=[(7,'Sample Quest','sample-quest','wine',1,'/games/Sample Quest'),(8,'Not Installed','not-installed','wine',0,''),(9,'Unsafe','../../bad','wine',1,'')])
        before=hashlib.sha256(db.read_bytes()).hexdigest()
        files=set(db.parent.iterdir())
        result=self.cli('catalog')
        self.assertEqual([r['id'] for r in result['rows']],['lutris:native:7'])
        row=result['rows'][0]
        self.assertEqual(row['label'],'Sample Quest')
        for detail in ['Lutris','wine','sample-quest','ID 7','Sample Quest']:
            self.assertIn(detail,row['detail'])
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),before)
        self.assertEqual(set(db.parent.iterdir()),files)
        self.assertEqual(self.calls(),[])

    def test_lutris_native_and_flatpak_id_collision_is_not_merged(self):
        self.lutris();self.lutris(flatpak=True)
        rows=self.cli('catalog')['rows']
        self.assertEqual({r['id'] for r in rows},{'lutris:native:7','lutris:flatpak:7'})

    def test_lutris_corrupt_unsupported_and_oversized_records_are_honest(self):
        p=self.lutris(schema='CREATE TABLE games (id INTEGER, name TEXT)')
        result=self.cli('catalog')
        self.assertEqual(result['rows'],[])
        self.assertIn('unsupported',result['message'].lower())
        p.write_bytes(b'not a sqlite database')
        result=self.cli('catalog')
        self.assertEqual(result['rows'],[])
        self.assertIn('unreadable',result['message'].lower())
        p.unlink()
        self.lutris(rows=[(1,'x'*70000,'huge','wine',1,''),(2,'Fine','fine','wine',1,'')])
        self.assertEqual([r['id'] for r in self.cli('catalog')['rows']],['lutris:native:2'])

    def test_steam_launch_uses_only_known_numeric_id(self):
        self.steam(name='Literal $(touch BAD)')
        self.shim('steam')
        result=self.cli('action','--id','steam:42','--verb','launch','--apply')
        self.assertTrue(result.get('ok',False))
        self.assertEqual(self.calls()[0]['argv'][1:],['steam://rungameid/42'])
        self.assertIn('accepted',result['message'].lower())
        self.assertIn('not confirmed',result['message'].lower())

    def test_lutris_launch_uses_numeric_database_id_not_mutable_slug(self):
        self.lutris();self.shim('lutris')
        result=self.cli('action','--id','lutris:native:7','--verb','launch','--apply')
        self.assertTrue(result.get('ok',False))
        self.assertEqual(self.calls()[0]['argv'][1:],['lutris:rungameid/7'])

    def test_flatpak_lutris_requires_installed_marker_and_preserves_provider(self):
        self.lutris(flatpak=True);self.shim('lutris');self.shim('flatpak')
        args=('action','--id','lutris:flatpak:7','--verb','launch','--apply')
        self.assertFalse(self.cli(*args,rc=1)['ok'])
        self.assertEqual(self.calls(),[])
        self.put('.local/share/flatpak/app/net.lutris.Lutris/current/active/metadata','[Application]\nname=net.lutris.Lutris\n')
        self.assertTrue(self.cli(*args)['ok'])
        self.assertEqual(self.calls()[0]['argv'][1:],['run','net.lutris.Lutris','lutris:rungameid/7'])

    def test_launch_revalidates_membership_apply_and_verb(self):
        p=self.steam();self.shim('steam')
        for args in [('action','--id','steam:42','--verb','launch'),('action','--id','steam:42;touch BAD','--verb','launch','--apply'),('action','--id','steam:042','--verb','launch','--apply'),('action','--id','steam:42','--verb','restore','--apply'),('catalog','--apply'),('invalid',)]:
            self.assertFalse(self.cli(*args,rc=1)['ok'])
        p.unlink()
        self.assertFalse(self.cli('action','--id','steam:42','--verb','launch','--apply',rc=1)['ok'])
        self.assertEqual(self.calls(),[])

    def test_missing_failed_and_timed_out_client_never_reports_success(self):
        self.steam()
        args=('action','--id','steam:42','--verb','launch','--apply')
        self.assertFalse(self.cli(*args,rc=1)['ok'])
        self.shim('steam',rc=8)
        self.assertFalse(self.cli(*args,rc=1)['ok'])
        self.shim('steam',body='time.sleep(30)')
        self.assertIn('timed out',self.cli(*args,rc=1)['message'])

    def test_local_steam_flat_hashed_and_lutris_covers(self):
        import base64
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l2kAAAAASUVORK5CYII=')
        self.steam();self.lutris()
        steam=self.home/'.local/share/Steam/appcache/librarycache/42_library_600x900.png'
        lutris=self.home/'.local/share/lutris/coverart/sample-quest.png'
        for p in [steam,lutris]:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(png)
        rows={r['id']:r for r in self.cli('catalog')['rows']}
        self.assertEqual(rows['steam:42'].get('preview'),str(steam))
        self.assertEqual(rows['lutris:native:7'].get('preview'),str(lutris))
        steam.unlink()
        hashed=steam.parent/'42'/'abcdef1234'/'library_capsule.png'
        hashed.parent.mkdir(parents=True);hashed.write_bytes(png)
        self.assertEqual(next(r for r in self.cli('catalog')['rows'] if r['id']=='steam:42').get('preview'),str(hashed))
        hashed.write_bytes(b'not an image')
        self.assertNotIn('preview',next(r for r in self.cli('catalog')['rows'] if r['id']=='steam:42'))
        self.assertEqual(self.calls(),[])

    def test_launch_membership_skips_artwork_but_keeps_fresh_provider_validation(self):
        import base64
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l2kAAAAASUVORK5CYII=')
        self.steam();missing=self.steam('43')
        native=self.lutris();self.lutris(flatpak=True)
        covers={'steam:42':self.home/'.local/share/Steam/appcache/librarycache/42_library_600x900.png',
                'lutris:native:7':native.parent/'coverart/sample-quest.png',
                'lutris:flatpak:7':self.home/'.var/app/net.lutris.Lutris/data/lutris/coverart/sample-quest.png'}
        for path in covers.values():
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(png)
        for name in ('steam','lutris','flatpak'):
            self.shim(name)
        marker=self.put('.local/share/flatpak/app/net.lutris.Lutris/current/active/metadata','[Application]\nname=net.lutris.Lutris\n')
        catalog_opens=[]
        rows={r['id']:r for r in self.cli('catalog',artwork_opens=catalog_opens)['rows']}
        self.assertEqual(set(rows),set(covers)|{'steam:43'})
        for ident,path in covers.items():
            self.assertEqual(rows[ident]['preview'],str(path))
        self.assertNotIn('preview',rows['steam:43'])
        self.assertGreater(catalog_opens[0],0)
        action_opens=[]
        expected={'steam:42':['steam','steam://rungameid/42'],
                  'steam:43':['steam','steam://rungameid/43'],
                  'lutris:native:7':['lutris','lutris:rungameid/7'],
                  'lutris:flatpak:7':['flatpak','run','net.lutris.Lutris','lutris:rungameid/7']}
        for ident in expected:
            self.assertTrue(self.cli('action','--id',ident,'--verb','launch','--apply',artwork_opens=action_opens)['ok'])
        self.assertEqual([[Path(c['argv'][0]).name,*c['argv'][1:]] for c in self.calls()],list(expected.values()))
        missing.write_text(missing.read_text().replace('"StateFlags" "4"','"StateFlags" "2"'))
        from contextlib import closing
        with closing(sqlite3.connect(native)) as conn:
            conn.execute('UPDATE games SET installed=0');conn.commit()
        marker.unlink()
        for ident in ('steam:43','lutris:native:7','lutris:flatpak:7','steam:042','lutris:other:7'):
            self.assertFalse(self.cli('action','--id',ident,'--verb','launch','--apply',rc=1,artwork_opens=action_opens)['ok'])
        self.assertEqual(len(self.calls()),len(expected))
        print('ARTWORK_EVIDENCE '+json.dumps({'catalog_opens':catalog_opens,'action_opens':action_opens}),flush=True)
        self.assertEqual(action_opens,[0]*9)

    def test_catalog_display_limit_keeps_full_game_membership(self):
        for n in range(1,1031):
            self.steam(str(n))
        result=self.cli('catalog')
        self.assertLessEqual(len(result['rows']),1024)
        self.assertIn('limited',result['message'].lower())
        hidden=next('steam:'+str(n) for n in range(1,1031) if 'steam:'+str(n) not in {r['id'] for r in result['rows']})
        self.shim('steam')
        self.assertTrue(self.cli('action','--id',hidden,'--verb','launch','--apply')['ok'])
        self.assertEqual(self.calls()[0]['argv'][1], 'steam://rungameid/'+hidden.split(':')[1])

    def test_child_running_vanished_stat_file(self):
        statfile = self.put('child.stat', '123 (worker) S 0')
        class VanishingStat:
            def exists(self):
                return statfile.exists()
            def read_text(self):
                statfile.unlink()
                return statfile.read_text()
        self.assertFalse(child_running(VanishingStat()))
        self.assertFalse(statfile.exists())

    def test_child_running_states_and_comm(self):
        statfile = self.home/'child.stat'
        self.assertFalse(child_running(statfile))
        for comm in ('worker', 'worker ) Z'):
            for state in ('R', 'S', 'D', 'T', 't', 'I', 'Z', 'X'):
                with self.subTest(comm=comm, state=state):
                    statfile.write_text(f'123 ({comm}) {state} 0')
                    self.assertEqual(child_running(statfile), state not in ('Z', 'X'))

    def test_child_running_read_errors_propagate(self):
        from unittest.mock import patch
        statfile = self.put('child.stat', '123 (worker) S 0')
        for error in (PermissionError, OSError):
            with self.subTest(error=error), patch.object(Path, 'read_text', side_effect=error):
                with self.assertRaises(error):
                    child_running(statfile)

    def test_independent_deadline_survives_backend_termination(self):
        import signal, time
        self.steam()
        self.shim('steam',body='import signal\nchild=os.fork()\nif child == 0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n time.sleep(30)\n sys.exit(0)\n(Path(os.environ["HOME"])/"child.pid").write_text(str(child))\ntime.sleep(30)')
        proc=subprocess.Popen(['/usr/bin/python3',str(BACKEND),'action','--id','steam:42','--verb','launch','--apply'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pidfile=self.home/'child.pid'
        def cleanup():
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=2)
            if pidfile.exists():
                try:
                    os.kill(int(pidfile.read_text()),signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.addCleanup(cleanup)
        deadline=time.monotonic()+2
        while not pidfile.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        self.assertTrue(pidfile.exists())
        pid=int(pidfile.read_text())
        proc.terminate();proc.wait(timeout=2)
        self.assertEqual(proc.returncode,-signal.SIGTERM)
        deadline=time.monotonic()+5
        statfile=Path('/proc')/str(pid)/'stat'
        while child_running(statfile) and time.monotonic()<deadline:
            time.sleep(.05)
        alive=child_running(statfile)
        self.assertFalse(alive,'helper outlived its deadline after backend termination')

    def test_flatpak_steam_fallback_is_reported_and_launches_fixed_appid(self):
        self.steam();self.shim('flatpak')
        self.put('.local/share/flatpak/app/com.valvesoftware.Steam/current/active/metadata','[Application]\nname=com.valvesoftware.Steam\n')
        result=self.cli('catalog')
        self.assertIn('Steam client available',result['message'])
        self.assertTrue(self.cli('action','--id','steam:42','--verb','launch','--apply')['ok'])
        self.assertEqual(self.calls()[0]['argv'][1:],['run','com.valvesoftware.Steam','steam://rungameid/42'])

    def test_utf8_output_budget_precedes_row_limit(self):
        self.lutris(rows=[(n,'界'*160,'game-'+str(n),'界'*64,1,'界'*160) for n in range(1,701)])
        result=self.cli('catalog')
        self.assertLess(len(result['rows']),700)
        self.assertLess(len(json.dumps(result,ensure_ascii=False).encode('utf-8')),810000)
        self.assertIn('limited',result['message'].lower())

    def test_open_folder_revalidates_registered_existing_steam_directory(self):
        self.steam();self.shim('xdg-open')
        result=self.cli('action','--id','steam:42','--verb','open-folder','--apply')
        self.assertTrue(result['ok'])
        folder=self.home/'.local/share/Steam/steamapps/common/Game 42'
        self.assertEqual(self.calls()[0]['argv'][1:],[str(folder)])
        self.assertIn('open-folder',self.cli('catalog')['actions'])
        folder.rmdir()
        self.assertFalse(self.cli('action','--id','steam:42','--verb','open-folder','--apply',rc=1)['ok'])
        self.assertEqual(len(self.calls()),1)

    def test_lutris_folder_accepts_only_exact_absolute_existing_directory(self):
        folder=self.home/'Games/Local Quest';folder.mkdir(parents=True)
        db=self.lutris(rows=[(7,'Quest','quest','wine',1,str(folder))])
        self.shim('xdg-open')
        args=('action','--id','lutris:native:7','--verb','open-folder','--apply')
        self.assertTrue(self.cli(*args)['ok'])
        self.assertEqual(self.calls()[0]['argv'][1:],[str(folder)])
        for value in ['relative', 'https://example.test', str(self.home/'absent'), '/']:
            from contextlib import closing
            with closing(sqlite3.connect(db)) as conn:
                conn.execute('UPDATE games SET directory=?',(value,));conn.commit()
            self.assertFalse(self.cli(*args,rc=1)['ok'])
        self.assertEqual(len(self.calls()),1)

    def test_preferences_read_is_nonmutating_and_catalog_exposes_schema(self):
        result=self.cli('preferences')
        self.assertTrue(result['ok'])
        self.assertEqual(result['preferences']['version'],1)
        self.assertEqual(result['preferences']['favorites'],[])
        self.assertIn('view',result['settingsSchema'])
        cat=self.cli('catalog')
        self.assertEqual(cat['preferences'],result['preferences'])
        self.assertEqual(cat['settingsSchema'],result['settingsSchema'])
        self.assertFalse((self.home/'.config').exists())

    def test_preferences_patch_is_explicit_bounded_exact_json_and_persistent(self):
        payload=json.dumps({'options':{'view':'favorites'},'collections':{'Work':['inert-id']}})
        for args in [('preferences','--payload',payload),('catalog','--payload',payload),('preferences','--id','')]:
            self.assertFalse(self.cli(*args,rc=1)['ok'])
        result=self.cli('preferences','--payload',payload,'--apply')
        self.assertEqual(result['preferences']['options']['view'],'favorites')
        self.assertEqual(result['preferences']['collections'],{'Work':['inert-id']})
        before=self.cli('preferences')['preferences']
        for raw in ['[]','null','{"options":{"view":"all","view":"recent"}}','{"options":{"view":NaN}}','{"recent":[]}','{"options":{"command":"sh"}}','{"options":{"view":"bad"}}',json.dumps({'options':{'x':'界'*6000}})]:
            self.assertFalse(self.cli('preferences','--payload',raw,'--apply',rc=1)['ok'])
            self.assertEqual(self.cli('preferences')['preferences'],before)
        self.assertEqual(self.calls(),[])

    def test_preferences_reset_only_exact_true_resets_saved_preferences(self):
        self.cli('preferences','--payload','{"options":{"view":"recent"},"favorites":["inert-id"]}','--apply')
        for raw in ['{"reset":1}','{"reset":false}','{"reset":true,"favorites":[]}']:
            self.assertFalse(self.cli('preferences','--payload',raw,'--apply',rc=1)['ok'])
        result=self.cli('preferences','--payload','{"reset":true}','--apply')
        self.assertEqual(result['preferences']['options']['view'],'all')
        self.assertEqual(result['preferences']['favorites'],[])
        self.assertEqual(self.cli('preferences')['preferences'],result['preferences'])

    def test_favorite_toggle_validates_membership_without_helper(self):
        self.steam();self.shim('steam')
        self.assertFalse(self.cli('action','--id','steam:42','--verb','favorite',rc=1)['ok'])
        self.assertFalse(self.cli('action','--id','unknown','--verb','favorite','--apply',rc=1)['ok'])
        result=self.cli('action','--id','steam:42','--verb','favorite','--apply')
        self.assertEqual(result['preferences']['favorites'],['steam:42'])
        self.assertTrue(self.cli('catalog')['rows'][0]['favorite'])
        self.assertEqual(self.cli('action','--id','steam:42','--verb','favorite','--apply')['preferences']['favorites'],[])
        self.assertEqual(self.calls(),[])

    def test_recent_records_only_accepted_launch_and_warns_on_storage_failure(self):
        self.steam()
        args=('action','--id','steam:42','--verb','launch','--apply')
        self.shim('steam',rc=4)
        self.cli(*args,rc=1)
        self.assertEqual(self.cli('preferences')['preferences']['recent'],[])
        self.shim('steam')
        result=self.cli(*args)
        self.assertIn('preferences',result)
        self.assertEqual(result['preferences']['recent'],['steam:42'])
        pref=self.home/'.config/omarchy/lego/game-shelf/preferences.json'
        pref.write_text('broken')
        result=self.cli(*args)
        self.assertTrue(result['ok'])
        self.assertIn('warning',result['message'].lower())
        self.assertEqual(pref.read_text(),'broken')

    def test_saved_collections_favorites_and_recent_filter_without_authorizing_ids(self):
        self.steam();self.steam('43')
        self.cli('preferences','--payload','{"favorites":["steam:42","absent"],"collections":{"Evening":["steam:42","absent"]},"options":{"view":"favorites"}}','--apply')
        self.assertEqual([r['id'] for r in self.cli('catalog')['rows']],['steam:42'])
        self.cli('preferences','--payload','{"options":{"view":"all","collection":"Evening"}}','--apply')
        self.assertEqual([r['id'] for r in self.cli('catalog')['rows']],['steam:42'])
        self.shim('steam');self.cli('action','--id','steam:43','--verb','launch','--apply')
        self.cli('preferences','--payload','{"options":{"view":"recent","collection":""}}','--apply')
        self.assertEqual([r['id'] for r in self.cli('catalog')['rows']],['steam:43'])
        self.assertFalse(self.cli('action','--id','absent','--verb','launch','--apply',rc=1)['ok'])

    def test_provider_filter_preserves_native_flatpak_identity_and_full_membership(self):
        self.steam();self.lutris();self.lutris(flatpak=True)
        expected={'steam':'steam:42','lutris-native':'lutris:native:7','lutris-flatpak':'lutris:flatpak:7'}
        for provider,ident in expected.items():
            self.cli('preferences','--payload',json.dumps({'options':{'provider':provider}}),'--apply')
            rows=self.cli('catalog')['rows']
            self.assertEqual([r['id'] for r in rows],[ident])
            self.assertEqual(rows[0]['provider'],provider)
            self.assertIs(rows[0]['installed'],True)
        self.shim('steam')
        self.assertTrue(self.cli('action','--id','steam:42','--verb','launch','--apply')['ok'])

    def test_installed_filters_include_only_valid_local_metadata_never_install_or_launch_missing(self):
        self.steam();self.steam('43',state='2');self.steam('44',installed=False)
        self.lutris(rows=[(7,'Installed','installed','wine',1,''),(8,'Not installed','not-installed','wine',0,'')])
        self.assertEqual({r['id'] for r in self.cli('catalog')['rows']},{'steam:42','lutris:native:7'})
        self.cli('preferences','--payload','{"options":{"installed":"all"}}','--apply')
        rows={r['id']:r for r in self.cli('catalog')['rows']}
        self.assertEqual(set(rows),{'steam:42','steam:43','steam:44','lutris:native:7','lutris:native:8'})
        for ident in ['steam:43','steam:44','lutris:native:8']:
            self.assertIs(rows[ident]['installed'],False)
        self.cli('preferences','--payload','{"options":{"installed":"not-installed"}}','--apply')
        self.assertEqual({r['id'] for r in self.cli('catalog')['rows']},{'steam:43','steam:44','lutris:native:8'})
        self.shim('steam');self.shim('lutris')
        for ident in ['steam:43','steam:44','lutris:native:8']:
            self.assertFalse(self.cli('action','--id',ident,'--verb','launch','--apply',rc=1)['ok'])
            self.assertTrue(self.cli('action','--id',ident,'--verb','favorite','--apply')['ok'])
        self.assertEqual(self.calls(),[])

    def test_lutris_folder_resolved_root_is_not_a_game_directory(self):
        folder=self.home/'root-alias';folder.symlink_to('/',target_is_directory=True)
        self.lutris(rows=[(7,'Quest','quest','wine',1,str(folder))]);self.shim('xdg-open')
        self.assertFalse(self.cli('action','--id','lutris:native:7','--verb','open-folder','--apply',rc=1)['ok'])
        self.assertEqual(self.calls(),[])

    def test_all_shipped_python_sources_compile(self):
        sources=sorted(p for p in ROOT.rglob('*.py') if 'release-output' not in p.parts)
        for source in sources:
            compile(source.read_bytes(),str(source),'exec')
        self.assertGreaterEqual(len(sources),4)

    def test_docs_reference_current_cli_and_only_existing_local_links(self):
        import re
        for name in ('README.md','BACKEND.md','NOTICE.backend.md'):
            text=(ROOT/name).read_text()
            self.assertNotRegex(text,r'/home/(?!user/)[^\s`]+')
            self.assertNotRegex(text,r'/srv/[^\s`]+')
            self.assertNotIn('runtime/0.2.1/',text)
            for target in re.findall(r'\]\(([^)]+)\)',text):
                if not target.startswith(('https://','http://','#')):
                    self.assertTrue((ROOT/target.split('#')[0]).is_file(),target)

    def test_common_display_schema_saves_exact_choices_and_resets_defaults(self):
        expected = {'density': ('comfortable', ['comfortable', 'compact']),
                    'layout': ('grid', ['grid', 'list']),
                    'sortOrder': ('default', ['default', 'name', 'favorites-first'])}
        result = self.cli('preferences')
        for key, (default, choices) in expected.items():
            self.assertIn(key, result['settingsSchema'])
            self.assertEqual(result['settingsSchema'][key]['type'], 'enum')
            self.assertEqual(result['settingsSchema'][key]['default'], default)
            self.assertEqual(result['settingsSchema'][key]['choices'], choices)
            self.assertEqual(result['preferences']['options'][key], default)
        self.assertFalse((self.home/'.config').exists())
        chosen = {'density':'compact', 'layout':'list', 'sortOrder':'favorites-first'}
        result = self.cli('preferences', '--apply', '--payload', json.dumps({'options':chosen}))
        for key, value in chosen.items():
            self.assertEqual(result['preferences']['options'][key], value)
        before = self.cli('preferences')['preferences']
        self.assertEqual(before, result['preferences'])
        for key in expected:
            for value in ['../../invalid', '', True, 1, None, [], {}]:
                with self.subTest(key=key, value=value):
                    self.assertFalse(self.cli('preferences', '--apply', '--payload',
                        json.dumps({'options':{key:value}}), rc=1)['ok'])
                    self.assertEqual(self.cli('preferences')['preferences'], before)
        self.cli('preferences', '--apply', '--payload', '{"options":{"sortOrder":"name"}}')
        result = self.cli('preferences', '--apply', '--payload', '{"reset":true}')
        for key, (default, _) in expected.items():
            self.assertEqual(result['preferences']['options'][key], default)
        self.assertEqual(self.calls(), [])

    def test_saved_hide_compatibility_tools_is_a_bounded_name_filter(self):
        names = ['Proton 9.0', 'GE-Proton9-20', 'Steam Linux Runtime 3.0 (sniper)',
                 'Steamworks Common Redistributables', 'Protonaut', 'The Proton Adventure',
                 'Runtime Quest', 'My Proton Tools']
        for n, name in enumerate(names, 1):
            self.steam(str(n), name)
        self.lutris(rows=[(7,'Proton Experimental','proton-test','wine',1,''),
                          (8,'Regular Quest','regular','wine',1,'')])
        self.assertIs(self.cli('preferences')['preferences']['options'].get('hideCompatibilityTools'), False)
        self.assertEqual(len(self.cli('catalog')['rows']), 10)
        result = self.cli('preferences', '--apply', '--payload', '{"options":{"hideCompatibilityTools":true}}')
        self.assertIs(result['preferences']['options']['hideCompatibilityTools'], True)
        self.assertEqual([r['label'] for r in self.cli('catalog')['rows']], names[4:]+['Regular Quest'])
        self.assertEqual(self.calls(), [])
        self.shim('steam')
        self.assertTrue(self.cli('action', '--id', 'steam:1', '--verb', 'launch', '--apply')['ok'])
        self.assertEqual(self.calls()[0]['argv'][1:], ['steam://rungameid/1'])
        self.cli('preferences', '--apply', '--payload', '{"reset":true}')
        self.assertIs(self.cli('preferences')['preferences']['options']['hideCompatibilityTools'], False)
        self.assertEqual(len(self.cli('catalog')['rows']), 10)

    def test_display_defaults_upgrade_old_options_without_rewriting_store(self):
        self.cli('preferences', '--apply', '--payload', '{"options":{"view":"favorites"},"favorites":["inert-id"]}')
        store = next((self.home/'.config/omarchy/lego').glob('*/preferences.json'))
        legacy = json.loads(store.read_bytes())
        for key in ('density', 'layout', 'sortOrder', 'hideCompatibilityTools'):
            legacy['options'].pop(key)
        store.write_text(json.dumps(legacy))
        original = store.read_bytes()
        result = self.cli('preferences')['preferences']
        self.assertEqual(result['favorites'], ['inert-id'])
        self.assertEqual(result['options']['view'], 'favorites')
        self.assertEqual({key:result['options'][key] for key in ('density','layout','sortOrder')},
                         {'density':'comfortable', 'layout':'grid', 'sortOrder':'default'})
        self.assertIs(result['options']['hideCompatibilityTools'], False)
        self.assertEqual(store.read_bytes(), original)
        self.assertEqual(self.calls(), [])

    def test_compatibility_filter_precedes_display_cap_and_composes_saved_filters(self):
        for n in range(1,1026):
            self.steam(str(n), 'Proton 9.0')
        self.steam('90000', 'Last Quest')
        self.lutris(rows=[(7,'Other Quest','other','wine',1,'')])
        self.cli('preferences','--apply','--payload','{"options":{"hideCompatibilityTools":true}}')
        self.assertEqual([r['id'] for r in self.cli('catalog')['rows']], ['steam:90000','lutris:native:7'])
        self.steam('90001','Partial Quest',state='2')
        patch = {'options':{'provider':'steam', 'installed':'not-installed', 'view':'favorites', 'collection':'Evening'},
                 'favorites':['steam:1','steam:90000','steam:90001','lutris:native:7'],
                 'collections':{'Evening':['steam:1','steam:90001','lutris:native:7']}}
        self.cli('preferences','--apply','--payload',json.dumps(patch))
        rows = self.cli('catalog')['rows']
        self.assertEqual([r['id'] for r in rows], ['steam:90001'])
        self.assertTrue(rows[0]['favorite'])
        self.assertEqual(rows[0]['collection'], 'Evening')
        self.assertIs(rows[0]['installed'], False)
        self.assertEqual(self.calls(), [])

    def test_compatibility_setting_rejects_non_boolean_without_replacing_preferences(self):
        self.cli('preferences','--apply','--payload','{"options":{"hideCompatibilityTools":true}}')
        store = self.home/'.config/omarchy/lego/game-shelf/preferences.json'
        original = store.read_bytes()
        for value in [0, 1, 'true', 'false', None, [], {}]:
            self.assertFalse(self.cli('preferences','--apply','--payload',
                json.dumps({'options':{'hideCompatibilityTools':value}}), rc=1)['ok'])
            self.assertEqual(store.read_bytes(), original)
        self.assertEqual(self.calls(), [])

    def test_current_feature_docs_match_versioned_backend_contract(self):
        for name in ('README.md', 'BACKEND.md'):
            text = (ROOT/name).read_text()
            self.assertIn('v0.4.1', text)
            for key in ('density', 'layout', 'sortOrder', 'hideCompatibilityTools'):
                self.assertIn(key, text)
        reference = (ROOT/'BACKEND.md').read_text()
        self.assertIn('runtime/0.4.1/backend.py', reference)
        self.assertNotIn('runtime/0.3.0/backend.py', reference)

if __name__ == '__main__':
    unittest.main()
