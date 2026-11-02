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
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
    readonly property bool glyphMode: false
    readonly property bool presetMode: false
    readonly property var matches: Controller.filter(root.rows, root.query)
    readonly property var selectedRow: selected >= 0 && selected < matches.length ? matches[selected] : null
    readonly property string primaryVerb: actions.filter(function(a) { return a !== "restore" && a !== "confirm"; })[0] || ""
    onMatchesChanged: selected = Math.max(0, Math.min(selected, matches.length - 1))

    function open(payloadJson) {
        if (root.opened || root.opening) return;
        root.generation++; root.query = ""; root.selected = 0; root.rows = []; root.actions = []; root.message = "";
        root.opening = true; root.attemptAdmission();
    }
    function attemptAdmission() {
        if (root.opening && !root.opened && !lockProbe.running && !catalogue.running && !action.running) lockProbe.start();
    }
    function close() {
        root.generation++; root.opening = false; root.opened = false;
        root.rows = []; root.actions = []; root.query = ""; root.selected = 0; root.message = "";
        root.actionBusy = false;
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
    function acceptCatalogue(code, status, text, error) {
        if (!root.opened || root.catalogueGeneration !== root.generation) return;
        if (error || status !== 0) { root.rows = []; root.actions = []; root.message = strings.t("loadFailed"); return; }
        var data = Controller.catalog(text);
        root.rows = code === 0 ? data.rows : []; root.actions = code === 0 ? data.actions : [];
        root.message = data.message || (code !== 0 ? strings.t("loadFailed") : "");
    }
    function activate(verb) {
        if (!root.opened || root.opening || root.actionBusy || action.running || catalogue.running || lockProbe.running || root.actions.indexOf(verb) < 0) return;
        if (verb !== "restore" && (root.selected < 0 || root.selected >= root.matches.length)) return;
        var id = verb === "restore" ? "restore:last" : root.matches[root.selected].id;
        root.actionBusy = true; root.actionGeneration = root.generation; root.message = "";
        action.command = ["/usr/bin/python3", backendPath, "action", "--id", id, "--verb", verb, "--apply"];
        action.start();
    }
    function acceptAction(code, status, text, error) {
        if (!root.opened || root.actionGeneration !== root.generation) return;
        root.actionBusy = false;
        var result = Controller.actionResult(text, code, status, error);
        root.message = result.message;
        if (result.ok) {
            if (result.actions !== undefined) root.actions = result.actions;
            else root.loadCatalogue();
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
        byteLimit: 65536
        deadlineSeconds: 30
        onCompleted: (code, status, text, error) => root.acceptAction(code, status, text, error)
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
            height: Math.max(1, Math.min(Style.space(root.presetMode ? 520 : 650), panel.height - Style.space(32)))
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
                    if (event.key === Qt.Key_Escape) root.dismiss();
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
                    Label { text: strings.tn("results", root.matches.length).arg(Commons.I18n.formatNumber(root.matches.length)); opacity: 0.65; font.pixelSize: Style.font.bodySmall }
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
                    Button { id: clear; anchors.right: parent.right; anchors.rightMargin: Style.space(4); anchors.verticalCenter: parent.verticalCenter; text: "×"; Accessible.name: strings.t("clearSearch"); visible: root.query.length > 0; onClicked: { root.query = ""; root.selected = 0; keyboard.forceActiveFocus(); } }
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
                        readonly property int columns: root.presetMode ? 1 : Math.max(1, Math.floor(width / Style.space(root.glyphMode ? 104 : 176)))
                        cellWidth: width / columns
                        cellHeight: Style.space(root.presetMode ? (card.compact ? 76 : 88) : root.glyphMode ? 104 : 156)
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
                                anchors.top: root.presetMode ? undefined : parent.top
                                anchors.bottom: root.presetMode ? undefined : parent.bottom
                                anchors.verticalCenter: root.presetMode ? parent.verticalCenter : undefined
                                anchors.margins: root.presetMode ? Style.space(14) : Style.space(8)
                                spacing: Style.space(4)
                                Rectangle {
                                    visible: !root.presetMode
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
                                    Label { width: parent.width; text: modelData.label; font.pixelSize: root.presetMode ? Style.font.body : Style.font.bodySmall; font.bold: root.presetMode }
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
                            clip: true
                            contentHeight: detailLabels.implicitHeight
                            boundsBehavior: Flickable.StopAtBounds
                            Column {
                                id: detailLabels
                                width: parent.width
                                spacing: Style.space(8)
                                Label { width: parent.width; text: root.selectedRow ? root.selectedRow.label : ""; font.pixelSize: Style.font.title; font.bold: true; wrapMode: Text.Wrap; elide: Text.ElideNone }
                                Label { width: parent.width; text: root.selectedRow ? root.selectedRow.detail : ""; wrapMode: Text.Wrap; elide: Text.ElideNone; opacity: 0.75 }
                            }
                        }
                    }
                }
                Flickable {
                    objectName: "lego-compact-detail"
                    visible: card.compact && root.selectedRow !== null
                    Layout.fillWidth: true
                    Layout.preferredHeight: Style.space(40)
                    clip: true
                    contentHeight: compactLabels.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: compactLabels
                        width: parent.width
                        topPadding: Style.space(4)
                        spacing: Style.space(2)
                        Label { width: parent.width; text: root.selectedRow ? root.selectedRow.label : ""; font.bold: true; wrapMode: Text.Wrap; elide: Text.ElideNone }
                        Label { width: parent.width; text: root.selectedRow ? root.selectedRow.detail : ""; font.pixelSize: Style.font.bodySmall; wrapMode: Text.Wrap; elide: Text.ElideNone; opacity: 0.75 }
                    }
                    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Commons.Color.menu.border; opacity: 0.25 }
                }
                Label { Layout.fillWidth: true; text: root.message; visible: text.length > 0; wrapMode: Text.Wrap; elide: Text.ElideNone; font.pixelSize: Style.font.bodySmall }
                Flow {
                    Layout.fillWidth: true
                    spacing: Style.space(8)
                    Button { objectName: "lego-primary"; text: strings.t(root.primaryVerb || "select"); enabled: root.selectedRow !== null && !!root.primaryVerb && !root.actionBusy && !catalogue.running; active: true; foreground: Commons.Color.accent; bordered: true; onClicked: root.activate(root.primaryVerb) }
                    Button { text: strings.t("restore"); visible: root.actions.indexOf("restore") >= 0; enabled: !root.actionBusy && !catalogue.running && !action.running && !lockProbe.running; bordered: true; onClicked: root.activate("restore") }
                    Button { text: strings.t("confirm"); visible: root.actions.indexOf("confirm") >= 0; enabled: !root.actionBusy && root.selectedRow !== null; bordered: true; onClicked: root.activate("confirm") }
                    Button { text: strings.t("refresh"); enabled: !root.actionBusy && !catalogue.running; onClicked: root.loadCatalogue() }
                    Label { visible: !card.compact; text: root.actionBusy ? strings.t("working") : strings.t("keys"); font.pixelSize: Style.font.bodySmall; opacity: 0.6; height: Style.space(32); verticalAlignment: Text.AlignVCenter }
                }
                Label { objectName: "lego-safety"; Layout.fillWidth: true; text: strings.t("safety"); wrapMode: Text.Wrap; elide: Text.ElideNone; font.pixelSize: Style.font.bodySmall; opacity: 0.7 }
            }
        }
    }
}
