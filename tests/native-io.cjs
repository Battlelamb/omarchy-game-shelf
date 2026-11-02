// SPDX-License-Identifier: GPL-3.0-only
// Run only through native-io.test.sh: no host sockets, network or real HOME.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const cp = require('node:child_process');
assert.equal(process.env.NATIVE_IO_SANDBOX, '1', 'use bash test.sh');
for (const name of ['DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'HYPRLAND_INSTANCE_SIGNATURE']) {
  assert.equal(process.env[name], undefined, 'no live session variable: ' + name);
}
assert.ok(['/home/test', '/tmp'].includes(process.env.HOME), 'fake HOME');
assert.equal(fs.existsSync('/run/user'), false, 'no host runtime sockets');
fs.mkdirSync('/tmp/runtime', {recursive:true, mode:0o700});
let helper = fs.readFileSync(require('./runtime-path.cjs')('BoundedProcess.qml'), 'utf8');
if (process.env.NATIVE_IO_MUTATION) {
  const mutation = process.env.NATIVE_IO_MUTATION;
  const replacements = {
    'unbounded-collector': ['/usr/bin/head -c "$limit"', '/usr/bin/cat'],
    'accept-stale-run': ['var accepted = current === run && !run.cancelled;', 'var accepted = true;'],
    'ignored-deadline': ['String(owner.deadlineSeconds),', '"2",'],
    'inherited-ignore-term': ['trap "while :; do /usr/bin/sleep 1; done" TERM PIPE;', 'trap "" TERM PIPE;'],
    'unprotected-supervisor': ['trap "while :; do /usr/bin/sleep 1; done" TERM PIPE;', 'trap : TERM PIPE;'],
    'release-cancel-ownership': ['run.signal(15);', 'current = null; run.running = false;'],
    'missing-independent-watchdog': ['"/usr/bin/timeout", "--kill-after=1", String(owner.deadlineSeconds), ', ''],
    'unprotected-closed-pipe': ['done" TERM PIPE;', 'done" TERM;']
  };
  const [before, after] = replacements[mutation] || [];
  assert.ok(before && helper.includes(before), 'known mutation must match source');
  helper = helper.replace(before, after);
}
let passed = 0;
function run(name, body, {missingTimeout = false, limit = 1024, childPidFile = ''} = {}) {
  if (process.env.NATIVE_IO_CASE && !name.includes(process.env.NATIVE_IO_CASE)) return;
  if (childPidFile) fs.rmSync(childPidFile, {force:true});
  if (childPidFile === '/tmp/native-grandchild.pid') fs.rmSync('/tmp/native-grandchild-work', {force:true});
  const dir = fs.mkdtempSync('/tmp/native-io-');
  fs.copyFileSync(require('./runtime-path.cjs')('Controller.js'), dir + '/Controller.js');
  assert.ok(helper.includes('StdioCollector { id: collected }'), 'collector observation must attach');
  fs.writeFileSync(dir + '/BoundedProcess.qml', (missingTimeout
    ? helper.replace('"/usr/bin/timeout"', '"/no-such-timeout"') : helper)
    .replace('StdioCollector { id: collected }', `StdioCollector { id: collected
      onDataChanged: {
        console.log("COLLECTOR bytes=" + data.byteLength);
        if (typeof data.byteLength !== "number" || data.byteLength > run.limit + 1) console.log("FAIL unbounded native collector");
      }
    }`));
  fs.writeFileSync(dir + '/shell.qml', `import QtQuick
import Quickshell
import "Controller.js" as Controller
ShellRoot {
  id: test
  property int completions: 0
  property double began: Date.now()
  function check(ok, message) { if (!ok) { console.log("FAIL " + message); Qt.exit(1); } }
  BoundedProcess { id: io; byteLimit: ${limit} }
  Timer { interval: 6000; running: true; onTriggered: { console.log("FAIL watchdog"); Qt.exit(1); } }
  ${body}
}`);
  const result = cp.spawnSync('/usr/bin/timeout', ['--kill-after=1', '9', '/usr/bin/qs', '-p', dir + '/shell.qml'],
    {encoding:'utf8', timeout:12000, env:process.env});
  const log = (result.stdout || '') + (result.stderr || '');
  console.log(`NATIVE ${name}\n${log}`);
  assert.equal(result.status, 0, name + ' native process exit');
  assert.match(log, /PASS native-case/, name + ' assertion receipt');
  assert.doesNotMatch(log, /FAIL |Error:|ReferenceError|TypeError/, name + ' no QML failure');
  if (childPidFile) {
    const pid = fs.readFileSync(childPidFile, 'utf8').trim();
    assert.match(pid, /^\d+$/);
    const path = '/proc/' + pid + '/stat';
    const state = fs.existsSync(path) ? fs.readFileSync(path, 'utf8').split(') ')[1][0] : 'gone';
    console.log('CHILD_OBSERVED pid=' + pid + ' state=' + state);
    assert.ok(state === 'gone' || state === 'Z', name + ' must not leave a running child');
    console.log('CHILD_TERMINATED pid=' + pid + ' state=' + state);
  }
  console.log('PASS ' + name); passed++;
}
function completion(command, checks, options) {
  return run(options.name, `Component.onCompleted: {
    io.completed.connect(function(code, status, text, error) {
      completions++; check(completions === 1, "exactly one completion"); ${checks}; settle.start();
    });
    io.command = ${JSON.stringify(command)}; io.start();
  }
  Timer { id: settle; interval: 100; onTriggered: { console.log("PASS native-case"); Qt.exit(0); } }`, options);
}
run('native catalogue preserves supplementary Unicode label boundaries', `
 Component.onCompleted: Qt.callLater(function() {
   var labels=["A".repeat(160),"A".repeat(159)+"😀","😀".repeat(160)];
   for(var i=0;i<labels.length;i++) {
     var rows=Controller.catalog(JSON.stringify({rows:[{id:"one",label:labels[i]}]})).rows;
     check(rows.length===1 && rows[0].label===labels[i],"native Unicode label admission");
   }
   check(Controller.catalog(JSON.stringify({rows:[{id:"too-long",label:"😀".repeat(161)}]})).rows.length===0,"native Unicode label bound");
   console.log("PASS native-case");Qt.exit(0);
 })
`);
run('cancel acknowledgment prevents delayed backend work', `
 Component.onCompleted: {
   io.completed.connect(function() { check(false, "cancelled run cannot complete"); });
   io.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import signal,time,pathlib
pathlib.Path('/tmp/native-signal-state').write_text(str(signal.getsignal(signal.SIGTERM)))
time.sleep(.7)
pathlib.Path('/tmp/native-delayed-work').write_text('acted')`])};
   io.start();
 }
 Timer { interval: 250; running: true; onTriggered: io.cancel() }
 Timer { interval: 1800; running: true; onTriggered: {
   check(!io.running, "cancel must eventually acknowledge drain"); console.log("PASS native-case"); Qt.exit(0);
 } }
