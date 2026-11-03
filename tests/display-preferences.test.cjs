// SPDX-License-Identifier: GPL-3.0-only
const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const paths=require('./shared-paths.cjs');
const api=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(paths.runtime,'Controller.js'),'utf8'),api);
const ids=rows=>Array.from(rows,r=>r.id);
const getFunction=require('./panel-functions.cjs');
test('filter reset changes presentation only and native buttons accept keyboard focus',()=>{
 const src=fs.readFileSync(paths.panel,'utf8');let focus=0;
 const root={query:'find',categoryFilter:'Tools',providerFilter:'Local',installedFilter:'installed',selected:3,actions:['restore'],preferences:{options:{}}};
 const ctx=vm.createContext({root,keyboard:{forceActiveFocus(){focus++}}});vm.runInContext(getFunction(src,'clearFilters'),ctx);ctx.clearFilters();
 for(const key of ['query','categoryFilter','providerFilter','installedFilter'])assert.equal(root[key],'');
 assert.equal(focus,1);assert.deepEqual(root.actions,['restore']);
 for(const line of src.split('\n').filter(line=>/Button \{/.test(line)))assert.match(line,/focusable:true/,'native action keyboard focus: '+line);
 assert.ok(src.indexOf('objectName:"lego-configure"')<src.indexOf('objectName: "lego-search"'),'Configure is secondary in toolbar');
});
test('panel selection follows the selected ID across sort changes and clamps a removed selection',()=>{
 const root={matches:[{id:'b'},{id:'a'}],selected:0,selectedId:'a'};
 const ctx=vm.createContext({root});vm.runInContext(getFunction(fs.readFileSync(paths.panel,'utf8'),'reconcileSelection'),ctx);
 ctx.reconcileSelection();assert.equal(root.selected,1);assert.equal(root.selectedId,'a');
 root.matches=[{id:'b'}];ctx.reconcileSelection();assert.equal(root.selected,0);assert.equal(root.selectedId,'b');
 root.matches=[];ctx.reconcileSelection();assert.equal(root.selected,0);assert.equal(root.selectedId,'');
});
test('panel consumes density and both layouts for galleries and presets without trusting primary verbs',()=>{
 const src=fs.readFileSync(paths.panel,'utf8');
 function binding(name,root){const match=src.match(new RegExp('readonly property (?:bool|string) '+name+': ([^\\n]+)'));assert.ok(match,'missing '+name);return vm.runInNewContext(match[1],{root,Controller:api});}
 for(const presetMode of [true,false])for(const layout of ['grid','list','bad']) {
  const root={presetMode,preferences:{options:{layout,density:'compact'}}};
  assert.equal(binding('listMode',root),layout==='list'||layout==='bad'&&presetMode);
  assert.equal(binding('dense',root),true);
 }
 assert.match(src,/Controller.primaryVerb\(actions, root.settingsSchema.primaryAction \? root.preferences.options : null\)/);
 assert.match(src,/function featureRevision\(\) \{ return '0.4.1'; \}/);
 for(const verb of ['copy-unicode','copy-app-id','copy-css'])assert.ok(JSON.parse(fs.readFileSync(path.join(paths.runtime,'i18n/en.json'),'utf8'))[verb]);
 assert.match(src,/text:strings.t\(modelData\)/);
});
test('fixed copy verbs survive validation and dispatch without stale payload or primary promotion',()=>{
 const verbs=['copy-unicode','copy-app-id','copy-css'];
 assert.deepEqual(Array.from(api.catalog(JSON.stringify({rows:[],actions:[...verbs,'evil']})).actions),verbs);
 assert.deepEqual(Array.from(api.actionResult(JSON.stringify({ok:true,actions:verbs}),0,0,'').actions),verbs);
 assert.equal(api.primaryVerb(verbs),'');
 const root={actionData:'not JSON',actions:verbs,opened:true,selected:0,matches:[{id:'known'}],generation:1};let starts=0;
 const action={running:false,start(){starts++}};
 const ctx=vm.createContext({root,Controller:api,action,catalogue:{running:false},lockProbe:{running:false},backendPath:'/backend.py'});
 const source=fs.readFileSync(paths.panel,'utf8');
 for(const name of ['activate','selectionIndependent','activateSecondary'])vm.runInContext(getFunction(source,name),ctx);
 root.activate=(...args)=>ctx.activate(...args);root.selectionIndependent=v=>ctx.selectionIndependent(v);
 for(const verb of verbs){root.actionBusy=false;ctx.activateSecondary(verb);assert.equal(action.command[6],verb);assert.equal(action.command.length,8);}
 assert.equal(starts,3);root.actionBusy=false;ctx.activate('evil');assert.equal(starts,3);
});
test('Motion primary preference selects only advertised apply or preview',()=>{
 assert.equal(api.primaryVerb(['apply','preview'],{primaryAction:'preview'}),'preview');
 assert.equal(api.primaryVerb(['apply'],{primaryAction:'preview'}),'apply');
 assert.equal(api.primaryVerb(['copy','preview'],{primaryAction:'preview'}),'copy');
 assert.equal(api.primaryVerb(['apply','preview'],{primaryAction:'restore'}),'apply');
 assert.equal(api.primaryVerb(['preview'],{primaryAction:'preview'}),'');
});
test('saved favorite removal overrides stale catalogue favorite markers',()=>{
 const rows=[{id:'one',label:'One',favorite:true},{id:'two',label:'Two'}];
 const prefs={favorites:['two'],recent:[],collections:{},options:{sortOrder:'favorites-first'}};
 assert.deepEqual(ids(api.viewRows(rows,'',prefs,'all','','','')),['two','one']);
});
test('saved sort is stable, nonmutating, and precedes the display cap',()=>{
 const rows=Array.from({length:300},(_,i)=>({id:String(i),label:i===299?'A':'Same',detail:'',favorite:i===298}));
 const before=JSON.stringify(rows), prefs={favorites:['299'],recent:[],collections:{},options:{sortOrder:'name'}};
 assert.equal(api.viewRows(rows,'',prefs,'all','','','')[0].id,'299');
 assert.deepEqual(ids(api.viewRows(rows,'',prefs,'all','','','')).slice(1,5),['0','1','2','3']);
 prefs.options.sortOrder='favorites-first';assert.deepEqual(ids(api.viewRows(rows,'',prefs,'all','','','')).slice(0,3),['299','0','1']);
 prefs.options.sortOrder='default';assert.deepEqual(ids(api.viewRows(rows,'',prefs,'all','','','')).slice(0,3),['0','1','2']);
 prefs.options.sortOrder='unknown';assert.equal(api.viewRows(rows,'',prefs,'all','','','')[0].id,'0');
 prefs.recent=['299','2'];assert.deepEqual(ids(api.viewRows(rows,'',prefs,'recent','','','')),['299','2']);
 assert.equal(JSON.stringify(rows),before);
});

test('public identity, runtime revision and stable preference slug match the manifest',()=>{
 const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../manifest.json'),'utf8'));
 const backend=fs.readFileSync(path.join(paths.runtime,'backend.py'),'utf8');
 const slug=backend.match(/^SLUG = '([a-z-]+)'$/m)[1];
 assert.equal(manifest.id,'battlelamb.'+slug);
 assert.equal(manifest.author,'Battlelamb');
 assert.equal(manifest.version,'0.4.1');
 assert.equal(manifest.entryPoints.overlay,'runtime/'+manifest.version+'/'+path.basename(paths.panel));
 assert.deepEqual(fs.readdirSync(path.join(__dirname,'../runtime')),[manifest.version]);
 const source=fs.readFileSync(paths.panel,'utf8');
 assert.ok(source.includes('WlrLayershell.namespace: "battlelamb-'+slug+'"'));
 assert.ok(source.includes("function featureRevision() { return '"+manifest.version+"'; }"));
 assert.ok(fs.readFileSync(path.join(__dirname,'../README.md'),'utf8').includes('omarchy/lego/'+slug+'/preferences.json'));
});
test('current public files contain no machine-specific paths or personal manifest metadata',()=>{
 const root=path.resolve(__dirname,'..');
 function inspect(directory) {
  for(const entry of fs.readdirSync(directory,{withFileTypes:true})) {
   if(['.git','release-output','__pycache__'].includes(entry.name)||entry.name.includes('.bak-'))continue;
   const file=path.join(directory,entry.name);
   if(entry.isDirectory()) {inspect(file);continue;}
   const bytes=fs.readFileSync(file);if(bytes.includes(0))continue;
   const text=bytes.toString('utf8');
   assert.doesNotMatch(text,/\/home\/(?!test(?:\/|['"\s])|user(?:\/|['"\s]))[a-zA-Z0-9_.-]+\//,path.relative(root,file));
   assert.doesNotMatch(text,/\/srv\/[a-zA-Z0-9_.-]+\//,path.relative(root,file));
   if(entry.name==='manifest.json')assert.equal(JSON.parse(text).author,'Battlelamb');
  }
 }
 inspect(root);
});
