"""Real Qt layout checks with an offscreen FloatingWindow surface adapter.
Only OverlayWindow/layer-shell surface plumbing and lock probe are substituted.
Native tokens, controls, layouts, models and request ownership are unchanged.
"""
from pathlib import Path
import json
import hashlib
import shutil
import subprocess
import tempfile
import os
import signal
import time

from shared_paths import ROOT as root
evidence=Path('/evidence') if Path('/evidence').is_dir() else Path('/tmp/shared-native')
evidence.mkdir(parents=True,exist_ok=True)
manifests=[root/'manifest.json'] if (root/'manifest.json').is_file() else sorted((root/'candidates').glob('*/manifest.json'))
Path('/tmp/runtime').mkdir(mode=0o700,exist_ok=True)
results=[]
sources=[file for m in manifests for file in (m.parent/json.loads(m.read_text())['entryPoints']['overlay']).parent.iterdir() if file.suffix in ('.py','.js','.qml')]
source_hashes={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in sources}
evidence.joinpath('source-sha256.json').write_text(json.dumps(source_hashes,indent=2))
for manifest_path in manifests:
    directory=manifest_path.parent
    manifest=json.loads(manifest_path.read_text())
    slug=manifest['id'].split('.')[-1]
    runtime=directory/manifest['entryPoints']['overlay']
    response=subprocess.run(['/usr/bin/python3',str(runtime.parent/'backend.py'),'preferences'],capture_output=True,text=True,timeout=10)
    assert response.returncode==0,(slug,response.stdout,response.stderr)
    snapshot=json.loads(response.stdout)
    assert snapshot.get('ok') is True
    for mode,width,height in [('wide',1150,850),('compact',580,690),('wide-tall',1150,850),('compact-tall',580,690),('compact-light',580,690)]:
        with tempfile.TemporaryDirectory() as tmp:
            host=Path(tmp)
            for name in ['Ui','Commons','services','plugins']:
                (host/name).symlink_to('/usr/share/omarchy/shell/'+name)
            for name in ['Controller.js','Settings.qml','BoundedProcess.qml']:
                shutil.copy2(runtime.parent/name,host/name)
            for name in ['backend.py','preferences.py']:
                shutil.copy2(runtime.parent/name,host/name)
            if (runtime.parent/'data').exists():
                (host/'data').symlink_to(runtime.parent/'data')
            for helper in runtime.parent.glob('*.py'):
                if not (host/helper.name).exists():
                    shutil.copy2(helper,host/helper.name)
            shutil.copytree(runtime.parent/'i18n',host/'i18n')
            text=runtime.read_text().replace('OverlayWindow {','FloatingWindow {\n        implicitWidth:'+str(width)+'; implicitHeight:'+str(height))
            text=text.replace('shown: root.opened','visible: root.opened')
            text='\n'.join(line for line in text.split('\n') if 'WlrLayershell.namespace:' not in line and 'onTargetScreenChanged:' not in line)
            text=text.replace('id: root','id: root\n    property var testPanel: panel\n    property var testKeyboard: keyboard\n    property int testCatalogueLoads: 0',1).replace('/usr/bin/omarchy-hyprland-session-locked','/usr/bin/false')
            text=text.replace('catalogue.start();','root.testCatalogueLoads++;catalogue.start();')
            if os.environ.get('NATIVE_LAYOUT_OLD')=='1':
                text=text.replace('Math.min(Style.space(240), compactTitle.implicitHeight + smallMetrics.height + compactSwatches.implicitHeight + Style.space(12))','Math.min(Style.space(64), compactLabels.implicitHeight)').replace('Layout.minimumHeight: Layout.preferredHeight','')
            (evidence/(slug+'-'+mode+'-adapted.qml')).write_text(text)
            (host/'Candidate.qml').write_text(text)
            fixture={'rows':[{'id':'fixture','label':'<b>Plain long selected metadata</b> '+('A'*80),'detail':'<img src=bad> '+('Long metadata with swatches and category. '*20),'category':'Tools','provider':'Local','installed':True,'favorite':True,'swatches':['#112233','#abcdef'],'preview':'','glyph':'X','color':''}], 'actions':['apply','favorite','capture','import','export-preset','compare','restore'], 'preferences':snapshot['preferences'],'settingsSchema':snapshot['settingsSchema']}
            chip_fixture=dict(fixture, rows=[{'id':'chip-fixture','label':'A'*160,'detail':'Short chip fixture.','category':'<b>'+('C'*249)+'</b>','provider':'<i>'+('P'*249)+'</i>','installed':False}])
            choices=[{'id':str(i),'label':label,'detail':'One complete description line.'} for i,label in enumerate(['First choice','Second choice','Third choice'])]
            if (runtime.parent/'data/presets.json').is_file():
                choices += [{'id':row['id'],'label':row['label'],'detail':row['detail']+' Backend status: offline reference only.'} for row in json.loads((runtime.parent/'data/presets.json').read_text())]
            qml='''import QtQuick
import Quickshell
import QtTest
import qs.Commons as Commons
ShellRoot {
 id:h
 property int phase:0
 onPhaseChanged:console.log("PHASE "+h.phase)
 property int beforeLoads:0
 property var savedOptions: ({})
 property bool savedReadback:false
 property int choiceIndex:0
 property int presentationStep:0
 property string selectionBefore:""
 property var choices:@CHOICES@
 Candidate {id:c}
 BoundedProcess {id:readback;command:["/usr/bin/python3",c.backendPath,"preferences"];onCompleted:(code,status,text,error)=>{h.check(code===0&&status===0&&!error,"independent backend preferences readback");var data=JSON.parse(text);h.check(JSON.stringify(data.preferences.options)===JSON.stringify(h.savedOptions),"native saved fields persisted on disk");h.savedReadback=true;console.log("SAVED_OPTIONS "+JSON.stringify(data.preferences.options));}}
 TestCase {id:keyDriver;name:"ConfigureKeys";when:false;parent:c.testPanel.contentItem}
 property string stage:"startup"
 function check(ok,message) {if(!ok) {console.log("FAIL "+h.stage+": "+message);Qt.exit(1);throw new Error(message);}}
 function until(name,predicate) {
  if(h.stage!==name)console.log("STAGE "+name);h.stage=name;
  var deadline=Date.now()+2000;
  var ready=predicate();
  while(!ready&&Date.now()<deadline){keyDriver.wait(1);ready=predicate();}
  h.check(ready,"bounded readiness/effect deadline");
 }
 function geometry(item) {
  if(!item.visible)return [];
  var values=[item.x,item.y,item.width,item.height,item.implicitWidth,item.implicitHeight,item.visible];
  if(item.text!==undefined)values.push(item.text);
  if(item.contentY!==undefined)values.push(item.contentY,item.contentHeight);
  for(var i=0;i<item.children.length;i++)values.push(h.geometry(item.children[i]));
  return values;
 }
 function settle(name) {
  var previous="",stable=0;
  h.until(name,function(){
   // Drain deferred bindings as well as the window's native layout polish.
   keyDriver.wait(1);
   var current=JSON.stringify(h.geometry(c.testPanel.contentItem));
   stable=!keyDriver.isPolishScheduled(c.testPanel.contentItem.Window.window)&&current===previous?stable+1:0;
   previous=current;return stable>=2;
  });
 }
 function key(item,value,modifiers) {
  item.forceActiveFocus();h.until("native key focus",function(){return item.activeFocus;});
  keyDriver.keyClick(value,modifiers===undefined?Qt.NoModifier:modifiers,0);
 }
 function find(item,name) {if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var result=find(item.children[i],name);if(result)return result;}return null;}
 function button(item,text) {if(item.text===text&&item.clicked!==undefined)return item;for(var i=0;i<item.children.length;i++){var result=button(item.children[i],text);if(result)return result;}return null;}
 Timer {interval:0;running:true;onTriggered:{
  h.until("initial fixture and surface",function(){return c.testPanel.visible&&c.rows.length===1&&c.selectedRow!==null;});
  Commons.Color.shellFile.text();Commons.Color.userShellFile.text();
  Commons.Style.fontFamily="@FONT@";
  if("@MODE@".indexOf("tall")>=0)Commons.Style.fontOverrides={"body":22,"body-small":20,"title":24,"heading":26};
  if("@MODE@".indexOf("light")>=0){Commons.Color.background="#f4f4ef";Commons.Color.foreground="#202426";Commons.Color.accent="#285e8e";}
  h.settle("initial native layout");
  h.check(Commons.Style.fontFamily==="@FONT@"&&("@MODE@".indexOf("tall")<0||Commons.Style.font.body===22&&Commons.Style.font.bodySmall===20),"actual test typography applied");
  var card=h.find(c.testPanel.contentItem,"lego-card"),grid=h.find(c.testPanel.contentItem,"lego-results");
  h.check(card!==null&&grid!==null,"native objects exist");
  h.check(h.find(c.testPanel.contentItem,"lego-swatches")!==null,"validated swatches are rendered");
  h.check(grid.width>=100&&grid.height>=65,"positive usable grid "+grid.width+"x"+grid.height);
  h.check(card.x>=0&&card.y>=0&&card.x+card.width<=c.testPanel.width+1&&card.y+card.height<=c.testPanel.height+1,"contained card");
  function installationLabel(item) {if(item.text==="All installations"&&item.visible)return item;for(var i=0;i<item.children.length;i++){var found=installationLabel(item.children[i]);if(found)return found;}return null;}
  var installation=installationLabel(c.testPanel.contentItem);
  function toolbarTitle(item) {if(item.text===@TITLE@ && item.visible)return item;for(var i=0;i<item.children.length;i++){var found=toolbarTitle(item.children[i]);if(found)return found;}return null;}
  var heading=toolbarTitle(c.testPanel.contentItem);h.check(heading!==null&&!heading.truncated,"native toolbar keeps complete plugin title");
  h.check(installation!==null&&!installation.truncated,"native installation label not elided");
  console.log("GEOMETRY "+JSON.stringify({card:[card.width,card.height],grid:[grid.width,grid.height],compact:card.compact}));
  var detail=h.find(c.testPanel.contentItem,card.compact ? "lego-compact-detail" : "lego-detail");
  function label(item,text) {if(item.text===text && item.font!==undefined && item.visible)return item;for(var i=0;i<item.children.length;i++){var found=label(item.children[i],text);if(found)return found;}return null;}
  var title=label(detail,c.selectedRow.label),body=label(detail,c.selectedRow.detail);
  h.check(title!==null && body!==null,"native selected text exists");
  var titleY=title.mapToItem(detail,0,0).y,bodyY=body.mapToItem(detail,0,0).y;
  var fullLine=body.height/Math.max(1,body.lineCount);
  var detailOrigin=detail.mapToItem(card,0,0),titleOrigin=title.mapToItem(card,0,0),bodyOrigin=body.mapToItem(card,0,0);
  console.log("LINEBOX "+JSON.stringify({viewport:detail.height,titleY:titleY,titleHeight:title.height,bodyY:bodyY,fullLine:fullLine,font:body.font.family,pixels:body.font.pixelSize,detail:[detailOrigin.x,detailOrigin.y,detail.width,detail.height],title:[titleOrigin.x,titleOrigin.y,title.width,title.height],body:[bodyOrigin.x,bodyOrigin.y,body.width,fullLine]}));
  var lineOkay=titleY>=0 && titleY+title.height<=detail.height+0.1 && bodyY+fullLine<=detail.height+0.1;
  h.check(detail.clip&&detail.height>0&&detail.contentHeight>detail.height,"long authoritative metadata has real bounded scrolling");
  card.grabToImage(function(result){h.check(result.saveToFile("@CATALOG_IMAGE@"),"offscreen catalogue capture");h.check(lineOkay,"complete selected title and one full body line fit");chips.start();});
 }}
 property int chipStep:0
 function contained(item,container,name) {
  var p=item.mapToItem(container,0,0);
  h.check(item.visible&&item.width>0&&item.height>0&&p.x>=-0.1&&p.y>=-0.1&&p.x+item.width<=container.width+0.1&&p.y+item.height<=container.height+0.1,"UI-1 @MODE@ "+name+" contained");
  return [p.x,p.y,item.width,item.height];
 }
 function chipCheck(kind,text) {
  var card=h.find(c.testPanel.contentItem,"lego-card"),flow=h.find(card,"lego-filter-chips"),chip=h.button(flow,text);
  h.check(flow.visible&&chip!==null,"UI-1 @MODE@ "+kind+" chip visible");
  var geometry=chip.mapToItem(card,0,0);
  console.log("CHIP_GEOMETRY "+JSON.stringify({mode:"@MODE@",kind:kind,queryLength:c.query.length,card:[card.width,card.height],flow:[flow.width,flow.height],chip:[geometry.x,geometry.y,chip.width,chip.height],naturalWidth:chip.implicitWidth}));
  h.contained(chip,flow,kind+" chip in Flow");h.contained(chip,card,kind+" chip in card");
  var label;
  function findLabel(item){if(item.text===text&&item.textFormat!==undefined)return item;for(var i=0;i<item.children.length;i++){var found=findLabel(item.children[i]);if(found)return found;}return null;}
  label=findLabel(chip);h.check(label!==null&&label.textFormat===Text.PlainText,"UI-1 native chip keeps literal PlainText");
  h.contained(label,chip,kind+" native fit/elide label");
  h.check(chip.focusable&&chip.activeFocusOnTab,"UI-1 chip remains keyboard focusable");
  var search=h.find(card,"lego-search"),clear=h.button(search,"×");
  h.check(clear.visible===(c.query.length>0),"UI-1 search clear visibility");
  if(clear.visible){h.contained(clear,card,"search clear in card");h.contained(clear,c.testPanel.contentItem,"search clear in window");h.check(clear.Accessible.name.length>0,"UI-1 named clear affordance");}
  return chip;
 }
 Timer {id:chips;interval:0;onTriggered:{
  h.settle("chips "+h.chipStep);
  var card=h.find(c.testPanel.contentItem,"lego-card"),flow=h.find(card,"lego-filter-chips"),search=h.find(card,"lego-search"),clear=h.button(search,"×");
  if(h.chipStep===0){
   h.check(c.query===""&&!flow.visible&&!clear.visible,"UI-1 empty query hides chips and clear");
   c.acceptCatalogue(0,0,JSON.stringify(@CHIP_FIXTURE@),"");
   h.check(c.rows.length===1&&c.rows[0].category.length===256&&c.rows[0].provider.length===256,"UI-1 long filters admitted by actual Controller");
   for(var i=0;i<3;i++)h.key(c.testKeyboard,"A",Qt.ShiftModifier);
  } else if(h.chipStep===1){
   h.until("short query delivered",function(){return c.query==="AAA";});h.check(c.query==="AAA","UI-1 short query entered through native keyboard");
   var chip=h.chipCheck("short-query","Search: "+c.query+" ×");h.check(Math.abs(chip.width-chip.implicitWidth)<0.1,"UI-1 short chip keeps natural width");
   chip.forceActiveFocus();h.check(chip.activeFocus,"UI-1 short chip keyboard focus");h.key(chip,Qt.Key_Return);
   h.until("query chip clear and focus",function(){return c.query===""&&c.testKeyboard.activeFocus;});h.check(c.query===""&&c.testKeyboard.activeFocus,"UI-1 query chip keyboard activation clears query and restores search focus");
  } else if(h.chipStep===2){
   h.until("cleared chip visibility",function(){return !flow.visible&&!clear.visible;});h.check(!flow.visible&&!clear.visible,"UI-1 cleared query hides chips and clear");
   for(var i=0;i<128;i++)h.key(c.testKeyboard,"A",Qt.ShiftModifier);
  } else if(h.chipStep===3){
   h.until("long query delivered",function(){return c.query==="A".repeat(128)&&c.matches.length===1;});h.check(c.query==="A".repeat(128)&&c.matches.length===1,"UI-1 allowed 128-character query matches admitted 160-character label");
   h.chipCheck("long-query","Search: "+c.query+" ×");
   chips.stop();card.grabToImage(function(result){h.check(result.saveToFile("@CHIP_IMAGE@"),"UI-1 long-query native capture");h.chipStep++;chips.start();});return;
  } else if(h.chipStep===4){
   clear.forceActiveFocus();h.check(clear.activeFocus,"UI-1 clear affordance keyboard focus");h.key(clear,Qt.Key_Return);
   h.until("search clear effect",function(){return c.query===""&&c.selected===0&&c.testKeyboard.activeFocus;});h.check(c.query===""&&c.selected===0&&c.testKeyboard.activeFocus,"UI-1 search clear keyboard activation clears query");c.categoryFilter=c.rows[0].category;
  } else if(h.chipStep===5){
   var chip=h.chipCheck("long-category",c.categoryFilter+" ×");chip.forceActiveFocus();h.key(chip,Qt.Key_Space);h.until("category clear effect",function(){return c.categoryFilter==="";});h.check(c.categoryFilter==="","UI-1 category chip clears filter");c.providerFilter=c.rows[0].provider;
  } else if(h.chipStep===6){
   var chip=h.chipCheck("long-provider",c.providerFilter+" ×");chip.forceActiveFocus();h.key(chip,Qt.Key_Return);h.until("provider clear effect",function(){return c.providerFilter==="";});h.check(c.providerFilter==="","UI-1 provider chip clears filter");c.installedFilter="uninstalled";
  } else if(h.chipStep===7){
   var chip=h.chipCheck("installed",c.installedFilter+" ×");chip.forceActiveFocus();h.key(chip,Qt.Key_Return);h.until("installed clear effect",function(){return c.installedFilter==="";});h.check(c.installedFilter==="","UI-1 installed chip clears filter");
   c.query="A".repeat(128);c.categoryFilter=c.rows[0].category;c.providerFilter=c.rows[0].provider;c.installedFilter="uninstalled";
  } else if(h.chipStep===8){
   h.chipCheck("combined-query","Search: "+c.query+" ×");h.chipCheck("combined-category",c.categoryFilter+" ×");h.chipCheck("combined-provider",c.providerFilter+" ×");h.chipCheck("combined-installed",c.installedFilter+" ×");
   var reset=h.button(flow,"Clear filters");h.contained(reset,card,"Clear filters in card");reset.forceActiveFocus();h.key(reset,Qt.Key_Return);
   h.until("all filters clear effect",function(){return !c.query&&!c.categoryFilter&&!c.providerFilter&&!c.installedFilter&&c.testKeyboard.activeFocus;});h.check(!c.query&&!c.categoryFilter&&!c.providerFilter&&!c.installedFilter&&c.testKeyboard.activeFocus,"UI-1 Clear filters keyboard activation clears all filters");
  } else {
   h.until("cleared chip visibility",function(){return !flow.visible&&!clear.visible;});h.check(!flow.visible&&!clear.visible,"UI-1 reset hides chips and clear");chips.stop();console.log("PASS UI-1 @SLUG@ @MODE@ native chip containment and clear");
   c.rows=h.choices;c.preferences={version:1,favorites:[],recent:[],collections:{},options:Object.assign({},c.preferences.options,{layout:"list"})};c.selected=0;c.testKeyboard.forceActiveFocus();walk.start();
  }
  h.chipStep++;if(h.chipStep<10)chips.start();
 }}
 Timer {id:walk;interval:0;onTriggered:{
  h.settle("choice "+h.choiceIndex);
  var grid=h.find(c.testPanel.contentItem,"lego-results");
  h.check(c.selected===h.choiceIndex && c.selectedRow.id===h.choices[h.choiceIndex].id,"native keyboard reaches choice "+h.choiceIndex);
  var tile=grid.itemAtIndex(c.selected);h.check(tile!==null,"selected choice instantiated");var y=tile.y-grid.contentY;
  h.check(y>=-0.1 && y+tile.height<=grid.height+0.1,"selected choice fully visible through keyboard scrolling "+h.choiceIndex);
  if(h.choiceIndex+1<h.choices.length){h.choiceIndex++;h.key(c.testKeyboard,Qt.Key_Down);walk.start();return;}
  walk.stop();console.log("KEYBOARD_CHOICES "+h.choices.length);h.selectionBefore=c.selectedRow.id;presentation.start();
 }}
 Timer {id:presentation;interval:0;onTriggered:{
  h.settle("presentation "+h.presentationStep);
  var grid=h.find(c.testPanel.contentItem,"lego-results");
  h.check(c.selectedRow.id===h.selectionBefore,"QV4 selected ID survives presentation ordering");
  if(h.presentationStep>0){h.check(grid.columns===(c.listMode?1:Math.max(1,Math.floor(grid.width/Commons.Style.space(c.glyphMode?104:176)))),"saved grid/list applied in native layout");h.check(c.dense===((h.presentationStep-1)%2===1),"native density applied");}
  if(h.presentationStep===4){presentation.stop();c.configuring=true;inspect.restart();return;}
  var step=h.presentationStep++;
  c.preferences={version:1,favorites:[h.choices[0].id],recent:[],collections:{},options:Object.assign({},c.preferences.options,{layout:step<2?"list":"grid",density:step%2?"compact":"comfortable",sortOrder:step%2?"favorites-first":"name"})};presentation.start();
 }}
 Timer {id:inspect;interval:0;onTriggered:{
  h.settle("Configure layout");
  var editor=h.find(c.testPanel.contentItem,"lego-settings");
  h.check(editor.visible&&editor.width>100&&editor.height>100,"settings page visible and contained");
  var keys=Object.keys(c.settingsSchema);
  for(var i=0;i<keys.length;i++)h.check(editor.findControl("option-"+keys[i])!==null,"actual schema control "+keys[i]);
  h.find(c.testPanel.contentItem,"lego-card").grabToImage(function(result){h.check(result.saveToFile("@IMAGE@"),"offscreen capture");console.log("LAYOUT native-panel @SLUG@ @MODE@ controls="+keys.length);writes.start();});
 }}
 Timer {id:writes;interval:0;onTriggered:{
  try {
  h.until("preferences idle phase "+h.phase,function(){return !c.preferencesBusy;});
  h.settle("preferences phase "+h.phase);
  h.until("preferences admission phase "+h.phase,function(){return !c.preferencesBusy;});
  var editor=h.find(c.testPanel.contentItem,"lego-settings");
  if(h.phase===0){
   var keys=Object.keys(c.settingsSchema);for(var i=0;i<keys.length;i++){
    var k=keys[i],spec=c.settingsSchema[k],control=editor.findControl("option-"+k);
    if(spec.type==="enum")control.changed(spec.choices[(spec.choices.indexOf(spec.default)+1)%spec.choices.length]);
    else if(spec.type==="boolean")control.clicked();
    else if(spec.type==="integer"){control.text=String(spec.default===spec.maximum?spec.minimum:spec.maximum);control.textEdited();}
   }
   h.savedOptions=JSON.parse(JSON.stringify(editor.draft));var save=editor.findControl("lego-settings-save");h.check(save.enabled,"native Save enabled for changed valid fields");save.clicked();h.phase=1;return;
  }
  if(h.phase===1){h.check(JSON.stringify(c.preferences.options)===JSON.stringify(h.savedOptions),"native Save acknowledged typed options");h.check(!editor.dirty,"save acknowledgment clears dirty state");readback.start();h.phase=11;return;}
  if(h.phase===11){h.until("independent saved readback",function(){return h.savedReadback;});h.until("preference patch admission",function(){return !c.preferencesBusy;});c.savePreferences({favorites:["native-@MODE@"],collections:{"Native test":["native-@MODE@"]}});h.phase=2;return;}
  if(h.phase===2){h.check(c.preferences.favorites[0]==="native-@MODE@"&&c.preferences.collections["Native test"][0]==="native-@MODE@","real preference patch acknowledged");c.view="favorites";editor.findControl("lego-settings-reset").clicked();h.phase=3;return;}
  if(h.phase===3){
   h.check(c.preferences.favorites.length===0&&Object.keys(c.preferences.collections).length===0&&c.view==="all","native Reset acknowledged and stale view cleared");
   h.beforeLoads=c.testCatalogueLoads;editor.backRequested();h.until("Configure exit effect",function(){return !c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1;});h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"Back refreshes and restores catalogue focus");h.phase=4;return;
  }
  if(h.phase===4){h.beforeLoads=c.testCatalogueLoads;c.configuring=true;h.key(editor,Qt.Key_Escape);h.phase=5;return;}
  if(h.phase===5){
   h.until("Configure exit effect",function(){return !c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1;});h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"native editor Escape refreshes and restores catalogue focus");
   h.beforeLoads=c.testCatalogueLoads;c.configuring=true;h.key(c.testKeyboard,Qt.Key_Escape);h.phase=6;return;
  }
  if(h.phase===6){
   h.until("Configure exit effect",function(){return !c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1;});h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"native catalogue Escape refreshes and restores catalogue focus");
   c.rows=[];c.actions=["import","capture"];c.organizing=true;
   h.check(h.button(c.testPanel.contentItem,"Import preset").enabled,"native Import button enabled without selection");
   h.check(h.button(c.testPanel.contentItem,"Capture preset").enabled===c.presetMode,"native Capture admission follows mode not stale selection");
   console.log("PASS native-panel @SLUG@ @MODE@ save-patch-reset-back-escape");h.phase=7;c.close();Qt.exit(0);
  }
  } finally {if(h.phase!==7)writes.start();}
 }}
 Timer {interval:12000;running:true;onTriggered:{console.log("FAIL watchdog stage="+h.stage);Qt.exit(124);}}

 Component.onCompleted:{c.opened=true;c.acceptCatalogue(0,0,JSON.stringify(@FIXTURE@),"");}
}
'''.replace('@CHIP_FIXTURE@',json.dumps(chip_fixture)).replace('@CHIP_IMAGE@',str(evidence/(slug+'-'+mode+'-long-query.png'))).replace('@FIXTURE@',json.dumps(fixture)).replace('@TITLE@',json.dumps(json.loads((runtime.parent/'i18n/en.json').read_text())['title'])).replace('@CHOICES@',json.dumps(choices)).replace('@SLUG@',slug).replace('@MODE@',mode).replace('@FONT@','Noto Sans' if 'tall' in mode else 'monospace').replace('@IMAGE@',str(evidence/(slug+'-'+mode+'.png'))).replace('@CATALOG_IMAGE@',str(evidence/(slug+'-'+mode+'-catalog.png')))
            (host/'shell.qml').write_text(qml)
            command=['/usr/bin/qs','-n','-p',str(host)]
            timed_out=False
            owned_children=set()
            cleanup_complete=True
            output_incomplete=False
            cleanup_errors=[]
            prefix=evidence/(slug+'-'+mode)
            def read_stat(pid):
                try:
                    fields=Path('/proc',str(pid),'stat').read_text().rpartition(') ')[2].split()
                    return fields[0],int(fields[1]),int(fields[19])
                except (FileNotFoundError,ProcessLookupError):return None
            def save_process():
                log=stdout+stderr
                stages=[line for line in log.splitlines() if 'STAGE ' in line or 'PHASE ' in line]
                prefix.with_suffix('.stdout').write_text(stdout)
                prefix.with_suffix('.stderr').write_text(stderr)
                prefix.with_suffix('.log').write_text(log)
                prefix.with_suffix('.process.json').write_text(json.dumps({'timed_out':timed_out,'exit':process.returncode,'last_stage':stages[-1] if stages else 'before QML startup','owned_pid':process.pid,'owned_children':sorted(owned_children),'reaped':process.poll() is not None,'cleanup_complete':cleanup_complete,'output_incomplete':output_incomplete,'cleanup_errors':cleanup_errors},indent=2))
            def partial(value):
                return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            root_stat=read_stat(process.pid)
            try:
                stdout,stderr=process.communicate(timeout=16)
            except subprocess.TimeoutExpired as expired:
                timed_out=True
                cleanup_complete=False
                output_incomplete=True
                stdout,stderr=partial(expired.stdout),partial(expired.stderr)
                save_process()  # Preserve the failure before any signal, scan or wait.
                prefix.with_suffix('.timeout.json').write_text(prefix.with_suffix('.process.json').read_text())
                prefix.with_suffix('.partial.stdout').write_bytes(expired.stdout if isinstance(expired.stdout,bytes) else stdout.encode())
                prefix.with_suffix('.partial.stderr').write_bytes(expired.stderr if isinstance(expired.stderr,bytes) else stderr.encode())
                owners={process.pid:root_stat[2]} if root_stat else {}
                def signal_owned(pid,birth,sig):
                    try:
                        fd=os.pidfd_open(pid)
                        try:
                            current=read_stat(pid)
                            if current is None or current[2]!=birth:
                                raise ProcessLookupError('PID identity changed')
                            signal.pidfd_send_signal(fd,sig)
                        finally:os.close(fd)
                    except OSError as error:cleanup_errors.append(f'{pid}: {error}')
                frozen=False
                try:
                    if not owners:raise ProcessLookupError('owned root identity unavailable')
                    signal_owned(process.pid,owners[process.pid],signal.SIGSTOP)
                    deadline=time.monotonic()+1
                    previous=None
                    # Stop the discovered tree before killing parents can orphan a late fork.
                    while time.monotonic()<deadline:
                        snapshot={int(p.parent.name):read_stat(int(p.parent.name)) for p in Path('/proc').glob('[0-9]*/stat')}
                        while True:
                            children={pid:stat[2] for pid,stat in snapshot.items() if stat and pid not in owners and stat[1] in owners and snapshot.get(stat[1]) and snapshot[stat[1]][2]==owners[stat[1]]}
                            if not children:break
                            owners.update(children)
                            owned_children.update(children)
                            for pid,birth in children.items():signal_owned(pid,birth,signal.SIGSTOP)
                        stopped=all(snapshot.get(pid) and snapshot[pid][2]==birth and snapshot[pid][0] in ['T','t','Z','X'] for pid,birth in owners.items())
                        if stopped and previous==owners:
                            frozen=True;break
                        previous=dict(owners)
                        time.sleep(.01)
                    if not frozen:cleanup_errors.append('owned tree could not be frozen and verified before deadline')
                except (OSError,ValueError,IndexError) as error:cleanup_errors.append(str(error))
                for pid,birth in reversed(list(owners.items())):signal_owned(pid,birth,signal.SIGKILL)
                try:
                    stdout,stderr=process.communicate(timeout=1)
                    output_incomplete=False
                except subprocess.TimeoutExpired as drain:
                    stdout,stderr=partial(drain.stdout),partial(drain.stderr)
                    cleanup_errors.append('bounded output drain expired')
                except OSError as error:cleanup_errors.append(str(error))
                finally:
                    process.stdout.close();process.stderr.close()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:cleanup_errors.append('bounded root reap expired')
                except OSError as error:cleanup_errors.append(str(error))
                deadline=time.monotonic()+0.5
                remaining=dict(owners)
                try:
                    while remaining and time.monotonic()<deadline:
                        remaining={pid:birth for pid,birth in remaining.items() if (stat:=read_stat(pid)) and stat[2]==birth and stat[0] not in ['Z','X']}
                        if remaining:time.sleep(.01)
                except (OSError,ValueError,IndexError) as error:cleanup_errors.append(str(error))
                if remaining:cleanup_errors.append('owned processes still running: '+str(sorted(remaining)))
                cleanup_complete=frozen and not cleanup_errors and not output_incomplete and process.returncode is not None
            finally:
                process.stdout.close();process.stderr.close()
            run=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
            log=stdout+stderr
            stages=[line for line in log.splitlines() if 'STAGE ' in line or 'PHASE ' in line]
            save_process()
            okay=not timed_out and run.returncode==0 and 'PASS native-panel' in log and not any(x in log for x in ['FAIL ','ReferenceError','TypeError','Error:','Detected recursive','Binding loop'])
            if okay:
                stored=Path('/home/test/.config/omarchy/lego')/slug/'preferences.json'
                disk=json.loads(stored.read_text())
                assert disk['favorites']==[] and disk['collections']=={} and disk['recent']==[]
                assert disk['options']=={key:spec['default'] for key,spec in snapshot['settingsSchema'].items()}
                assert stored.stat().st_mode & 0o777 == 0o600
                (evidence/(slug+'-'+mode+'-readback.json')).write_text(json.dumps(disk,indent=2))
            results.append({'slug':slug,'mode':mode,'ok':okay,'exit':run.returncode,'timed_out':timed_out,'last_stage':stages[-1] if stages else 'before QML startup','disk_reset_verified':okay})
            evidence.joinpath('native-panels.json').write_text(json.dumps(results,indent=2))
            print(json.dumps(results[-1]),flush=True)
            if not okay: print(log,flush=True)
            if not cleanup_complete:raise SystemExit('native timeout cleanup incomplete; refusing further cases')
evidence.joinpath('native-panels.json').write_text(json.dumps(results,indent=2))
assert source_hashes=={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in sources}, 'runtime sources changed during native verification'
assert len(results)==5*len(manifests) and all(r['ok'] for r in results)
