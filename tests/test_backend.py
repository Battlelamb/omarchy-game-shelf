"""CLI tests: real adapters, synthetic local files, isolated executable shims."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1] / 'runtime/0.1.0/backend.py'

class BackendTests(unittest.TestCase):
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

    def cli(self, *args, rc=0):
        r = subprocess.run(['/usr/bin/python3',str(BACKEND),*args],cwd='/',env=self.env,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        self.assertEqual(r.returncode,rc,r.stderr.decode()+r.stdout.decode())
        self.assertTrue(r.stdout.strip(), 'backend must emit JSON')
        self.assertLessEqual(len(r.stdout),1048576)
        self.assertNotIn(b'Traceback',r.stdout+r.stderr)
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
            self.assertEqual(set(row)-{'id','label','detail','preview','color'},set())
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

    def test_independent_deadline_survives_backend_termination(self):
        import time
        self.steam()
        self.shim('steam',body='import signal\nchild=os.fork()\nif child == 0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n time.sleep(30)\n sys.exit(0)\n(Path(os.environ["HOME"])/"child.pid").write_text(str(child))\ntime.sleep(30)')
        proc=subprocess.Popen(['/usr/bin/python3',str(BACKEND),'action','--id','steam:42','--verb','launch','--apply'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pidfile=self.home/'child.pid'
        deadline=time.monotonic()+2
        while not pidfile.exists() and time.monotonic()<deadline:
            time.sleep(.02)
        self.assertTrue(pidfile.exists())
        pid=int(pidfile.read_text())
        proc.terminate();proc.wait(timeout=2)
        deadline=time.monotonic()+5
        def running():
            statfile=Path('/proc')/str(pid)/'stat'
            return statfile.exists() and statfile.read_text().split()[2] not in ('Z','X')
        while running() and time.monotonic()<deadline:
            time.sleep(.05)
        alive=running()
        if alive:
            os.kill(pid,9)
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

if __name__ == '__main__':
    unittest.main()
