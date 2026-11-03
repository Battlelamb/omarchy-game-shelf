#!/usr/bin/env python3
from pathlib import Path
import json
r=Path(__file__).resolve().parents[1]
m=json.loads((r/'manifest.json').read_text())
assert m['schemaVersion']==1 and m['version']=='0.4.1','Stale release version'
assert m['id'].startswith('battlelamb.') and m['author']=='Battlelamb' and m['kinds']==['overlay']
assert m.get('keepLoaded') is True,'Keep helper ownership across native host hide/unload'
runtime=Path('runtime')/m['version'];entry=Path(m['entryPoints']['overlay'])
assert entry.parent==runtime and entry.suffix=='.qml' and (r/entry).is_file(),'Entry must be a direct sibling of its versioned runtime'
assert sorted(p.name for p in (r/'runtime').iterdir())==[m['version']],'Stale or duplicate runtime'
assert len(m['description'])<=500
for f in [runtime/'backend.py',runtime/'preferences.py',runtime/'Settings.qml',runtime/'Controller.js',runtime/'BoundedProcess.qml',runtime/'i18n/en.json','README.md','LICENSE','NOTICE.md','NOTICE.backend.md','BACKEND.md','tests/test_backend.py','tests/controller.test.cjs','tests/ui.test.cjs','tests/runner.test.cjs','tests/test_shared_preferences.py','tests/preferences-ui.test.cjs','tests/display-preferences.test.cjs','tests/shared_paths.py','tests/shared-paths.cjs','tests/panel-functions.cjs','tests/native-settings.py','tests/native-panels.py','tests/shared-packaging.py']:
 assert (r/f).is_file(),f
for p in r.rglob('*'):
 if '.git' in p.parts or 'release-output' in p.parts:continue
 assert not p.is_symlink(),str(p)
s=json.loads((r/runtime/'i18n/en.json').read_text());assert s['title']==m['name']
for p in (r/runtime).iterdir():
 assert not (r/p.name).exists(),'Duplicate flat runtime: '+p.name
print('PASS package identity, versioned runtime, data/docs/tests, translations and no symlinks')
