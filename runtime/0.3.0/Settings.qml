// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Layouts
import qs.Ui
import qs.Commons
import qs.Commons as Commons
import "Controller.js" as Controller

Item {
    id: root
    property var schema: ({})
    property var preferences: ({options:{}})
    property bool busy: false
    property var draft: ({})
    property string error: ""
    property var invalid: ({})
    property string status: ""
    signal saveRequested(var patch)
    signal resetRequested()
    signal backRequested()
    Keys.onEscapePressed:root.backRequested()
    onPreferencesChanged: reload()
    onSchemaChanged: reload()
    function reload() {
        var next=Object.create(null);
        Object.keys(root.schema).forEach(function(k) { next[k]=root.preferences.options && root.preferences.options[k]!==undefined ? root.preferences.options[k] : root.schema[k].default; });
        root.draft=next; root.error="";root.invalid=({});
    }
    function editOption(key,value) {
        var failures=Object.assign(Object.create(null),root.invalid);
        if (!Object.prototype.hasOwnProperty.call(root.schema,key) || !Controller.validOption(value,root.schema[key])) { failures[key]=true;root.invalid=failures;root.error="Invalid value; check the option limits"; return false; }
        delete failures[key];root.invalid=failures;
        var next=Object.assign(Object.create(null),root.draft); next[key]=value; root.draft=next; root.error=Object.keys(failures).length ? "Correct the invalid fields before saving" : ""; return true;
    }
    function save() {
        if(root.busy || Object.keys(root.invalid).length>0) return;
        var keys=Object.keys(root.schema);
        if(!keys.every(function(k){return Controller.validOption(root.draft[k],root.schema[k]);})) {root.error="Invalid settings";return;}
        var patch={options:root.draft};
        if(!Controller.preferenceCommand("backend.py",patch)) {root.error="Settings exceed the 16 KiB payload limit";return;}
        root.saveRequested(patch);
    }
    function findControl(name) {
        function visit(item) {
            if(item.objectName===name) return item;
            for(var i=0;i<item.children.length;i++) {var found=visit(item.children[i]);if(found) return found;}
            return null;
        }
        return visit(root);
    }
    component Label: Text {
        textFormat: Text.PlainText
        color: Commons.Color.menu.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
        wrapMode: Text.Wrap
    }
    ColumnLayout {
        anchors.fill:parent
        spacing:Style.space(12)
        Label { text:"Configure"; font.pixelSize:Style.font.heading; font.bold:true; Layout.fillWidth:true }
        Flickable {
            objectName:"lego-settings-scroll"
            Layout.fillWidth:true
            Layout.fillHeight:true
            contentHeight:fields.implicitHeight
            clip:true
            boundsBehavior:Flickable.StopAtBounds
            Column {
                id:fields
                width:parent.width
                spacing:Style.space(12)
                Repeater {
                    model:Object.keys(root.schema)
                    delegate:Column {
                        id:field
                        required property string modelData
                        readonly property var spec:root.schema[modelData]
                        width:fields.width
                        spacing:Style.space(4)
                        Label { width:parent.width; text:field.spec.label + (field.spec.type==="integer" ? " ("+field.spec.minimum+"–"+field.spec.maximum+")" : field.spec.type==="string-list" ? " (JSON array, up to 32 strings)" : "") }
                        Loader {
                            width:parent.width
                            sourceComponent:field.spec.type==="enum" ? choice : field.spec.type==="boolean" ? flag : entry
                            Component {
                                id:choice
                                Dropdown {
                                    objectName:"option-"+field.modelData
                                    width:parent.width
                                    showLabel:false
                                    options:field.spec.choices
                                    value:root.draft[field.modelData]===undefined ? "" : root.draft[field.modelData]
                                    enabled:!root.busy
                                    onChanged:value=>root.editOption(field.modelData,value)
                                }
                            }
                            Component {
                                id:flag
                                Toggle {
                                    objectName:"option-"+field.modelData
                                    width:parent.width
                                    label:field.spec.label
                                    checked:root.draft[field.modelData]===true
                                    enabled:!root.busy
                                    onClicked:root.editOption(field.modelData,!checked)
                                }
                            }
                            Component {
                                id:entry
                                TextField {
                                    objectName:"option-"+field.modelData
                                    width:parent.width
                                    enabled:!root.busy
                                    // Native TextInput limits UTF-16 units; editOption enforces codepoints and bytes.
                                    maximumLength:field.spec.type==="string-list" ? 16384 : field.spec.type==="integer" ? 12 : 2*(field.spec.maxLength===undefined ? 4096 : field.spec.maxLength)
                                    text:field.spec.type==="string-list" ? JSON.stringify(root.draft[field.modelData]||[]) : String(root.draft[field.modelData]===undefined ? "" : root.draft[field.modelData])
                                    Accessible.name:field.spec.label
                                    onTextEdited: {
                                        var value=text;
                                        if(field.spec.type==="integer") value=/^-?[0-9]+$/.test(text) ? Number(text) : NaN;
                                        else if(field.spec.type==="string-list") { try {value=JSON.parse(text);} catch(e) {root.editOption(field.modelData,null);root.error="Enter a JSON array of strings";return;} }
                                        root.editOption(field.modelData,value);
                                    }
                                    onAccepted:root.save()
                                }
                            }
                        }
                    }
                }
                Label { width:parent.width; visible:Object.keys(root.schema).length===0; text:"No plugin-specific options. Favorites, recent items and collections are available in the catalogue." }
            }
        }
        Label { Layout.fillWidth:true; visible:root.status.length>0; text:root.status }
        Label { Layout.fillWidth:true; visible:root.error.length>0; text:root.error; color:Commons.Color.accent }
        Flow {
            Layout.fillWidth:true
            spacing:Style.space(8)
            Button { objectName:"lego-settings-save"; text:"Save settings"; enabled:!root.busy && !root.error; bordered:true; onClicked:root.save() }
            Button { objectName:"lego-settings-reset"; text:"Reset preferences"; enabled:!root.busy; bordered:true; onClicked:root.resetRequested() }
            Button { text:"Back"; onClicked:root.backRequested() }
        }
        Label { Layout.fillWidth:true; text:"Reset clears only options, favorites, recent items and collections; custom presets and recovery journals are kept."; font.pixelSize:Style.font.bodySmall; opacity:0.7 }
    }
}
