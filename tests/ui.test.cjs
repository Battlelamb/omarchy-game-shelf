const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm'), test=require('node:test'), assert=require('node:assert/strict');
const file=require('./runtime-path.cjs')(require('../manifest.json').entryPoints.overlay.split('/').pop());const src=fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';
function get(name){const start=src.indexOf('function '+name+'(');assert.ok(start>=0,'Missing actual UI function '+name);let body=src.indexOf('{',start),depth=1,i=body+1,quote='',escape=false;for(;i<src.length;i++){const c=src[i];if(quote){if(escape)escape=false;else if(c==='\\')escape=true;else if(c===quote)quote='';continue;}if(c==='"'||c==="'"){quote=c;continue;}if(c==='{')depth++;if(c==='}'&&!--depth)break;}return src.slice(start,i+1);}
function fixture(){let probes=0,loads=0,actions=0,cancels=0;const root={opened:false,opening:false,generation:0,query:'old',selected:0,rows:[],message:'',actions:[],actionBusy:false};const ctx=vm.createContext({root,lockProbe:{running:false,start(){probes++},cancel(){cancels++}},catalogue:{running:false,start(){loads++},cancel(){cancels++}},action:{command:[],start(){actions++},cancel(){cancels++}},Controller:{catalog:()=>({rows:[],actions:[],message:'ok'}),actionResult:()=>({ok:false,message:'failed'})},strings:{t:k=>k},Qt:{callLater:()=>{}},keyboard:{forceActiveFocus:()=>{}},backendPath:'/work/backend.py'});for(const n of ['open','attemptAdmission','close','admit','loadCatalogue','acceptCatalogue','activate','acceptAction','selectionIndependent','syncView','leaveConfigure'])vm.runInContext(get(n),ctx);for(const n of ['close','loadCatalogue','attemptAdmission','selectionIndependent','syncView','leaveConfigure'])root[n]=(...a)=>ctx[n](...a);root.dismiss=()=>ctx.close();return {ctx,root,counts:()=>({probes,loads,actions,cancels})};}
test('UI waits for unlocked admission before mapping or catalogue work',()=>{const f=fixture();f.ctx.open('{}');assert.equal(f.root.opened,false);assert.equal(f.root.opening,true);assert.equal(f.counts().loads,0);f.ctx.admit(1,0,'','');assert.equal(f.root.opened,true);assert.equal(f.counts().loads,1);});
test('opening waits for old process drain and retries admission without mapping early',()=>{for(const key of ['action','catalogue','lockProbe']){const f=fixture();f.ctx[key].running=true;f.ctx.open('{}');assert.equal(f.counts().probes,0,key);assert.equal(f.root.opened,false);assert.equal(f.root.opening,true);f.ctx[key].running=false;f.ctx.attemptAdmission();assert.equal(f.counts().probes,1);f.ctx.admit(1,0,'','');assert.equal(f.root.opened,true);f.ctx.close();f.ctx.attemptAdmission();assert.equal(f.counts().probes,1);}});
test('UI fails closed on bad lock and ignores stale admission after close',()=>{for(const [c,s,e] of [[0,0,''],[2,0,''],[1,1,''],[1,0,'startFailed']]){const f=fixture();f.ctx.open('{}');f.ctx.admit(c,s,'',e);assert.equal(f.root.opened,false);}const f=fixture();f.ctx.open('{}');f.ctx.close();f.ctx.admit(1,0,'','');assert.equal(f.root.opened,false);});
test('UI action requires explicit known verb and selected id',()=>{const f=fixture();f.root.opened=true;f.root.matches=[{id:'one'}];f.root.actions=['copy'];f.ctx.activate('apply');assert.equal(f.counts().actions,0);f.ctx.activate('copy');assert.equal(f.counts().actions,1);assert.deepEqual(Array.from(f.ctx.action.command),['/usr/bin/python3','/work/backend.py','action','--id','one','--verb','copy','--apply']);f.ctx.activate('copy');assert.equal(f.counts().actions,1);});
test('a draining action process blocks another action even after UI busy state clears',()=>{const f=fixture();f.root.opened=true;f.root.matches=[{id:'one'}];f.root.actions=['apply'];f.ctx.action.running=true;f.ctx.activate('apply');assert.equal(f.counts().actions,0);});
test('every action is blocked while a catalogue request is in flight',()=>{for(const verb of ['apply','restore','confirm']){const f=fixture();f.root.opened=true;f.root.matches=[{id:'one'}];f.root.actions=[verb];f.ctx.catalogue.running=true;f.ctx.activate(verb);assert.equal(f.counts().actions,0,verb);}});
test('receipt Restore does not depend on filtered selection and still respects all busy gates',()=>{
 for(const matches of [[],[{id:'different-source'}]]) {
  const f=fixture();f.root.opened=true;f.root.matches=matches;f.root.selected=-1;f.root.actions=['restore'];
  f.ctx.activate('restore');assert.equal(f.counts().actions,1);assert.equal(f.ctx.action.command[4],'restore:last');assert.equal(f.ctx.action.command[6],'restore');
 }
 for(const key of ['catalogue','lockProbe','action']) {
  const f=fixture();f.root.opened=true;f.root.matches=[];f.root.actions=['restore'];f.ctx[key].running=true;f.ctx.activate('restore');assert.equal(f.counts().actions,0,key);
 }
 const f=fixture();f.root.opened=true;f.root.matches=[];f.root.actions=['apply'];f.ctx.activate('restore');f.ctx.activate('apply');assert.equal(f.counts().actions,0);
 const line=src.split('\n').find(s=>s.includes('text: strings.t("restore")'));
 const enabled=line.match(/enabled: ([^;]+)/)[1];const ctx=vm.createContext({root:{actionBusy:false,selectedRow:null},catalogue:{running:false},action:{running:false},lockProbe:{running:false}});
 assert.equal(vm.runInContext(enabled,ctx),true);ctx.catalogue.running=true;assert.equal(vm.runInContext(enabled,ctx),false);
});
test('UI failed action retains query and close clears owned work',()=>{const f=fixture();f.root.opened=true;f.root.query='keep';f.root.actionGeneration=f.root.generation;f.root.actionBusy=true;f.ctx.acceptAction(1,0,'','');assert.equal(f.root.opened,true);assert.equal(f.root.query,'keep');f.ctx.close();assert.equal(f.root.opened,false);assert.equal(f.root.query,'');assert.ok(f.counts().cancels>=3);});
test('catalogue failure displays bounded backend feedback but no partial actionable rows',()=>{const f=fixture();f.root.opened=true;f.root.catalogueGeneration=f.root.generation;f.ctx.Controller.catalog=()=>({rows:[{id:'partial'}],actions:['apply'],message:'Install optional image decoder'});f.ctx.acceptCatalogue(2,0,'{}','');assert.match(f.root.message,/Install optional image decoder/);assert.equal(f.root.rows.length,0);assert.equal(f.root.actions.length,0);});
test('successful metadata-only actions update buttons without decoding the catalogue again',()=>{
 const api=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(path.dirname(file),'Controller.js'),'utf8'),api);
 const f=fixture();f.ctx.Controller=api;f.root.opened=true;f.root.query='keep';f.root.rows=[{id:'palette:one'}];f.root.actionGeneration=f.root.generation;f.root.actionBusy=true;f.root.actions=['export'];
 const text=JSON.stringify({ok:true,message:'Exported locally',actions:['export','restore']});f.ctx.acceptAction(0,0,text,'');
 assert.equal(f.counts().loads,0);assert.deepEqual(Array.from(f.root.actions),['export','restore']);assert.equal(f.root.query,'keep');assert.equal(f.root.rows[0].id,'palette:one');assert.equal(f.root.actionBusy,false);
 for(const hint of [['export','unknown'],['export','export'],[{}],'export',Array(7).fill('restore')]) {
  const out=api.actionResult(JSON.stringify({ok:true,actions:hint}),0,0,'');assert.equal(out.actions,undefined);
 }
 const failed=api.actionResult(JSON.stringify({ok:false,actions:['restore']}),1,0,'');assert.equal(failed.actions,undefined);
 const g=fixture();g.ctx.Controller=api;g.root.opened=true;g.root.actionGeneration=g.root.generation;g.ctx.acceptAction(0,0,'{"ok":true}','');assert.equal(g.counts().loads,1);
 const old=Array.from(f.root.actions);f.root.generation++;f.ctx.acceptAction(0,0,'{"ok":true,"actions":[]}','');assert.deepEqual(Array.from(f.root.actions),old);assert.equal(f.counts().loads,0);
});
test('wide preview has bounded non-growing width so the results grid keeps space',()=>{
 const start=src.indexOf('visible: !card.compact && root.selectedRow');assert.ok(start>=0);
 const pane=src.slice(start,src.indexOf('Rectangle {',start));assert.match(pane,/Layout.maximumWidth: Style.space\(320\)/);assert.match(pane,/Layout.minimumWidth: 0/);assert.match(pane,/Layout.fillWidth: false/);
});
test('compact layout does not request the hidden large preview and wide layout restores it',()=>{
 const line=src.split('\n').find(s=>s.includes('sourceSize.width: 640'));const expression=line.match(/source: ([^;]+)/)[1];
 const ctx=vm.createContext({root:{selectedRow:{preview:'/fixture/local.png'}},card:{compact:true},Controller:{imageUrl:p=>'file://'+p}});
 assert.equal(vm.runInContext(expression,ctx),'');ctx.card.compact=false;assert.equal(vm.runInContext(expression,ctx),'file:///fixture/local.png');
 ctx.root.selectedRow=null;assert.equal(vm.runInContext(expression,ctx),'');
});
test('UI source uses native styling plain text bounded previews and no hidden daemon',()=>{assert.match(src,/textFormat: Text.PlainText/);assert.match(src,/Commons.Color.menu.background/);assert.match(src,/sourceSize.width/);assert.match(src,/Controller.imageUrl/);assert.doesNotMatch(src,/execDetached|AutoText|http[s]?:\/\//);});