`);
if (!process.env.NATIVE_IO_CASE || 'cancel acknowledgment prevents delayed backend work'.includes(process.env.NATIVE_IO_CASE)) {
  const disposition = fs.readFileSync('/tmp/native-signal-state', 'utf8');
  const acted = fs.existsSync('/tmp/native-delayed-work');
  console.log('BACKEND_SIGTERM=' + disposition + ' DELAYED_WORK=' + acted);
  assert.equal(acted, false, 'no delayed backend work after cancellation acknowledgment');
  assert.equal(disposition, '0', 'backend must inherit default SIGTERM, not supervisor protection');
}
const grandchild = `import os,pathlib,signal,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
pathlib.Path('/tmp/native-grandchild.pid').write_text(str(os.getpid()))
while True:
 with open('/tmp/native-grandchild-work','a') as f: f.write('tick\\n')
 time.sleep(.01)`;
// Observe both process identity and actual work before cancellation/teardown.
const readinessCommand = JSON.stringify(['/usr/bin/python3','-c',`import pathlib,time
pidfile=pathlib.Path(${JSON.stringify(process.env.NATIVE_IO_NEVER_READY ? '/tmp/never-ready' : '/tmp/native-grandchild.pid')})
work=pathlib.Path('/tmp/native-grandchild-work'); began=time.monotonic()
while time.monotonic()-began<1.2:
 if pidfile.exists() and work.exists() and work.stat().st_size>0:
  pid=pidfile.read_text().strip()
  if pid.isdigit() and (pathlib.Path('/proc')/pid/'stat').exists():
   print('ready:'+pid,end='');break
 time.sleep(.01)
