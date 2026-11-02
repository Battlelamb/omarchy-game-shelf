"""Standalone required-file guard negative controls; offline runner only."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from shared_paths import ROOT

def check(directory):
    return subprocess.run(['/usr/bin/python3',str(directory/'scripts/check-package.py')],capture_output=True,text=True)

roots=[ROOT] if (ROOT/'manifest.json').is_file() else sorted((ROOT/'candidates').glob('omarchy-*'))
for root in roots:
    runtime=Path(json.loads((root/'manifest.json').read_text())['entryPoints']['overlay']).parent
    required=[runtime/'preferences.py',runtime/'Settings.qml', *[Path('tests')/name for name in ['test_shared_preferences.py','preferences-ui.test.cjs','display-preferences.test.cjs','shared_paths.py','shared-paths.cjs','panel-functions.cjs','native-settings.py','native-panels.py','shared-packaging.py']]]
    if json.loads((root/'manifest.json').read_text())['id']=='leviathan.shader-deck':
        required += [runtime/'data/comparisons/grayscale-ramp'/(name+'.png') for name in ['cool','dim','grayscale','sepia','softcontrast','warm']]
    for name in required:
        assert (root/name).is_file(),f'{root.name}: missing standalone {name}'
    with tempfile.TemporaryDirectory() as tmp:
        copied=Path(tmp)/'package'
        shutil.copytree(root,copied,ignore=shutil.ignore_patterns('.git','release-output','__pycache__'))
        baseline=check(copied)
        assert baseline.returncode==0,baseline.stdout+baseline.stderr
        for name in required:
            target=copied/name
            raw=target.read_bytes()
            target.unlink()
            run=check(copied)
            assert run.returncode!=0,f'guard accepts missing {name}'
            assert str(name) in run.stderr,run.stderr
            target.write_bytes(raw)
    print(f'PASS standalone packaging {root.name}: {len(required)} missing-file negative controls')
