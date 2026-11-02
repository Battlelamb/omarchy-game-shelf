// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Ui
import qs.Commons
import qs.Commons as Commons
import "Controller.js" as Controller

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property bool opening: false
    property int generation: 0
    property int catalogueGeneration: 0
    property int actionGeneration: 0
    property bool actionBusy: false
    property string query: ""
    property int selected: 0
    property var rows: []
    property var actions: []
    property string message: ""
    property var preferences: ({version:1,favorites:[],recent:[],collections:{},options:{}})
    property var settingsSchema: ({})
    property bool configuring: false
    property bool organizing: false
    property bool previewing: false
    property string actionPreview: ""
    property string view: "all"
    property bool resetViewPending: false
    property string categoryFilter: ""
    property string providerFilter: ""
    property string installedFilter: ""
    property string actionData: ""
    property string captureName: ""
    property string actionDetail: ""
    readonly property bool preferencesBusy: root.actionBusy || action.running || catalogue.running || lockProbe.running
    function fieldOptions(field) {
        var values=[];
        root.rows.forEach(function(r){if(r[field] && values.indexOf(r[field])<0) values.push(r[field]);});
        return [{value:"",label:field==="category" ? "All categories" : "All "+field+"s"}].concat(values.sort());
    }
    readonly property var viewOptions: [{value:"all",label:"All items"},{value:"favorites",label:"Favorites"},{value:"recent",label:"Recent"}].concat(Object.keys(root.preferences.collections).map(function(n){return {value:"collection:"+n,label:n};}))
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
    readonly property bool glyphMode: false
    readonly property bool presetMode: false
    readonly property bool dense: root.preferences.options.density === "compact"
    readonly property bool listMode: root.preferences.options.layout === "list" || root.preferences.options.layout !== "grid" && root.presetMode
    FontMetrics { id: rowMetrics; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body }
    FontMetrics { id: smallMetrics; font.family: Style.font.menuFamily; font.pixelSize: Style.font.bodySmall }
    property string selectedId: ""
    readonly property var matches: Controller.viewRows(root.rows, root.query, root.preferences, root.view, root.categoryFilter, root.providerFilter, root.installedFilter)
    readonly property var selectedRow: selected >= 0 && selected < matches.length ? matches[selected] : null
    readonly property string primaryVerb: Controller.primaryVerb(actions, root.settingsSchema.primaryAction ? root.preferences.options : null)
    onSelectedChanged: if (root.selected >= 0 && root.selected < root.matches.length) root.selectedId = root.matches[root.selected].id
    onMatchesChanged: {
        root.reconcileSelection();
        Qt.callLater(function() { if (root.opened) grid.positionViewAtIndex(root.selected, GridView.Contain); });
    }
    function featureRevision() { return '0.4.0'; }
    function clearFilters() {
        root.query="";root.categoryFilter="";root.providerFilter="";root.installedFilter="";root.selected=0;
        keyboard.forceActiveFocus();
    }
    function reconcileSelection() {
        var index=root.matches.findIndex(function(row){return row.id===root.selectedId;});
        root.selected=index>=0 ? index : Math.max(0,Math.min(root.selected,root.matches.length-1));
        root.selectedId=root.matches.length ? root.matches[root.selected].id : "";
    }

    function setView(value) {
        root.view=value;root.selected=0;
        var options=Object.create(null);
        if(root.settingsSchema.view) options.view=value.indexOf("collection:")===0 ? "all" : value;
        if(root.settingsSchema.collection) options.collection=value.indexOf("collection:")===0 ? value.slice(11) : "";
        if(Object.keys(options).length) root.savePreferences({options:options});
    }
    function savePreferences(patch) {
        if (!root.opened || root.opening || root.actionBusy || action.running || catalogue.running || lockProbe.running) return;
        var command=Controller.preferenceCommand(backendPath,patch);
        if(!command) {root.message="Invalid preference patch or payload exceeds 16 KiB";return;}
        root.resetViewPending=patch.reset===true;
        root.actionBusy=true;root.actionGeneration=root.generation;root.message="";
        action.command=command;action.start();
    }
    function collectionChange(name,remove) {
        if(!Controller.preferenceText(name,256)||!name) {root.message="Enter a collection name";return;}
        var groups=Object.assign(Object.create(null),root.preferences.collections);
        if(remove) delete groups[name];
        else {
            if(!root.selectedRow) return;
            var ids=(groups[name]||[]).slice();
            var index=ids.indexOf(root.selectedRow.id);
            if(index>=0) ids.splice(index,1);else ids.push(root.selectedRow.id);
            groups[name]=ids;
        }
        root.savePreferences({collections:groups});
    }
    function open(payloadJson) {
        if (root.opened || root.opening) return;
        root.configuring=false;root.organizing=false;root.previewing=false;root.actionPreview=""; root.actionDetail=""; root.view="all"; root.categoryFilter="";root.providerFilter="";root.installedFilter="";root.actionData="";root.captureName="";
        root.generation++; root.query = ""; root.selected = 0; root.rows = []; root.actions = []; root.message = "";
        root.opening = true; root.attemptAdmission();
    }
    function attemptAdmission() {
        if (root.opening && !root.opened && !lockProbe.running && !catalogue.running && !action.running) lockProbe.start();
    }
    function close() {
        root.generation++; root.opening = false; root.opened = false;
        root.rows = []; root.actions = []; root.query = ""; root.selected = 0; root.message = "";
        root.configuring=false;root.organizing=false;root.previewing=false;
        root.actionPreview="";root.actionDetail="";root.actionData="";root.captureName="";
        root.actionBusy = false;root.resetViewPending=false;
        lockProbe.cancel(); catalogue.cancel(); action.cancel();
    }
    function dismiss() {
        root.close();
        if (root.shell && root.manifest) root.shell.hide(root.manifest.id);
    }
    function toggle() { if (root.opened || root.opening) root.dismiss(); else root.open("{}"); }
    function admit(code, status, text, error) {
        if (!root.opening && !root.opened) return;
        if (error || code !== 1 || status !== 0) { root.dismiss(); return; }
        if (root.opening) {
            root.opening = false; root.opened = true; root.loadCatalogue();
            Qt.callLater(function() { if (root.opened) keyboard.forceActiveFocus(); });
        }
    }
    function loadCatalogue() {
        if (!root.opened || catalogue.running || root.actionBusy) return;
        root.catalogueGeneration = root.generation;
        catalogue.start();
    }
    function leaveConfigure() {
        root.configuring=false;
        root.loadCatalogue();
        keyboard.forceActiveFocus();
    }
    function syncView() {
        var options=root.preferences.options;
        if(options.collection) root.view="collection:"+options.collection;
        else if(options.view!==undefined || options.collection!==undefined || root.resetViewPending) root.view=options.view || "all";
        root.resetViewPending=false;
    }
    function acceptCatalogue(code, status, text, error) {
        if (!root.opened || root.catalogueGeneration !== root.generation) return;
        if (error || status !== 0) { root.rows = []; root.actions = []; root.message = strings.t("loadFailed"); return; }
        var data = Controller.catalog(text);
        root.rows = code === 0 ? data.rows : []; root.actions = code === 0 ? data.actions : [];
        if(code===0) {
            root.preferences=data.preferences || {version:1,favorites:[],recent:[],collections:{},options:{}};
            root.settingsSchema=data.settingsSchema || {};
            root.syncView();
        }
        root.message = data.message || (code !== 0 ? strings.t("loadFailed") : "");
    }
    function selectionIndependent(verb) {
        return verb==="restore" || verb==="import" || (verb==="capture" && root.presetMode);
    }
    function activate(verb, payload) {
        if (!root.opened || root.opening || root.actionBusy || action.running || catalogue.running || lockProbe.running || root.actions.indexOf(verb) < 0) return;
        if (!root.selectionIndependent(verb) && (root.selected < 0 || root.selected >= root.matches.length)) return;
        var id = verb === "restore" ? "restore:last" : verb === "import" ? "import:preset" : verb === "capture" && root.presetMode ? "capture:current" : root.matches[root.selected].id;
        var encoded="";
        if(payload!==undefined) {
            if(!Controller.plainObject(payload)) {root.message="Action data must be a JSON object";return;}
            try {encoded=JSON.stringify(payload);} catch(e) {root.message="Invalid action data";return;}
            if(Controller.utf8Bytes(encoded)>16384) {root.message="Action data exceeds 16 KiB";return;}
        }
        root.actionBusy = true; root.actionGeneration = root.generation; root.message = "";
        action.command = ["/usr/bin/python3", backendPath, "action", "--id", id, "--verb", verb, "--apply"];
        if(encoded) action.command=action.command.concat(["--payload",encoded]);
        action.start();
    }
    function activateSecondary(verb) {
        var payload;
        if(["capture","import","copy-color"].indexOf(verb)>=0 && root.actionData) {try {payload=JSON.parse(root.actionData);} catch(e) {root.message="Invalid action JSON";return;}}
        if(verb==="capture") {
            if(payload===undefined) payload={};
            if(!Controller.plainObject(payload)) {root.message="Action data must be a JSON object";return;}
            payload.name=root.captureName;
        }
        root.activate(verb,payload);
    }
    function acceptAction(code, status, text, error) {
        if (!root.opened || root.actionGeneration !== root.generation) return;
        root.actionBusy = false;
        var result = Controller.actionResult(text, code, status, error);
        if(!result.ok) root.resetViewPending=false;
        root.message = result.message;
        root.actionDetail=result.detail || "";
        if(result.preferences) {root.preferences=result.preferences;root.syncView();}
        if(result.settingsSchema) root.settingsSchema=result.settingsSchema;
        if (result.ok) {
            if(result.preview) {root.actionPreview=result.preview;root.previewing=true;return;}
            if(result.selectedId) {
                root.query="";root.view="all";root.categoryFilter="";root.providerFilter="";root.installedFilter="";
                var index=root.matches.findIndex(function(r){return r.id===result.selectedId;});
                if(index>=0) root.selected=index;
                else root.message="Selected wallpaper is outside this catalogue snapshot; refresh before applying";
                return;
            }
            if (result.actions !== undefined) root.actions = result.actions;
            else if(!root.configuring) root.loadCatalogue();
        }
    }
    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    Timer { interval: 50; repeat: true; running: root.opening; onTriggered: root.attemptAdmission() }
    Timer { interval: 250; repeat: true; running: root.opened; onTriggered: if (!lockProbe.running) lockProbe.start() }
    BoundedProcess {
        id: lockProbe
        command: ["/usr/bin/omarchy-hyprland-session-locked"]
        byteLimit: 1024
        deadlineSeconds: 2
        onCompleted: (code, status, text, error) => root.admit(code, status, text, error)
    }
    BoundedProcess {
        id: catalogue
        command: ["/usr/bin/python3", root.backendPath, "catalog"]
        deadlineSeconds: 15
        onCompleted: (code, status, text, error) => root.acceptCatalogue(code, status, text, error)
    }
    BoundedProcess {
        id: action
        byteLimit: 1048576
        deadlineSeconds: 30
        onCompleted: (code, status, text, error) => root.acceptAction(code, status, text, error)
    }
    component Swatches: Flow {
        objectName:"lego-swatches"
        property var colors:root.selectedRow && root.selectedRow.swatches ? root.selectedRow.swatches : []
        visible:colors.length>0
        spacing:Style.space(4)
        Repeater {
            model:colors
            delegate:Rectangle {
                required property string modelData
                required property int index
                width:Style.space(32);height:Style.space(24)
                color:modelData
                border.width:activeFocus?2:1
                border.color:activeFocus?Commons.Color.accent:Commons.Color.menu.border
                radius:Style.cornerRadius
                activeFocusOnTab:root.actions.indexOf("copy-color")>=0
                Accessible.role:Accessible.Button
                Accessible.name:"Copy color "+modelData
                function copyColor() { if(root.actions.indexOf("copy-color")>=0) root.activate("copy-color",{index:index}); }
                Keys.onReturnPressed:copyColor()
                Keys.onSpacePressed:copyColor()
                MouseArea {anchors.fill:parent;onClicked:parent.copyColor()}
            }
        }
    }
    component Label: Text {
        textFormat: Text.PlainText
        color: Commons.Color.menu.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
        horizontalAlignment: Commons.I18n.rightToLeft ? Text.AlignRight : Text.AlignLeft
    }
    OverlayWindow {
        id: panel
        shown: root.opened
        WlrLayershell.namespace: "leviathan-game-shelf"
        onTargetScreenChanged: if (root.opened && !targetScreen) root.dismiss()
        Rectangle { anchors.fill: parent; color: Commons.Color.menu.scrim }
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
        Rectangle {
            id: card
            objectName: "lego-card"
            anchors.centerIn: parent
            width: Math.max(1, Math.min(Style.space(root.presetMode ? 680 : 1000), panel.width - Style.space(32)))
            height: Math.max(1, Math.min(root.presetMode ? Math.max(Style.space(520), rowMetrics.height * 24) : Style.space(650), panel.height - Style.space(32)))
            readonly property bool compact: width < Style.space(760) || height < Style.space(440)
            color: Commons.Color.menu.background
            border.color: Commons.Color.menu.border
            border.width: 1
            radius: Style.cornerRadius
            LayoutMirroring.enabled: Commons.I18n.rightToLeft
            LayoutMirroring.childrenInherit: true
            MouseArea { anchors.fill: parent; onClicked: {} }
            Item {
                id: keyboard
                anchors.fill: parent
                focus: true
                Keys.onPressed: function(event) {
                    if ((root.configuring || root.previewing) && event.key !== Qt.Key_Escape) return;
                    if (event.key === Qt.Key_Escape) { if(root.configuring) root.leaveConfigure(); else if(root.previewing) root.previewing=false; else root.dismiss(); }
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) root.activate(root.primaryVerb);
                    else if (event.key === Qt.Key_Down && root.matches.length) root.selected = Controller.step(root.selected, grid.columns, root.matches.length);
                    else if (event.key === Qt.Key_Up && root.matches.length) root.selected = Controller.step(root.selected, -grid.columns, root.matches.length);
                    else if (event.key === Qt.Key_Right && root.matches.length) root.selected = Controller.step(root.selected, Commons.I18n.rightToLeft ? -1 : 1, root.matches.length);
                    else if (event.key === Qt.Key_Left && root.matches.length) root.selected = Controller.step(root.selected, Commons.I18n.rightToLeft ? 1 : -1, root.matches.length);
                    else if (event.key === Qt.Key_Home) root.selected = 0;
                    else if (event.key === Qt.Key_End) root.selected = Math.max(0, root.matches.length - 1);
                    else if (Util.editsFilter(event, root.query)) { root.query = Util.editedFilter(event, root.query).slice(0, 128); root.selected = 0; }
                    else if (event.text && event.text.length && event.text.charCodeAt(0) >= 32 && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) { root.query = (root.query + event.text).slice(0, 128); root.selected = 0; }
                    else return;
                    grid.positionViewAtIndex(root.selected, GridView.Contain);
                    event.accepted = true;
                }
            }
            ColumnLayout {
                anchors.fill:parent
                anchors.margins:Style.space(20)
                visible:root.previewing
                Label { text:"Local reference comparison"; font.pixelSize:Style.font.heading; Layout.fillWidth:true }
                Image { objectName:"lego-comparison"; Layout.fillWidth:true; Layout.fillHeight:true; source:root.previewing ? Controller.imageUrl(root.actionPreview) : ""; fillMode:Image.PreserveAspectFit; asynchronous:true; sourceSize.width:1024; sourceSize.height:768 }
                Label { text:root.actionDetail; Layout.fillWidth:true; wrapMode:Text.Wrap; elide:Text.ElideNone }
                Button { focusable:true; text:"Back"; onClicked:{root.previewing=false;keyboard.forceActiveFocus();} }
            }
            Settings {
                objectName:"lego-settings"
                anchors.fill:parent
                anchors.margins:Style.space(20)
                visible:root.configuring
                schema:root.settingsSchema
                preferences:root.preferences
                busy:root.preferencesBusy
                status:root.message
                onSaveRequested:patch=>root.savePreferences(patch)
                onResetRequested:root.savePreferences({reset:true})
                onBackRequested:root.leaveConfigure()

            }
            ColumnLayout {
                visible:!root.configuring && !root.previewing
                anchors.fill: parent
                anchors.margins: card.compact ? Style.space(12) : Style.space(20)
                spacing: card.compact ? Style.space(8) : Style.space(12)
                RowLayout {
                    objectName: "lego-toolbar"
                    Layout.fillWidth: true
                    spacing: Style.space(12)
                    Rectangle {
                        Layout.preferredWidth: Style.space(32)
                        Layout.preferredHeight: Style.space(32)
                        radius: Style.cornerRadius
                        color: Commons.Color.menu.selectedBackground
                        Label { anchors.centerIn: parent; text: "♟"; font.pixelSize: Style.space(22); color: Commons.Color.accent }
                    }
                    Label { text: strings.t("title"); font.pixelSize: Style.font.heading; font.bold: true; Layout.fillWidth: true }
                    Label { visible:!card.compact; text: strings.tn("results", root.matches.length).arg(Commons.I18n.formatNumber(root.matches.length)); opacity: 0.65; font.pixelSize: Style.font.bodySmall }
                    Button { focusable:true; visible:!card.compact; text:strings.t("explore"); selected:true; onClicked:keyboard.forceActiveFocus() }
                    Button { focusable:true; objectName:"lego-configure"; text:strings.t("configure"); bordered:true; onClicked:root.configuring=true }
                }
                Rectangle {
                    objectName: "lego-search"
                    Layout.fillWidth: true
                    implicitHeight: Style.space(36)
                    radius: Style.cornerRadius
                    color: Commons.Color.menu.selectedBackground
                    border.color: keyboard.activeFocus ? Commons.Color.accent : Commons.Color.menu.border
                    border.width: keyboard.activeFocus ? 2 : 1
                    Accessible.role: Accessible.EditableText
                    Accessible.name: strings.t("search")
                    Accessible.description: root.query
                    MouseArea { anchors.fill: parent; onClicked: keyboard.forceActiveFocus() }
                    Label { id: searchIcon; anchors.left: parent.left; anchors.leftMargin: Style.space(14); anchors.verticalCenter: parent.verticalCenter; text: "⌕"; font.pixelSize: Style.space(22); opacity: 0.7 }
                    Label { anchors.left: searchIcon.right; anchors.right: clear.left; anchors.margins: Style.space(12); anchors.verticalCenter: parent.verticalCenter; text: root.query || strings.t("search"); opacity: root.query ? 1 : 0.65 }
                    Button { focusable:true; id: clear; anchors.right: parent.right; anchors.rightMargin: Style.space(4); anchors.verticalCenter: parent.verticalCenter; text: "×"; Accessible.name: strings.t("clearSearch"); visible: root.query.length > 0; onClicked: { root.query = ""; root.selected = 0; keyboard.forceActiveFocus(); } }
                }
                Flow {
                    Layout.fillWidth:true
                    spacing:Style.space(6)
                    Dropdown { width:Style.space(145); showLabel:false; options:root.viewOptions; value:root.view; enabled:!root.preferencesBusy; onChanged:value=>root.setView(value) }
                    Dropdown { width:Style.space(145); showLabel:false; options:root.fieldOptions("category"); value:root.categoryFilter; visible:options.length>1; onChanged:value=>root.categoryFilter=value }
                    Dropdown { width:Style.space(145); showLabel:false; options:root.fieldOptions("provider"); value:root.providerFilter; visible:options.length>1; onChanged:value=>root.providerFilter=value }
                    Dropdown { width:Style.spacing.dropdownWidth; showLabel:false; options:[{value:"",label:"All installations"},{value:"installed",label:"Installed"},{value:"uninstalled",label:"Not installed"}]; value:root.installedFilter; visible:root.rows.some(function(r){return r.installed!==undefined;}); onChanged:value=>root.installedFilter=value }
                }
                Flow {
                    objectName:"lego-filter-chips"
                    Layout.fillWidth:true
                    spacing:Style.space(6)
                    visible:root.query.length>0 || root.categoryFilter.length>0 || root.providerFilter.length>0 || root.installedFilter.length>0
                    Button { width:Math.min(implicitWidth,parent.width); focusable:true; visible:root.query.length>0; text:"Search: "+root.query+" ×"; bordered:true; onClicked:{root.query="";keyboard.forceActiveFocus();} }
                    Button { width:Math.min(implicitWidth,parent.width); focusable:true; visible:root.categoryFilter.length>0; text:root.categoryFilter+" ×"; bordered:true; onClicked:root.categoryFilter="" }
                    Button { width:Math.min(implicitWidth,parent.width); focusable:true; visible:root.providerFilter.length>0; text:root.providerFilter+" ×"; bordered:true; onClicked:root.providerFilter="" }
                    Button { width:Math.min(implicitWidth,parent.width); focusable:true; visible:root.installedFilter.length>0; text:root.installedFilter+" ×"; bordered:true; onClicked:root.installedFilter="" }
                    Button { focusable:true; text:"Clear filters"; onClicked:root.clearFilters() }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Style.space(16)
                    GridView {
                        id: grid
                        objectName: "lego-results"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        readonly property int columns: root.listMode ? 1 : Math.max(1, Math.floor(width / Style.space(root.glyphMode ? 104 : 176)))
                        cellWidth: width / columns
                        cellHeight: root.listMode ? Math.max(Style.space(root.dense ? 60 : 76), rowMetrics.height + smallMetrics.height + Style.space(root.dense ? 20 : 32)) : Style.space(root.glyphMode ? (root.dense ? 88 : 104) : (root.dense ? 136 : 156))
                        cacheBuffer: 0
                        model: root.matches
                        delegate: Rectangle {
                            objectName: "lego-result"
                            required property var modelData
                            required property int index
                            width: grid.cellWidth - Style.space(8)
                            height: grid.cellHeight - Style.space(8)
                            radius: Style.cornerRadius
                            color: index === root.selected ? Commons.Color.menu.selectedBackground : tileMouse.containsMouse ? Style.hoverFillFor(Commons.Color.menu.text, Commons.Color.accent) : "transparent"
                            border.width: index === root.selected ? 2 : 1
                            border.color: index === root.selected ? Commons.Color.accent : "transparent"
                            Accessible.role: Accessible.ListItem
                            Accessible.name: modelData.label
                            Accessible.selected: index === root.selected
                            Column {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: root.listMode ? undefined : parent.top
                                anchors.bottom: root.listMode ? undefined : parent.bottom
                                anchors.verticalCenter: root.listMode ? parent.verticalCenter : undefined
                                anchors.margins: root.listMode ? Style.space(root.dense ? 8 : 14) : Style.space(8)
                                spacing: Style.space(4)
                                Rectangle {
                                    visible: !root.listMode
                                    width: parent.width
                                    height: Math.max(Style.space(34), parent.height - labels.implicitHeight - Style.space(8))
                                    color: modelData.color || Commons.Color.menu.selectedBackground
                                    radius: Style.cornerRadius
                                    Image { id: thumbImage; anchors.fill: parent; source: root.presetMode ? "" : Controller.imageUrl(modelData.preview); fillMode: Image.PreserveAspectFit; asynchronous: true; sourceSize.width: 320; sourceSize.height: 180 }
                                    Label { anchors.centerIn: parent; visible: !modelData.color && thumbImage.status !== Image.Ready; text: modelData.glyph || "♟"; font.pixelSize: Style.space(root.glyphMode ? 32 : 28); opacity: modelData.glyph ? 1 : 0.55 }
                                }
                                Column {
                                    id: labels
                                    width: parent.width
                                    Label { width: parent.width; text: modelData.label; font.pixelSize: root.listMode ? Style.font.body : Style.font.bodySmall; font.bold: root.listMode }
                                    Label { width: parent.width; visible: !root.glyphMode; text: modelData.detail; font.pixelSize: Style.font.bodySmall; opacity: 0.6 }
                                }
                            }
                            MouseArea { id: tileMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { root.selected = index; keyboard.forceActiveFocus(); } }
                        }
                        Label { anchors.centerIn: parent; visible: root.matches.length === 0; width: parent.width; text: catalogue.running ? strings.t("loading") : strings.t("empty"); horizontalAlignment: Text.AlignHCenter }
                    }
                    ColumnLayout {
                        visible: !card.compact && root.selectedRow !== null
                        Layout.preferredWidth: Style.space(320)
                        Layout.minimumWidth: 0
                        Layout.maximumWidth: Style.space(320)
                        Layout.fillWidth: false
                        Layout.fillHeight: true
                        Rectangle {
                            visible: !root.presetMode
                            Layout.fillWidth: true
                            Layout.preferredHeight: Style.space(root.glyphMode ? 170 : 210)
                            Layout.maximumHeight: Style.space(210)
                            radius: Style.cornerRadius
                            color: root.selectedRow && root.selectedRow.color ? root.selectedRow.color : Commons.Color.menu.selectedBackground
                            Image { id: detailImage; anchors.fill: parent; anchors.margins: Style.space(12); source: !card.compact && root.selectedRow ? Controller.imageUrl(root.selectedRow.preview) : ""; fillMode: Image.PreserveAspectFit; asynchronous: true; sourceSize.width: 640; sourceSize.height: 640 }
                            Label { anchors.centerIn: parent; text: root.selectedRow ? root.selectedRow.glyph || "♟" : ""; visible: root.selectedRow && !root.selectedRow.color && detailImage.status !== Image.Ready; font.pixelSize: Style.space(root.glyphMode ? 72 : 40); opacity: root.glyphMode ? 1 : 0.55 }
                        }
                        Label { Layout.fillWidth: true; text: strings.t("details"); font.pixelSize: Style.font.bodySmall; color: Commons.Color.accent }
                        Flickable {
                            objectName: "lego-detail"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: detailTitle.implicitHeight + rowMetrics.height + wideSwatches.implicitHeight + Style.space(16)
                            clip: true
                            contentHeight: detailLabels.implicitHeight
                            boundsBehavior: Flickable.StopAtBounds
                            Column {
                                id: detailLabels
                                width: parent.width
                                spacing: Style.space(8)
                                Swatches { id: wideSwatches; width:parent.width }
                                Label { id: detailTitle; width: parent.width; text: root.selectedRow ? root.selectedRow.label : ""; font.pixelSize: Style.font.title; font.bold: true; wrapMode: Text.Wrap; elide: Text.ElideNone }
                                Label { width: parent.width; text: root.selectedRow ? root.selectedRow.detail : ""; wrapMode: Text.Wrap; elide: Text.ElideNone; opacity: 0.75 }
                            }
                        }
                    }
                }
                Flickable {
                    objectName: "lego-compact-detail"
                    visible: card.compact && root.selectedRow !== null
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(Style.space(240), compactTitle.implicitHeight + smallMetrics.height + compactSwatches.implicitHeight + Style.space(12))
                    Layout.minimumHeight: Layout.preferredHeight
                    clip: true
                    contentHeight: compactLabels.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: compactLabels
                        width: parent.width
                        topPadding: Style.space(4)
                        spacing: Style.space(2)
                        Swatches { id: compactSwatches; width:parent.width }
                        Label { id: compactTitle; width: parent.width; text: root.selectedRow ? root.selectedRow.label : ""; font.bold: true; wrapMode: Text.Wrap; elide: Text.ElideNone }
                        Label { width: parent.width; text: root.selectedRow ? root.selectedRow.detail : ""; font.pixelSize: Style.font.bodySmall; wrapMode: Text.Wrap; elide: Text.ElideNone; opacity: 0.75 }
                    }
                    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Commons.Color.menu.border; opacity: 0.25 }
                }
                Flickable {
                    visible:root.actionDetail.length>0
                    Layout.fillWidth:true
                    Layout.preferredHeight:Style.space(90)
                    contentHeight:resultDetail.implicitHeight
                    clip:true
                    TextEdit { id:resultDetail; width:parent.width; text:root.actionDetail; textFormat:TextEdit.PlainText; readOnly:true; selectByMouse:true; wrapMode:TextEdit.Wrap; color:Commons.Color.menu.text; font.family:Style.font.menuFamily; font.pixelSize:Style.font.bodySmall }
                }
                Label { Layout.fillWidth: true; text: root.message; visible: text.length > 0; wrapMode: Text.Wrap; elide: Text.ElideNone; font.pixelSize: Style.font.bodySmall }
                Flow {
                    Layout.fillWidth: true
                    spacing: Style.space(8)
                    Button { focusable:true; objectName: "lego-primary"; text: strings.t(root.primaryVerb || "select"); enabled: root.selectedRow !== null && !!root.primaryVerb && !root.actionBusy && !catalogue.running; active: true; foreground: Commons.Color.accent; bordered: true; onClicked: root.activate(root.primaryVerb) }
                    Button { focusable:true; text: strings.t("restore"); visible: root.actions.indexOf("restore") >= 0; enabled: !root.actionBusy && !catalogue.running && !action.running && !lockProbe.running; bordered: true; onClicked: root.activate("restore") }
                    Button { focusable:true; text: strings.t("confirm"); visible: root.actions.indexOf("confirm") >= 0; enabled: !root.actionBusy && root.selectedRow !== null; bordered: true; onClicked: root.activate("confirm") }
                    Button { focusable:true; text:root.organizing ? "Less" : "More"; onClicked:root.organizing=!root.organizing }

                    Button { focusable:true; text: strings.t("refresh"); enabled: !root.actionBusy && !catalogue.running; onClicked: root.loadCatalogue() }
                    Label { visible: !card.compact; text: root.actionBusy ? strings.t("working") : strings.t("keys"); font.pixelSize: Style.font.bodySmall; opacity: 0.6; height: Style.space(32); verticalAlignment: Text.AlignVCenter }
                }
                ColumnLayout {
                    visible:root.organizing
                    Layout.fillWidth:true
                    spacing:Style.space(8)
                Flow {
                    Layout.fillWidth:true
                    spacing:Style.space(6)
                    Button { focusable:true; text:root.selectedRow && root.preferences.favorites.indexOf(root.selectedRow.id)>=0 ? "★ Unfavorite" : "☆ Favorite"; visible:root.actions.indexOf("favorite")>=0; enabled:!root.preferencesBusy && root.selectedRow!==null; onClicked:root.activate("favorite") }
                    Repeater {
                        model:root.actions.filter(function(a){return [root.primaryVerb,"restore","confirm","favorite"].indexOf(a)<0;})
                        delegate:Button { focusable:true; required property string modelData; text:strings.t(modelData); enabled:!root.preferencesBusy && (root.selectedRow!==null || root.selectionIndependent(modelData)); onClicked:root.activateSecondary(modelData) }
                    }
                }
                RowLayout {
                    Layout.fillWidth:true
                    TextField { id:collectionName; objectName:"lego-collection-name"; Layout.fillWidth:true; maximumLength:512; placeholderText:"Collection name"; Accessible.name:"Collection name"; onAccepted:root.collectionChange(text,false) }
                    Button { focusable:true; text:"Add/remove item"; enabled:root.selectedRow!==null && !root.preferencesBusy; onClicked:root.collectionChange(collectionName.text,false) }
                    Button { focusable:true; text:"Delete collection"; enabled:!root.preferencesBusy; onClicked:root.collectionChange(collectionName.text,true) }
                }
                RowLayout {
                    Layout.fillWidth:true
                    visible:root.actions.some(function(a){return ["capture","import","copy-color","preview","compare","export-preset"].indexOf(a)>=0;})
                    TextField { Layout.fillWidth:true; visible:root.actions.indexOf("capture")>=0; maximumLength:64; text:root.captureName; placeholderText:"Capture name"; Accessible.name:"Capture name"; onTextEdited:root.captureName=text }
                    TextField { Layout.fillWidth:true; maximumLength:16384; text:root.actionData; placeholderText:"Optional action data (JSON object)"; Accessible.name:"Action data JSON"; onTextEdited:root.actionData=text }
                }
                }
                Label { objectName: "lego-safety"; Layout.fillWidth: true; text: strings.t("safety"); wrapMode: Text.Wrap; elide: Text.ElideNone; font.pixelSize: Style.font.bodySmall; opacity: 0.7 }
            }
        }
    }
}
