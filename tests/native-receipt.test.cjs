const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'native-io.cjs'),'utf8');
test('native child liveness receipts cannot reuse an earlier case PID',()=>{
 const pid='/tmp/stale-fixture.pid',files=new Map([[pid,'123']]);
 const fakeFs={mkdtempSync:()=>'/fixture',copyFileSync:(from,to)=>{assert.equal(from,'/runtime/Controller.js');assert.equal(to,'/fixture/Controller.js');},writeFileSync:()=>{},existsSync:p=>files.has(p),rmSync:p=>files.delete(p),readFileSync:p=>{if(!files.has(p)){const e=new Error('fresh PID missing');e.code='ENOENT';throw e;}return files.get(p);}};
 const context=vm.createContext({assert,fs:fakeFs,require:name=>{assert.equal(name,'./runtime-path.cjs');return file=>'/runtime/'+file;},cp:{spawnSync:()=>({status:0,stdout:'PASS native-case',stderr:''})},helper:'StdioCollector { id: collected }',console:{log:()=>{}},process:{env:{}},passed:0});
 const begin=source.indexOf('function run('),end=source.indexOf('function completion(');
 assert.ok(begin>=0&&end>begin);vm.runInContext(source.slice(begin,end),context);
 assert.throws(()=>context.run('failed child startup','',{childPidFile:pid}),e=>e.code==='ENOENT');
});