else: raise SystemExit('fixture readiness deadline')`]);
run('cancel acknowledgment includes a TERM-ignoring grandchild', `
 property bool cancelled: false
 property bool verifying: false
 Component.onCompleted: {
   io.completed.connect(function(code,status,text,error) {
     check(verifying && code === 0 && text === "drained" && error === "", "grandchild stopped before acknowledgment");
     console.log("PASS native-case"); Qt.exit(0);
   });
   io.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import subprocess,time
time.sleep(.45)  # Deterministic cold-start scheduling control.
subprocess.Popen(['/usr/bin/python3','-c',${JSON.stringify(grandchild)}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(30)`])}; io.start();
 }
 BoundedProcess {
  id: ready; command: ${readinessCommand}
  onCompleted: (code,status,text,error) => {
   if(code!==0 || error!=="" || text.indexOf("ready:")!==0) {check(false,"fixture readiness deadline before cancellation");return;}
   console.log("READY grandchild "+text);io.cancel();cancelled=true;
  }
  Component.onCompleted: start()
 }
 Timer { interval: 25; running: true; repeat: true; onTriggered: {
   if (cancelled && !verifying && !io.running) {
     verifying = true;
     io.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import pathlib,time
pid=pathlib.Path('/tmp/native-grandchild.pid').read_text()
p=pathlib.Path('/proc')/pid/'stat'
assert not p.exists() or p.read_text().rpartition(') ')[2].split()[0]=='Z', 'grandchild alive after acknowledgment'
w=pathlib.Path('/tmp/native-grandchild-work'); before=w.read_bytes(); time.sleep(.4)
assert w.read_bytes()==before, 'post-acknowledgment descendant work'
print('drained',end='')`])}; io.start();
   }
 } }
