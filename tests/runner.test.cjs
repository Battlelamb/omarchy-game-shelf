const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path'),cp=require('node:child_process');
const runner=path.join(__dirname, '../scripts/run-tests.py');
test('offline runner ignores ambient Node auto-install shims',()=>{
 assert.equal(process.env.HOME,'/home/test','run only through the offline runner');
 const probe=String.raw`
import json,os,runpy,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
assert os.environ['HOME']=='/home/test'
runner=Path(sys.argv[1]);calls=[]
with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
    bin=Path(tmp)/'bin';bin.mkdir();shim=bin/'node'
    shim.write_text('#!/bin/sh\nexit 99\n');shim.chmod(0o755)
    def capture(command,*args,**kwargs):
        calls.append(command);return SimpleNamespace(returncode=0)
    with patch.dict(os.environ,{'PATH':str(bin),'TMPDIR':tmp}),patch.object(sys,'argv',[str(runner)]),patch.object(subprocess,'run',capture):
        try:runpy.run_path(str(runner),run_name='__main__')
        except SystemExit as result:assert result.code==0
    assert len(calls)==1
    command=calls[0];index=command.index('/tools/node')
    print(json.dumps({'bound_node':command[index-1],'shim':str(shim),'subprocess_calls':len(calls)}))
`;
 const result=cp.spawnSync('/usr/bin/python3',['-c',probe,runner],{encoding:'utf8',timeout:10000});
 assert.equal(result.status,0,result.stdout+result.stderr);const data=JSON.parse(result.stdout);
 assert.equal(data.bound_node,'/usr/bin/node');assert.notEqual(data.bound_node,data.shim);assert.equal(data.subprocess_calls,1);
});
