const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'),vm=require('node:vm');
const path=require('node:path'),paths=require('./shared-paths.cjs');
const api=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(paths.runtime,'Controller.js'),'utf8'),api);
test('shuffle selection and comparison results retain only validated inert UI metadata',()=>{
 const result=api.actionResult(JSON.stringify({ok:true,selectedId:'wall:two',preview:'/tmp/reference.png',detail:'CPU reference only'}),0,0,'');
 assert.equal(result.selectedId,'wall:two');assert.equal(result.preview,'/tmp/reference.png');
 const bad=api.actionResult(JSON.stringify({ok:true,selectedId:['bad'],preview:'https://remote/image'}),0,0,'');
 assert.equal(bad.selectedId,undefined);assert.equal(bad.preview,undefined);
});
const plain=x=>JSON.parse(JSON.stringify(x));
const getFunction=require('./panel-functions.cjs');
function panelContext(names,root,extra={}) {
 const src=fs.readFileSync(paths.panel,'utf8');
 const ctx=vm.createContext({root,Controller:api,...extra});
 names.forEach(n=>vm.runInContext(getFunction(src,n),ctx));return ctx;
}
test('acknowledged defaults and Reset replace stale views, reopening restores collection',()=>{
 const root={opened:true,generation:1,catalogueGeneration:1,view:'favorites'};
 let ctx=panelContext(['acceptCatalogue'],root,{strings:{t:()=>''}});
 const prefs={version:1,favorites:['a'],recent:['b'],collections:{Work:['b']},options:{view:'all',collection:''}};
 root.syncView=()=>ctx.syncView && ctx.syncView();
 // Use the actual catalogue callback; not a separately reconstructed state update.
 const src=fs.readFileSync(paths.panel,'utf8');
 if(src.includes('function syncView(')) vm.runInContext(getFunction(src,'syncView'),ctx);
 ctx.acceptCatalogue(0,0,JSON.stringify({rows:[{id:'b',label:'B'}],actions:[],preferences:prefs}), '');
 assert.equal(root.view,'all','Reset must not intersect old favorites');
 prefs.options.view='recent';ctx.acceptCatalogue(0,0,JSON.stringify({rows:[{id:'b',label:'B'}],preferences:prefs}), '');
 assert.equal(root.view,'recent');
 prefs.options.view='all';prefs.options.collection='Work';root.view='all';
 ctx.acceptCatalogue(0,0,JSON.stringify({rows:[{id:'b',label:'B'}],preferences:prefs}), '');
 assert.equal(root.view,'collection:Work');
 assert.equal(api.viewRows(root.rows,'',root.preferences,root.view,'','','').length,1);
});
test('Back and Escape share refresh and catalogue focus restoration',()=>{
 const src=fs.readFileSync(paths.panel,'utf8');
 assert.match(src,/if\(root.configuring\) root.leaveConfigure\(\)/);
 assert.match(src,/onBackRequested:root.leaveConfigure\(\)/);
 let refreshed=0,focused=0;const root={configuring:true,loadCatalogue(){refreshed++}};
 const ctx=panelContext(['leaveConfigure'],root,{keyboard:{forceActiveFocus(){focused++}}});
 ctx.leaveConfigure();assert.equal(root.configuring,false);assert.equal(refreshed,1);assert.equal(focused,1);
});
test('import and scalar capture need no selected row; theme capture still does',()=>{
 let started=0;const root={opened:true,opening:false,actionBusy:false,actions:['import','capture','restore'],selected:0,matches:[],selectedRow:null,presetMode:true,generation:1};
 const src=fs.readFileSync(paths.panel,'utf8');
 const ctx=panelContext(['activate'],root,{backendPath:'/backend.py',action:{running:false,start(){started++}},catalogue:{running:false},lockProbe:{running:false}});
 if(src.includes('function selectionIndependent(')) {vm.runInContext(getFunction(src,'selectionIndependent'),ctx);root.selectionIndependent=v=>ctx.selectionIndependent(v);}
 ctx.activate('import',{version:1});assert.equal(started,1);assert.equal(ctx.action.command[4],'import:preset');
 root.actionBusy=false;ctx.activate('capture',{name:'Current'});assert.equal(started,2);assert.equal(ctx.action.command[4],'capture:current');
 root.actionBusy=false;root.presetMode=false;ctx.activate('capture',{name:'Theme'});assert.equal(started,2);
 ctx.activate('restore');assert.equal(started,3);
 assert.ok(src.includes('root.selectedRow!==null || root.selectionIndependent(modelData)'), 'button uses identical selection admission');
});
test('no-payload secondary verbs ignore stale and invalid action JSON',()=>{
 const calls=[],root={actionData:'{"version":1}',activate:(...args)=>calls.push(args)};
 const ctx=panelContext(['activateSecondary'],root);
 for(const raw of ['{"version":1}','not JSON']) {
  root.actionData=raw;
  for(const verb of ['export-preset','compare','preview','open-folder','copy-codepoint','shuffle']) {
   ctx.activateSecondary(verb);const args=calls.pop();assert.ok(args,verb);assert.equal(args[0],verb);assert.equal(args[1],undefined);
  }
 }
 root.actionData='{"index":2}';ctx.activateSecondary('copy-color');assert.deepEqual(plain(calls.pop()),['copy-color',{index:2}]);
 root.actionData='not JSON';ctx.activateSecondary('import');assert.equal(calls.length,0);assert.equal(root.message,'Invalid action JSON');
});
test('preference Unicode limits count codepoints while rejecting controls and lone surrogates',()=>{
 for(const value of ['😀'.repeat(129),'😀'.repeat(256),'A'.repeat(255)+'😀']) {
  assert.equal(api.preferenceText(value,256),true);
  const prefs={version:1,favorites:[value],recent:[],collections:{[value]:[value]},options:{}};
  assert.ok(api.actionResult(JSON.stringify({ok:true,preferences:prefs}),0,0,'').preferences);
  assert.ok(api.catalog(JSON.stringify({rows:[],preferences:prefs})).preferences);
 }
 for(const value of ['😀'.repeat(257),'A'.repeat(256)+'😀','\ud800','\udc00','a\u0085','a\n']) assert.equal(api.preferenceText(value,256),false);
 assert.equal(api.preferenceText('界'.repeat(1366),4096),false);
});
test('category selector uses the correct plural',()=>{
 const ctx=panelContext(['fieldOptions'],{rows:[]});
 assert.equal(ctx.fieldOptions('category')[0].label,'All categories');
});
test('failed Reset does not schedule a later unrelated view change',()=>{
 const root={opened:true,generation:1,actionGeneration:1,resetViewPending:true,view:'favorites'};
 const ctx=panelContext(['acceptAction'],root);
 ctx.acceptAction(1,0,JSON.stringify({ok:false,message:'Corrupt file'}),'');
 assert.equal(root.resetViewPending,false);assert.equal(root.view,'favorites');
});
test('collector boundary includes the encoder stdout newline without false failure',()=>{
 const base=JSON.stringify({ok:true,padding:''});
 const raw=JSON.stringify({ok:true,padding:'x'.repeat(1048576-Buffer.byteLength(base)-1)})+'\n';
 assert.equal(Buffer.byteLength(raw),1048576);assert.equal(api.actionResult(raw,0,0,'').ok,true);
 assert.equal(api.actionResult(raw+' ',0,0,'').ok,false);
 const multi=JSON.stringify({ok:true,padding:'界'.repeat(350000)});
 assert.ok(multi.length<1048576&&Buffer.byteLength(multi)>1048576);assert.equal(api.actionResult(multi,0,0,'').ok,false);
});
test('confirmed 104KB action uses the same 1MiB UTF8 cap as the collector',()=>{
 const prefs={version:1,favorites:Array.from({length:400},(_,i)=>'desktop-'+i+'x'.repeat(165)+'.desktop'),recent:[],collections:{Work:Array.from({length:100},(_,i)=>'界'.repeat(100)+i)},options:{}};
 const raw=JSON.stringify({ok:true,message:'Saved',preferences:prefs});
 assert.ok(Buffer.byteLength(raw)>104000);
 assert.equal(api.actionResult(raw,0,0,'').ok,true);
 assert.equal(api.actionResult(raw,0,0,'').preferences.favorites.length,400);
 assert.equal(api.actionResult(JSON.stringify({ok:true,detail:'界'.repeat(350000)}),0,0,'').ok,false);
 const src=fs.readFileSync(paths.panel,'utf8');
 assert.match(src,/id: action\s+byteLimit: 1048576/);
});
test('panel preferences use the existing owned action channel and reject lock/drain/closed writes',()=>{
 const src=fs.readFileSync(paths.panel,'utf8');
 assert.match(fs.readFileSync(path.join(paths.runtime,'Settings.qml'),'utf8'),/Keys.onEscapePressed:/,'native editor Escape returns to catalogue');
 assert.match(src,/if \(\(root.configuring \|\| root.previewing\) && event.key !== Qt.Key_Escape\) return;/,'hidden catalogue must not handle editor/comparison keys');
 function get(name){const start=src.indexOf('function '+name+'(');assert.ok(start>=0,'Missing '+name);let body=src.indexOf('{',start),depth=1,i=body+1,quote='',escape=false;for(;i<src.length;i++){const c=src[i];if(quote){if(escape)escape=false;else if(c==='\\\\')escape=true;else if(c===quote)quote='';continue;}if(c==='"'||c==="'"){quote=c;continue;}if(c==='{')depth++;if(c==='}'&&!--depth)break;}return src.slice(start,i+1);}
 const root={opened:true,opening:false,actionBusy:false,generation:3};let started=0;
 const ctx=vm.createContext({root,Controller:api,action:{running:false,start(){started++}},catalogue:{running:false},lockProbe:{running:false},backendPath:'/work/backend.py'});
 vm.runInContext(get('savePreferences'),ctx);
 ctx.savePreferences({options:{}});assert.equal(started,1);assert.equal(root.actionGeneration,3);assert.equal(ctx.action.command[2],'preferences');
 for(const key of ['action','catalogue','lockProbe']) {root.actionBusy=false;ctx[key].running=true;ctx.savePreferences({reset:true});assert.equal(started,1,key);ctx[key].running=false;}
 root.opened=false;ctx.savePreferences({reset:true});assert.equal(started,1);
 const writes=[];root.settingsSchema={view:{type:'enum'},collection:{type:'string'}};root.savePreferences=p=>writes.push(plain(p));
 vm.runInContext(get('setView'),ctx);ctx.setView('collection:Work');
 assert.deepEqual(writes.pop(),{options:{view:'all',collection:'Work'}});
 ctx.setView('all');assert.deepEqual(writes.pop(),{options:{view:'all',collection:''}});
 vm.runInContext(get('activateSecondary'),ctx);let capture;root.captureName='Pair';root.actionData=JSON.stringify({wallpaper:'/home/test/Pictures/local.png'});root.activate=(verb,payload)=>capture=plain(payload);
 ctx.activateSecondary('capture');assert.deepEqual(capture,{name:'Pair',wallpaper:'/home/test/Pictures/local.png'});
 ctx.action.cancel=ctx.catalogue.cancel=ctx.lockProbe.cancel=()=>{};
 root.previewing=true;root.actionPreview='/tmp/reference.png';root.actionData='private draft';root.actionDetail='private result';
 vm.runInContext(get('close'),ctx);ctx.close();
 assert.equal(root.previewing,false);assert.equal(root.actionPreview,'');assert.equal(root.actionData,'');assert.equal(root.actionDetail,'');
});
test('preferences payload is one bounded argv item and invalid values never become commands',()=>{
 assert.equal(typeof api.preferenceCommand,'function');
 const patch={options:{name:'quote\"; $(touch /tmp/no)'}};
 const command=plain(api.preferenceCommand('/work/backend.py',patch));
 assert.deepEqual(command,['/usr/bin/python3','/work/backend.py','preferences','--payload',JSON.stringify(patch),'--apply']);
 assert.equal(api.preferenceCommand('/work/backend.py',{options:{x:'界'.repeat(6000)}}),null);
 assert.equal(api.preferenceCommand('/work/backend.py',{recent:[]}),null);
 assert.equal(api.preferenceCommand('/work/backend.py',{reset:true,options:{}}),null);
});
test('saved view filters run before the display cap and recent preserves recency order',()=>{
 const rows=Array.from({length:300},(_,i)=>({id:String(i),label:'Row '+i,detail:'',category:i===299?'Tools':'Games',provider:'Local',installed:i===299}));
 const prefs={version:1,favorites:['299'],recent:['299','2'],collections:{Work:['299']},options:{}};
 for(const view of ['favorites','collection:Work']) assert.equal(api.viewRows(rows,'',prefs,view,'','','')[0].id,'299');
 assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'recent','','',''),r=>r.id),['299','2']);
 assert.equal(api.viewRows(rows,'',prefs,'all','Tools','Local','installed')[0].id,'299');
});
test('large saved views avoid a linear member scan for every catalogue row',()=>{
 const rows=Array.from({length:10757},(_,i)=>({id:'row-'+i,label:'Row '+i}));
 const ids=rows.slice(-512).map(r=>r.id),originalIndexOf=ids.indexOf;
 let scans=0;ids.indexOf=function(value){scans++;return originalIndexOf.call(this,value);};
 const prefs={favorites:ids,recent:[],collections:{}};
 const before=JSON.stringify(prefs);
 const result=api.viewRows(rows,'',prefs,'favorites','','','');
 assert.deepEqual(Array.from(result,r=>r.id),Array.from(api.filter(rows.slice(-512),''),r=>r.id));
 assert.equal(JSON.stringify(prefs),before);
 assert.ok(scans<=ids.length,'membership work must not rescan the selected IDs for all '+rows.length+' rows; scans='+scans);
});
test('indexed membership preserves prototype-shaped IDs and empty saved views',()=>{
 const rows=['constructor','__proto__','toString','😀','plain'].map(id=>({id,label:id}));
 const collections=Object.create(null);collections.__proto__=['__proto__','😀'];
 const prefs={favorites:['constructor','😀'],recent:['😀','constructor'],collections};
 assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'favorites','','',''),r=>r.id),['constructor','😀']);
 assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'recent','','',''),r=>r.id),['😀','constructor']);
 assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'collection:__proto__','','',''),r=>r.id),['__proto__','😀']);
 assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'collection:missing','','','')),[]);
 prefs.favorites=[];assert.deepEqual(Array.from(api.viewRows(rows,'',prefs,'favorites','','','')),[]);
});
test('new metadata is independently validated and known secondary verbs remain secondary',()=>{
 const schema={count:{type:'integer',minimum:2,maximum:16,default:4,label:'Colors'}};
 const prefs={version:1,favorites:['a'],recent:['b'],collections:{Work:['a']},options:{count:4}};
 const result=api.catalog(JSON.stringify({rows:[{id:'a',label:'A',favorite:true,category:'Tools',provider:'Local',installed:false,collection:'Work',swatches:['#112233','bad']}],actions:['copy','favorite','copy-codepoint','evil'],preferences:prefs,settingsSchema:schema}));
 assert.equal(result.rows[0].favorite,true);assert.equal(result.rows[0].installed,false);
 assert.deepEqual(plain(result.rows[0].swatches),['#112233']);
 assert.deepEqual(plain(result.preferences),prefs);assert.deepEqual(plain(result.settingsSchema),schema);
 assert.deepEqual(plain(result.actions),['copy','favorite','copy-codepoint']);
 assert.equal(api.primaryVerb(['favorite','restore','copy-codepoint']),'');
 assert.equal(api.primaryVerb(['favorite','copy','restore']),'copy');
});