`, {childPidFile:'/tmp/native-grandchild.pid'});
run('configured deadline permits a command beyond the default two seconds', `
 Component.onCompleted: { io.deadlineSeconds=4; io.completed.connect(function(code,status,text,error){ check(code===0 && text===\"extended\" && error===\"\", \"configured deadline honored\");console.log(\"PASS native-case\");Qt.exit(0); }); io.command=[\"/usr/bin/bash\",\"-c\",\"sleep 2.3; printf extended\"];io.start(); }
`);
completion(['/usr/bin/printf', 'ok\n'], 'check(code === 0 && status === 0 && text === "ok\\n" && error === "", "normal output/exit")', {name:'normal stdout and normal exit'});
completion(['/usr/bin/printf', '$(not-a-command); "literal"'], 'check(text === \'$(not-a-command); "literal"\' && error === "", "arguments remain literal")', {name:'shell metacharacters in arguments remain literal'});
completion(['/usr/bin/bash', '-c', 'printf rejected; exit 7'], 'check(code === 7 && status === 0 && text === "rejected" && error === "", "nonzero preserved")', {name:'nonzero exit remains failure-capable'});
completion(['/no-such-client-command'], 'check(code === 127 && status === 0, "missing wrapped executable denied")', {name:'missing wrapped executable cannot succeed'});
completion(['/usr/bin/bash', '-c', 'printf "\\303\\251\\360\\237\\230\\200"'], 'check(text === "é😀" && error === "", "UTF-8 round trip")', {name:'UTF-8 output is decoded after bounded collection'});
completion(['/usr/bin/head', '-c', '1024', '/dev/zero'], 'check(text.length === 1024 && error === "", "exact limit accepted")', {name:'exact ASCII byte boundary accepted'});
completion(['/usr/bin/head', '-c', '2097152', '/dev/zero'], 'check(error === "outputLimit" && text === "", "ASCII overflow rejected before publication")', {name:'large ASCII stream is capped'});
completion(['/usr/bin/bash', '-c', 'for ((i=0;i<600;i++)); do printf "\\303\\251"; done'], 'check(error === "outputLimit" && text === "", "UTF-8 bytes not UTF-16 units")', {name:'multibyte stream is capped by bytes'});
fs.writeFileSync('/tmp/utf8-limit', 'é'.repeat(1048576 / 2));
fs.writeFileSync('/tmp/utf8-overflow', 'é'.repeat(1048576 / 2 + 1));
completion(['/usr/bin/head', '-c', '1048576', '/dev/zero'], 'check(text.length === 1048576 && error === "", "production ASCII byte boundary")', {name:'production 1MiB ASCII limit accepted', limit:1048576});
completion(['/usr/bin/cat', '/tmp/utf8-limit'], 'check(text.length === 1048576 / 2 && error === "", "production UTF-8 byte boundary")', {name:'production 1MiB UTF-8 limit accepted', limit:1048576});
completion(['/usr/bin/cat', '/tmp/utf8-overflow'], 'check(error === "outputLimit" && text === "", "production UTF-8 overflow")', {name:'production 1MiB UTF-8 overflow rejected', limit:1048576});
completion(['/usr/bin/head', '-c', '2097152', '/dev/zero'], 'check(error === "outputLimit" && text === "", "production ASCII overflow")', {name:'production 1MiB ASCII overflow rejected', limit:1048576});
completion(['/usr/bin/bash', '-c', 'echo $$ > /tmp/native-hanging-child.pid; trap "" TERM; while :; do /usr/bin/sleep 1; done'], 'check(error === "" && (code === 124 || code === 137 || status !== 0), "timeout cannot succeed"); check(Date.now() - began < 4200, "hard deadline")', {name:'TERM-ignoring child has OS-enforced deadline', childPidFile:'/tmp/native-hanging-child.pid'});
completion(['/usr/bin/printf', 'never'], 'check(error === "startFailed" && code === -1 && text === "", "FailedToStart completion")', {name:'native FailedToStart without exited completes once', missingTimeout:true});
run('cancelled old run cannot complete a replacement run', `
  property bool cancelled: false
  property bool replacement: false
  Component.onCompleted: {
    io.completed.connect(function(code, status, text, error) {
      completions++; check(completions === 1 && text === "new" && error === "", "only new run completes");
    });
    io.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import fcntl,os,pathlib,signal,time
lock=open('/tmp/native-overlap.lock','w'); fcntl.flock(lock,fcntl.LOCK_EX)
pathlib.Path('/tmp/native-cancelled-child.pid').write_text(str(os.getpid()))
signal.signal(signal.SIGTERM,signal.SIG_IGN)
print('old',flush=True)
while True:
 with open('/tmp/native-drain-work','a') as work: work.write('tick\\n')
 time.sleep(.01)`])};
    io.start();
  }
  Timer { interval: 250; running: true; onTriggered: {
    var retiring = io.current; check(retiring !== null, "old backend still active");
    io.cancel(); io.cancel(); cancelled = true;
    check(io.running && io.current === retiring, "cancel retains physical ownership during drain");
    io.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import fcntl,pathlib,time
lock=open('/tmp/native-overlap.lock','w')
try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: print('overlap',end=''); raise SystemExit(1)
p=pathlib.Path('/tmp/native-drain-work'); before=p.read_bytes()
time.sleep(.4)
assert p.read_bytes()==before, 'post-acknowledgment work'
print('new',end='')`])};
    io.start(); check(io.current === retiring, "replacement refused until physical drain");
  } }
  Timer { interval: 500; running: true; onTriggered: {
    check(io.running && completions === 0 && !replacement, "TERM-ignoring child remains owned until KILL");
  } }
  Timer { interval: 25; running: true; repeat: true; onTriggered: {
    if (cancelled && !replacement && !io.running) { replacement = true; io.start(); }
  } }
  Timer { interval: 3600; running: true; onTriggered: {
    check(replacement && completions === 1 && !io.running, "retry after drain completes once without overlap");
    console.log("PASS native-case"); Qt.exit(0);
  } }
`, {childPidFile:'/tmp/native-cancelled-child.pid'});
run('immediate cancellation cannot notify a new request', `
  property bool replacement: false
  Component.onCompleted: {
    io.completed.connect(function(code, status, text, error) {
      completions++; check(text === "new" && error === "", "immediate cancellation ownership");
    });
    io.command = ["/usr/bin/printf", "old"]; io.start(); var retiring = io.current; io.cancel();
    io.command = ["/usr/bin/printf", "new"]; io.start();
    check(io.running && io.current === retiring, "immediate replacement refused before acknowledgment");
  }
  Timer { interval: 25; running: true; repeat: true; onTriggered: {
    if (!replacement && !io.running) { replacement = true; io.start(); }
  } }
  Timer { interval: 3500; running: true; onTriggered: {
    check(replacement && completions === 1 && !io.running, "exactly one native completion after retry"); console.log("PASS native-case"); Qt.exit(0);
  } }
