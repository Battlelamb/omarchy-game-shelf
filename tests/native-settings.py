"""Installed Qt offscreen native schema editing; called through run-shared.py."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

from shared_paths import RUNTIME
assert (RUNTIME/'Settings.qml').is_file(), 'Native Settings editor must exist'
with tempfile.TemporaryDirectory() as tmp:
    host = Path(tmp)
    for name in ['Ui', 'Commons', 'services', 'plugins']:
        (host/name).symlink_to('/usr/share/omarchy/shell/'+name)
    for name in ['Settings.qml', 'Controller.js']:
        shutil.copy2(RUNTIME/name, host/name)
    qml = '''import QtQuick
import Quickshell
import QtTest
import "Controller.js" as Controller
ShellRoot {
 id: h
 property var captured: null
 function check(ok,message) { if(!ok) {console.log("FAIL "+message);Qt.exit(1);} }
 FloatingWindow {
  id:window;visible:true; implicitWidth:640; implicitHeight:360
  Settings {
   id: editor; anchors.fill:parent
   schema: ({choice:{type:"enum",default:"a",choices:["a","b"],label:"Choice"}, count:{type:"integer",default:4,minimum:2,maximum:8,label:"Count"}, enabled:{type:"boolean",default:false,label:"Enabled"}, name:{type:"string",default:"",maxLength:32,label:"Name"}, folders:{type:"string-list",default:[],label:"Folders"}})
   preferences: ({version:1,favorites:[],recent:[],collections:{},options:{choice:"a",count:4,enabled:false,name:"",folders:[]}})
   onSaveRequested: patch => h.captured=patch
  }
 }
 TestCase {id:keys;name:"SettingsTab";when:false;parent:window.contentItem}
 property int tabs:0
 property bool reachedFolders:false
 Timer {id:focusWalk;interval:60;repeat:true;onTriggered:{
  var focused=window.contentItem.Window.window.activeFocusItem,control=focused;
  console.log("TAB_FOCUS "+(focused?focused.objectName:"none"));
  while(control&&control!==editor&&control.objectName.indexOf("option-")!==0)control=control.parent;
  if(control&&control!==editor){
   var scroll=editor.findControl("lego-settings-scroll"),y=control.mapToItem(scroll,0,0).y;
   h.check(y>=-0.1&&y+control.height<=scroll.height+0.1,"keyboard-focused native option scrolls fully into view "+control.objectName);
   if(control.objectName==="option-folders")h.reachedFolders=true;
  }
  if(++h.tabs>=16){h.check(h.reachedFolders,"sources remain keyboard reachable");console.log("PASS native-schema-controls 5 types and compact keyboard scroll");Qt.exit(0);return;}
  keys.keyClick(Qt.Key_Tab);
 }}
 Timer { interval:300; running:true; onTriggered: {
  function countLabels(item){var n=item.text==="Enabled"&&item.visible?1:0;for(var i=0;i<item.children.length;i++)n+=countLabels(item.children[i]);return n;}
  h.check(countLabels(editor)===1,"boolean has one readable label, not duplicate headings");
  h.check(editor.dirty===false && !editor.findControl("lego-settings-save").enabled,"unchanged settings clearly saved and Save disabled");
  h.check(editor.findControl("lego-settings-state").text==="Saved settings","explicit saved state");
  h.check(Controller.preferenceText("😀".repeat(256),256),"QV4 accepts 256 codepoints not UTF16 units");
  h.check(!Controller.preferenceText("😀".repeat(257),256),"QV4 rejects 257 codepoints");
  h.check(!Controller.preferenceText(String.fromCharCode(0xD800),256),"QV4 rejects lone surrogate");
  h.check(!Controller.preferenceText("界".repeat(1366),4096),"QV4 retains UTF8 byte cap");
  h.check(!Controller.preferenceText("x"+String.fromCharCode(0x85),256),"QV4 rejects C1 control");
  h.check(editor.editOption("count",99)===false,"reject invalid integer");
  h.check(editor.editOption("name","valid"),"other field still editable");
  editor.save();h.check(h.captured===null,"invalid field cannot be hidden by editing another field");
  h.check(editor.editOption("count",6),"edit integer");
  h.check(editor.editOption("choice","b"),"edit enum");
  h.check(editor.editOption("enabled",true),"edit boolean");
  h.check(editor.editOption("name","<b>plain</b>"),"edit string");
  h.check(editor.editOption("folders",["/home/test/Pictures"]),"edit list");
  editor.save();
  h.check(h.captured&&h.captured.options.count===6&&h.captured.options.enabled===true&&h.captured.options.folders.length===1,"native saved typed patch");
  h.check(editor.findControl("option-count")!==null,"integer control instantiated");
  var count=editor.findControl("option-count");count.text="7";count.textEdited();
  var list=editor.findControl("option-folders");list.text='["/home/test/Art"]';list.textEdited();
  editor.findControl("option-enabled").clicked();
  editor.findControl("option-choice").changed("a");
  var name=editor.findControl("option-name");name.text="native input";name.textEdited();
  editor.save();
  h.check(h.captured.options.count===7&&h.captured.options.enabled===false&&h.captured.options.choice==="a"&&h.captured.options.name==="native input"&&h.captured.options.folders[0]==="/home/test/Art","actual native control edit signals produce typed saved options");
  name.text="😀".repeat(32);name.textEdited();editor.save();
  h.check(h.captured.options.name==="😀".repeat(32),"native text field admits full codepoint budget");
  editor.sourcesExpanded=true;editor.findControl("option-count").forceActiveFocus();focusWalk.start();
 } }
 Timer {interval:8000;running:true;onTriggered:Qt.exit(124)}
}
'''
    (host/'shell.qml').write_text(qml)
    Path('/tmp/runtime').mkdir(mode=0o700,exist_ok=True)
    result=subprocess.run(['/usr/bin/qs','-n','-p',str(host)],capture_output=True,text=True,timeout=12)
    log=result.stdout+result.stderr
    print(log)
    assert result.returncode==0 and 'PASS native-schema-controls' in log
    assert not any(x in log for x in ['FAIL ', 'ReferenceError', 'TypeError', 'Error:', 'Detected recursive'])
