#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Offline test runner. No user HOME, environment, network or live IPC crosses in."""
import os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if sys.argv[1:] not in ([],['--backend-only']):raise SystemExit('Usage: run-tests.py [--backend-only]')
backend_only=bool(sys.argv[1:]);scratch=os.environ.get('TMPDIR')
if not scratch or not Path(scratch).is_dir():raise SystemExit('TMPDIR must name an existing approved scratch directory')
node='/usr/bin/node' if os.access('/usr/bin/node',os.X_OK) else None
if not backend_only and not node:raise SystemExit('System /usr/bin/node is required for component/native process tests; PATH shims are not used')
with tempfile.TemporaryDirectory(prefix='omarchy-plugin-test-',dir=scratch) as temporary:
 tmp=Path(temporary);stock=tmp/'stock';stock.mkdir()
 deny=tmp/'deny';deny.write_text('#!/usr/bin/python3\nimport sys\nsys.stderr.write("Production setter masked in offline tests\\n")\nsys.exit(126)\n');deny.chmod(0o755)
 cmd=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--clearenv','--ro-bind','/usr','/usr','--ro-bind','/etc','/etc','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--tmpfs','/run','--tmpfs','/home','--dir','/home/test','--ro-bind',str(root),'/work','--ro-bind',str(stock),'/usr/share/omarchy/themes','--chdir','/work']
 targets={Path(directory,name).resolve() for directory in ['/usr/bin','/usr/share/omarchy/bin'] for name in ['omarchy-theme-set','omarchy-theme-bg-set','omarchy-shell'] if Path(directory,name).exists()}
 for target in sorted(targets):cmd+=['--ro-bind',str(deny),str(target)]
 if node:cmd+=['--dir','/tools','--ro-bind',node,'/tools/node']
 for key,value in {'HOME':'/home/test','PATH':'/tools:/usr/bin','TMPDIR':'/tmp','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}.items():cmd+=['--setenv',key,value]
 if backend_only:cmd+=['--','/usr/bin/python3','-m','unittest','discover','-s','tests','-p','test_*.py','-v']
 else:
  for key,value in {'NATIVE_IO_SANDBOX':'1','QT_QPA_PLATFORM':'offscreen','QSG_RHI_BACKEND':'software','XDG_RUNTIME_DIR':'/tmp/runtime'}.items():cmd+=['--setenv',key,value]
  cmd+=['--','/bin/bash','-c','node --test --test-reporter=tap tests/*.test.cjs && /usr/bin/python3 -m unittest discover -s tests -p "test_*.py" -v && /usr/bin/python3 scripts/check-package.py && node tests/native-io.cjs && /usr/bin/python3 tests/shared-packaging.py && /usr/bin/python3 tests/native-settings.py && /usr/bin/python3 tests/native-panels.py']
 result=subprocess.run(cmd)
 raise SystemExit(result.returncode)