`);
run('destroyed request owner cannot strand a command beyond its deadline', `
  property var retiringOwner: null
  Component {
    id: requestOwner
    Item {
      property alias request: owned
      BoundedProcess { id: owned }
    }
  }
  Component.onCompleted: {
    retiringOwner = requestOwner.createObject(io);
    retiringOwner.request.command = ["/usr/bin/bash", "-c", "echo $$ > /tmp/native-owner-destroyed.pid; trap '' TERM; while :; do /usr/bin/sleep 1; done"];
    retiringOwner.request.start();
  }
  Timer { interval: 250; running: true; onTriggered: { retiringOwner.destroy(); retiringOwner = null; } }
  Timer { interval: 4100; running: true; onTriggered: { console.log("PASS native-case"); Qt.exit(0); } }
`, {childPidFile:'/tmp/native-owner-destroyed.pid'});
run('owner teardown drains TERM-ignoring grandchild on independent deadline', `
 Loader { id: disappearing; sourceComponent: Component { BoundedProcess {} } }
 Component.onCompleted: {
   disappearing.item.command = ${JSON.stringify(['/usr/bin/python3', '-c', `import subprocess,time
time.sleep(.45)  # Deterministic cold-start scheduling control.
subprocess.Popen(['/usr/bin/python3','-c',${JSON.stringify(grandchild)}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(30)`])}; disappearing.item.start();
 }
 BoundedProcess {
  command: ${readinessCommand}
  onCompleted: (code,status,text,error) => {
   if(code!==0 || error!=="" || text.indexOf("ready:")!==0) {check(false,"fixture readiness deadline before teardown");return;}
   console.log("READY grandchild "+text);disappearing.active=false;
  }
  Component.onCompleted: start()
 }
 Timer { interval: 4100; running: true; onTriggered: { console.log("PASS native-case"); Qt.exit(0); } }
`, {childPidFile:'/tmp/native-grandchild.pid'});
// Record the real pipeline process group before cancellation; no host PIDs enter this fixture.
const unloadProducer = `import os,pathlib,json
members=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit(): continue
 try:
  fields=(p/'stat').read_text().rpartition(') ')[2].split()
  if int(fields[2])==os.getpgrp(): members.append({'pid':int(p.name),'comm':(p/'comm').read_text().strip()})
 except (FileNotFoundError,ProcessLookupError): pass
parent=int((pathlib.Path('/proc')/str(os.getpgrp())/'stat').read_text().rpartition(') ')[2].split()[1])
if parent not in [p['pid'] for p in members]: members.append({'pid':parent,'comm':(pathlib.Path('/proc')/str(parent)/'comm').read_text().strip()})
pathlib.Path('/tmp/native-unloaded-pipeline.json').write_text(json.dumps(members))
os.execl('/usr/bin/sleep','sleep','30')`;
run('cancel then Loader unload terminates the sampled command pipeline', `
  Loader { id: unloadable; sourceComponent: Component { BoundedProcess {} } }
  Component.onCompleted: {
    check(unloadable.item !== null, "loaded request owner");
    unloadable.item.command = ${JSON.stringify(['/usr/bin/python3', '-c', unloadProducer])};
    unloadable.item.start();
  }
  Timer { interval: 400; running: true; onTriggered: { unloadable.item.cancel(); unloadable.active = false; } }
  Timer { interval: 4500; running: true; onTriggered: { console.log("PASS native-case"); Qt.exit(0); } }
`);
if (!process.env.NATIVE_IO_CASE || 'cancel then Loader unload terminates the sampled command pipeline'.includes(process.env.NATIVE_IO_CASE)) {
const pipeline = JSON.parse(fs.readFileSync('/tmp/native-unloaded-pipeline.json', 'utf8'));
assert.ok(pipeline.length >= 4, 'sample the real command pipeline, not just its immediate supervisor');
for (const role of ['bash', 'head', 'timeout']) assert.ok(pipeline.some(p => p.comm === role), 'sampled pipeline contains ' + role);
for (const p of pipeline) {
  assert.ok(Number.isInteger(p.pid) && p.pid > 0);
  const stat = '/proc/' + p.pid + '/stat';
  const state = fs.existsSync(stat) ? fs.readFileSync(stat, 'utf8').split(') ')[1][0] : 'gone';
  assert.ok(state === 'gone' || state === 'Z', p.comm + ' must stop after cancel/unload');
  console.log('PIPELINE_TERMINATED pid=' + p.pid + ' comm=' + p.comm + ' state=' + state);
}
}
console.log(`RESULT ${passed} passed`);
