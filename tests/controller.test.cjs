const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = path.join(__dirname, '../runtime/0.1.0/Controller.js');
const api = vm.createContext({});
vm.runInContext(fs.existsSync(file) ? fs.readFileSync(file,'utf8').replace(/^\.pragma library\s*/, '') : '', api);
const plain = x => JSON.parse(JSON.stringify(x));
test('selection clamps both reading directions and row steps at every edge',()=>{
 assert.equal(typeof api.step,'function');
 assert.equal(api.step(0,-1,4),0);assert.equal(api.step(3,1,4),3);
 assert.equal(api.step(2,-3,4),0);assert.equal(api.step(1,3,4),3);
 assert.equal(api.step(1,-1,4),0);assert.equal(api.step(0,1,4),1);
 assert.equal(api.step(0,1,0),0);
});
test('catalog admits bounded explicit rows and no implicit actions', () => {
 assert.equal(typeof api.catalog,'function');
 const a = api.catalog(JSON.stringify({rows:[{id:'one',label:'One',detail:'Example',glyph:'\uea60',color:'#112233'}]}));
 assert.equal(a.rows[0].id,'one');assert.deepEqual(plain(a.actions),[]);
});
test('catalog rejects malformed, oversized and non-string metadata', () => {
 assert.equal(api.catalog('bad').rows.length,0);
 assert.equal(api.catalog('界'.repeat(349526)).rows.length,0);
 const a=api.catalog(JSON.stringify({rows:[{id:[],label:'bad'},{id:'x',label:['bad']},{id:'ok',label:'<img src=https://bad>'}],actions:['apply','bad','restore']}));
 assert.equal(a.rows.length,1);assert.equal(a.rows[0].label,'<img src=https://bad>');assert.deepEqual(plain(a.actions),['apply','restore']);
});
test('filter matches every word without reparsing and caps after filtering', () => {
 assert.equal(typeof api.filter,'function');
 const rows=Array.from({length:300},(_,i)=>({id:String(i),label:i===299?'Target APP':'Other',detail:'notes'}));
 assert.equal(api.filter(rows,'APP target')[0].id,'299');assert.equal(api.filter(rows,'').length,256);assert.equal(api.filter(rows,'missing').length,0);
});
test('file image source is local and URI escaped', () => {
 assert.equal(typeof api.imageUrl,'function');
 assert.equal(api.imageUrl('https://bad/a.png'),'');assert.equal(api.imageUrl('/tmp/x#?.png'),'file:///tmp/x%23%3F.png');assert.equal(api.imageUrl('/tmp/x\n.png'),'');
});
test('failed backend actions retain bounded actionable feedback without becoming success',()=>{
 const r=api.actionResult('{"ok":false,"message":"Install the optional clipboard tool"}',2,0,'');
 assert.equal(r.ok,false);assert.match(r.message,/Install the optional clipboard tool/);
 assert.equal(api.actionResult('{"ok":true,"message":"looks successful"}',2,0,'').ok,false);
});
test('action success requires strict true and normal successful process', () => {
 assert.equal(typeof api.actionResult,'function');
 assert.equal(api.actionResult('{"ok":true}',0,0,'').ok,true);
 for(const [raw,code,status,error] of [['{"ok":"true"}',0,0,''],['{"ok":true}',1,0,''],['{"ok":true}',0,1,''],['{"ok":true}',0,0,'timeout'],['bad',0,0,'']]) assert.equal(api.actionResult(raw,code,status,error).ok,false);
});
