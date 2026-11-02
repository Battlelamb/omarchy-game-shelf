const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = require('./runtime-path.cjs')('Controller.js');
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
test('labels use 160 Unicode code points while retaining byte and control limits',()=>{
 for(const label of ['A'.repeat(160), 'A'.repeat(159)+'🙂', '🙂'.repeat(160), '𐐀'.repeat(160)]) {
  const out=api.catalog(JSON.stringify({rows:[{id:'one',label}]}));assert.equal(out.rows.length,1,String(label.length));assert.equal(out.rows[0].label,label);
 }
 for(const label of ['A'.repeat(161), '🙂'.repeat(161), 'A\u0001', [], null]) assert.equal(api.catalog(JSON.stringify({rows:[{id:'one',label}]})).rows.length,0);
 assert.equal(api.catalog('界'.repeat(349526)).rows.length,0);
});
test('broad searches stop after 256 matches but late and absent matches stay correct',()=>{
 let reads=0;const rows=Array.from({length:10757},(_,i)=>({id:String(i),get label(){reads++;return i===10756?'Rare late target':'Linux glyph';},detail:''}));
 assert.equal(api.filter(rows,'linux').length,256);assert.equal(reads,256);
 reads=0;assert.equal(api.filter(rows,'   ').length,256);assert.equal(reads,0);
 reads=0;assert.equal(api.filter(rows,'rare target')[0].id,'10756');assert.equal(reads,10757);
 assert.equal(api.filter(rows,'no such item').length,0);assert.equal(api.filter(rows,'x'.repeat(129)).length,0);
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
test('controller catalogue results contain only the three fields consumed by the UI',()=>{
 for(const raw of ['bad', JSON.stringify({rows:[],message:'Ready',actions:['copy'],actionLabel:'Unused backend label'})]) {
  assert.deepEqual(Object.keys(api.catalog(raw)).sort(),['actions','message','rows']);
 }
});
test('valid multibyte JSON is rejected by UTF-8 bytes rather than string length',()=>{
 const payload=n=>JSON.stringify({rows:[{id:'one',label:'Visible'}],actions:['copy'],message:'界'.repeat(n)});
 const oversized=payload(349526);assert.ok(oversized.length<1048576);assert.ok(Buffer.byteLength(oversized,'utf8')>1048576);
 assert.equal(api.catalog(oversized).rows.length,0);assert.equal(api.catalog(payload(100000)).rows.length,1);
});
test('seeded schema and search oracle covers 20000 bounded adversarial cases',()=>{
 let seed=0x6d2b79f5;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed;};
 const valid=(s,max)=>typeof s==='string'&&s.length<=max&&!/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(s);
 const values=['ok','constructor','__proto__','A'.repeat(160),'A'.repeat(161),'🙂'.repeat(160),'🙂'.repeat(161),'界'.repeat(161),'bad\u0001',null,[],{},42,true,''];
 const points=s=>{let n=0;for(const c of s)n++;return n;};
 for(let i=0;i<20000;i++) {
  const id=values[random()%values.length],label=values[random()%values.length];const data={rows:[{id,label,detail:'safe'}]};const raw=JSON.stringify(data);
  const good=valid(id,256)&&!!id&&typeof label==='string'&&valid(label,320)&&!!label&&points(label)<=160;
  assert.equal(api.catalog(raw).rows.length,good?1:0,'schema seed case '+i);
  if(i%20===0) {
   const rows=Array.from({length:random()%40},(_,j)=>({id:String(j),label:['App Alpha','Linux β','🙂 Game'][random()%3],detail:['Utility','Installed','Other'][random()%3]}));
   const q=['','ALPHA app','linux β','game installed','absent','   ','x'.repeat(129)][random()%7];
   const words=q.trim().toLowerCase().split(/\s+/).filter(Boolean);
   const expected=q.length>128?[]:rows.filter(r=>words.every(w=>(r.label+' '+r.detail).toLowerCase().includes(w))).slice(0,256).map(r=>r.id);
   assert.deepEqual(Array.from(api.filter(rows,q),r=>r.id),expected,'search seed case '+i);
  }
 }
});
test('action success requires strict true and normal successful process', () => {
 assert.equal(typeof api.actionResult,'function');
 assert.equal(api.actionResult('{"ok":true}',0,0,'').ok,true);
 for(const [raw,code,status,error] of [['{"ok":"true"}',0,0,''],['{"ok":true}',1,0,''],['{"ok":true}',0,1,''],['{"ok":true}',0,0,'timeout'],['bad',0,0,'']]) assert.equal(api.actionResult(raw,code,status,error).ok,false);
});
