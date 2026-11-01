#!/usr/bin/env python3
from pathlib import Path
import json
r=Path(__file__).resolve().parents[1]
m=json.loads((r/'manifest.json').read_text())
assert m['schemaVersion']==1 and m['version']=='0.1.0'
assert m['id'].startswith('leviathan.') and m['kinds']==['overlay']
assert m.get('keepLoaded') is True,'Keep helper ownership across native host hide/unload'
entry=m['entryPoints']['overlay']; assert entry.startswith('runtime/0.1.0/') and (r/entry).is_file()
assert len(m['description'])<=500
for f in ['runtime/0.1.0/backend.py','runtime/0.1.0/Controller.js','runtime/0.1.0/BoundedProcess.qml','runtime/0.1.0/i18n/en.json','README.md','LICENSE','NOTICE.md','NOTICE.backend.md','BACKEND.md','tests/test_backend.py','tests/controller.test.cjs','tests/ui.test.cjs','tests/runner.test.cjs']:
 assert (r/f).is_file(),f
for p in r.rglob('*'):
 if '.git' in p.parts or 'release-output' in p.parts:continue
 assert not p.is_symlink(),str(p)
s=json.loads((r/'runtime/0.1.0/i18n/en.json').read_text());assert s['title']==m['name']
assert not (r/Path(entry).name).exists(),'Duplicate flat entry point'
print('PASS package identity, versioned runtime, data/docs/tests, translations and no symlinks')
