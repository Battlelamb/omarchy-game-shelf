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
    for mode,width,height in [('wide',1150,850),('compact',580,690)]:
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
            (host/'Candidate.qml').write_text(text)
            fixture={'rows':[{'id':'fixture','label':'<b>Plain long selected metadata</b> '+('A'*80),'detail':'<img src=bad> '+('Long metadata with swatches and category. '*20),'category':'Tools','provider':'Local','installed':True,'favorite':True,'swatches':['#112233','#abcdef'],'preview':'','glyph':'X','color':''}], 'actions':['apply','favorite','capture','import','export-preset','compare','restore'], 'preferences':snapshot['preferences'],'settingsSchema':snapshot['settingsSchema']}
            qml='''import QtQuick
import Quickshell
import QtTest
ShellRoot {
 id:h
 property int phase:0
 onPhaseChanged:console.log("PHASE "+h.phase)
 property int beforeLoads:0
 Candidate {id:c}
 TestCase {id:keyDriver;name:"ConfigureKeys";when:false;parent:c.testPanel.contentItem}
 function check(ok,message) {if(!ok) {console.log("FAIL "+message);Qt.exit(1);}}
 function find(item,name) {if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var result=find(item.children[i],name);if(result)return result;}return null;}
 function button(item,text) {if(item.text===text&&item.clicked!==undefined)return item;for(var i=0;i<item.children.length;i++){var result=button(item.children[i],text);if(result)return result;}return null;}
 Timer {interval:350;running:true;onTriggered:{
  var card=h.find(c.testPanel.contentItem,"lego-card"),grid=h.find(c.testPanel.contentItem,"lego-results");
  h.check(card!==null&&grid!==null,"native objects exist");
  h.check(h.find(c.testPanel.contentItem,"lego-swatches")!==null,"validated swatches are rendered");
  h.check(grid.width>=100&&grid.height>=(c.presetMode?204:65),"positive usable grid "+grid.width+"x"+grid.height);
  h.check(card.x>=0&&card.y>=0&&card.x+card.width<=c.testPanel.width+1&&card.y+card.height<=c.testPanel.height+1,"contained card");
  function installationLabel(item) {if(item.text==="All installations"&&item.visible)return item;for(var i=0;i<item.children.length;i++){var found=installationLabel(item.children[i]);if(found)return found;}return null;}
  var installation=installationLabel(c.testPanel.contentItem);
  h.check(installation!==null&&!installation.truncated,"native installation label not elided");
  console.log("GEOMETRY "+JSON.stringify({card:[card.width,card.height],grid:[grid.width,grid.height],compact:card.compact}));
  var detail=h.find(c.testPanel.contentItem,card.compact ? "lego-compact-detail" : "lego-detail");
  h.check(detail.clip&&detail.height>0&&detail.contentHeight>detail.height,"long authoritative metadata has real bounded scrolling");
  card.grabToImage(function(result){h.check(result.saveToFile("@CATALOG_IMAGE@"),"offscreen catalogue capture");c.configuring=true;inspect.restart();});
 }}
 Timer {id:inspect;interval:150;onTriggered:{
  var editor=h.find(c.testPanel.contentItem,"lego-settings");
  h.check(editor.visible&&editor.width>100&&editor.height>100,"settings page visible and contained");
  var keys=Object.keys(c.settingsSchema);
  for(var i=0;i<keys.length;i++)h.check(editor.findControl("option-"+keys[i])!==null,"actual schema control "+keys[i]);
  h.find(c.testPanel.contentItem,"lego-card").grabToImage(function(result){h.check(result.saveToFile("@IMAGE@"),"offscreen capture");console.log("LAYOUT native-panel @SLUG@ @MODE@ controls="+keys.length);writes.start();});
 }}
 Timer {id:writes;interval:90;repeat:true;onTriggered:{
  if(c.preferencesBusy)return;
  var editor=h.find(c.testPanel.contentItem,"lego-settings");
  if(h.phase===0){editor.save();h.phase=1;return;}
  if(h.phase===1){h.check(JSON.stringify(c.preferences.options)===JSON.stringify(editor.draft),"native Save acknowledged typed options");c.savePreferences({favorites:["native-@MODE@"],collections:{"Native test":["native-@MODE@"]}});h.phase=2;return;}
  if(h.phase===2){h.check(c.preferences.favorites[0]==="native-@MODE@"&&c.preferences.collections["Native test"][0]==="native-@MODE@","real preference patch acknowledged");c.view="favorites";editor.resetRequested();h.phase=3;return;}
  if(h.phase===3){
   h.check(c.preferences.favorites.length===0&&Object.keys(c.preferences.collections).length===0&&c.view==="all","native Reset acknowledged and stale view cleared");
   h.beforeLoads=c.testCatalogueLoads;editor.backRequested();h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"Back refreshes and restores catalogue focus");h.phase=4;return;
  }
  if(h.phase===4){h.beforeLoads=c.testCatalogueLoads;c.configuring=true;editor.forceActiveFocus();keyDriver.keyClick(Qt.Key_Escape);h.phase=5;return;}
  if(h.phase===5){
   h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"native editor Escape refreshes and restores catalogue focus");
   h.beforeLoads=c.testCatalogueLoads;c.configuring=true;c.testKeyboard.forceActiveFocus();keyDriver.keyClick(Qt.Key_Escape);h.phase=6;return;
  }
  if(h.phase===6){
   h.check(!c.configuring&&c.testKeyboard.activeFocus&&c.testCatalogueLoads===h.beforeLoads+1,"native catalogue Escape refreshes and restores catalogue focus");
   c.rows=[];c.actions=["import","capture"];c.organizing=true;
   h.check(h.button(c.testPanel.contentItem,"import").enabled,"native Import button enabled without selection");
   h.check(h.button(c.testPanel.contentItem,"capture").enabled===c.presetMode,"native Capture admission follows mode not stale selection");
   console.log("PASS native-panel @SLUG@ @MODE@ save-patch-reset-back-escape");c.close();Qt.exit(0);
  }
 }}
 Timer {interval:12000;running:true;onTriggered:Qt.exit(124)}
 Component.onCompleted:{c.opened=true;c.acceptCatalogue(0,0,JSON.stringify(@FIXTURE@),"");}
}
'''.replace('@FIXTURE@',json.dumps(fixture)).replace('@SLUG@',slug).replace('@MODE@',mode).replace('@IMAGE@',str(evidence/(slug+'-'+mode+'.png'))).replace('@CATALOG_IMAGE@',str(evidence/(slug+'-'+mode+'-catalog.png')))
            (host/'shell.qml').write_text(qml)
            run=subprocess.run(['/usr/bin/qs','-n','-p',str(host)],capture_output=True,text=True,timeout=16)
            log=run.stdout+run.stderr
            (evidence/(slug+'-'+mode+'.log')).write_text(log)
            okay=run.returncode==0 and 'PASS native-panel' in log and not any(x in log for x in ['FAIL ','ReferenceError','TypeError','Error:','Detected recursive','Binding loop'])
            if okay:
                stored=Path('/home/test/.config/omarchy/lego')/slug/'preferences.json'
                disk=json.loads(stored.read_text())
                assert disk['favorites']==[] and disk['collections']=={} and disk['recent']==[]
                assert disk['options']=={key:spec['default'] for key,spec in snapshot['settingsSchema'].items()}
                assert stored.stat().st_mode & 0o777 == 0o600
                (evidence/(slug+'-'+mode+'-readback.json')).write_text(json.dumps(disk,indent=2))
            results.append({'slug':slug,'mode':mode,'ok':okay,'exit':run.returncode,'disk_reset_verified':okay})
            print(json.dumps(results[-1]),flush=True)
            if not okay: print(log,flush=True)
evidence.joinpath('native-panels.json').write_text(json.dumps(results,indent=2))
assert source_hashes=={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in sources}, 'runtime sources changed during native verification'
assert len(results)==2*len(manifests) and all(r['ok'] for r in results)
