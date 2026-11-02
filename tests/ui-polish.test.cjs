const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const test = require('node:test'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.env.UI_POLISH_SOURCE || require('./runtime-path.cjs')(require('../manifest.json').entryPoints.overlay.split('/').pop()), 'utf8');
function binding(name) {
    const match = source.match(new RegExp('(?:readonly property (?:int|bool|string) )?' + name + ': ([^\\n;]+)'));
    assert.ok(match, 'Missing layout binding: ' + name);
    return match[1];
}
test('Preset dialogs have fixed bounded 680 by 520 geometry, galleries keep their image-first canvas', () => {
    const cardSource = source.slice(source.indexOf('id: card'), source.indexOf('readonly property bool compact'));
    for (const [presetMode, viewportWidth, viewportHeight, expectedWidth, expectedHeight] of [
        [true, 1280, 800, 680, 520], [true, 640, 480, 608, 448],
        [false, 1280, 800, 1000, 650], [false, 640, 480, 608, 448]
    ]) {
        for (const [name, expected] of [['width', expectedWidth], ['height', expectedHeight]]) {
            const expression = cardSource.match(new RegExp('\\b' + name + ': ([^\\n]+)'))[1];
            assert.equal(vm.runInNewContext(expression, {Math, Style: {space: n => n}, root: {presetMode}, panel: {width: viewportWidth, height: viewportHeight}}), expected);
        }
    }
    assert.doesNotMatch(cardSource, /implicitHeight/);
});
test('Safety footer is localized plain text and wraps without claiming read-only behavior', () => {
    const footer = source.split('\n').find(line => line.includes('objectName: "lego-safety"')) || '';
    assert.match(footer, /text: strings.t\("safety"\)/);
    assert.match(footer, /Layout.fillWidth: true/);
    assert.match(footer, /wrapMode: Text.Wrap; elide: Text.ElideNone/);
    assert.match(footer, /font.pixelSize: Style.font.bodySmall/);
    assert.doesNotMatch(footer, /visible: !card.compact|read.only/i);
    assert.ok(source.indexOf('objectName: "lego-safety"') > source.indexOf('objectName: "lego-primary"'));
    assert.match(source, /component Label: Text \{\s+textFormat: Text.PlainText/);
    const search = source.slice(source.indexOf('objectName: "lego-search"'), source.indexOf('GridView {'));
    assert.match(search, /implicitHeight: Style.space\(36\)/, 'Compact toolbar makes room for safety without losing three rows');
});
const space = n => n;
function evaluate(name, context) { return vm.runInNewContext(binding(name), {Style: {space}, card: {compact: false}, ...context}); }

test('Configure keeps the existing grid but fits three readable preset rows', () => {
    for (const width of [260, 584, 600]) {
        const root = {presetMode: true, glyphMode: false};
        assert.equal(evaluate('columns', {root, width}), 1);
        const height = evaluate('cellHeight', {root});
        assert.ok(height >= 76 && height <= 96, 'Three presets must fit without giant letter tiles');
    }
    assert.match(source, /readonly property bool presetMode: false/);
    assert.equal((source.match(/objectName: "lego-results"/g) || []).length, 1);
    assert.doesNotMatch(source, /ListView\s*\{/);
    assert.match(source, /visible: !root.presetMode/);
});

test('Single-line title toolbar avoids redundant role and subtitle labels while preserving focused search', () => {
    assert.ok(source.includes('text: "♟"'), 'Meaningful tool icon is materialized by the caller');
    const header = source.slice(source.indexOf('objectName: "lego-toolbar"'), source.indexOf('objectName: "lego-search"'));
    assert.ok(header.length > 0, 'Toolbar has an inspectable hierarchy');
    assert.equal((header.match(/strings.t\("title"\)/g) || []).length, 1);
    assert.doesNotMatch(header, /strings.t\(root.presetMode|strings.t\("subtitle"\)/);
    assert.match(header, /strings.tn\("results", root.matches.length\)/, 'Caller provides truthful per-tool count units');
    assert.match(header, /Layout.preferredHeight: Style.space\(32\)/);
    const search = source.slice(source.indexOf('objectName: "lego-search"'), source.indexOf('GridView {'));
    assert.ok(search.length > 0, 'Search has an inspectable focus surface');
    const expression = search.match(/border.color: ([^\n]+)/)[1];
    for (const focused of [true, false]) {
        assert.equal(vm.runInNewContext(expression, {keyboard: {activeFocus: focused}, Commons: {Color: {accent: 'accent', menu: {border: 'border'}}}}), focused ? 'accent' : 'border');
    }
    assert.match(search, /border.width: keyboard.activeFocus \? 2 : 1/);
    assert.match(search, /Accessible.name: strings.t\("clearSearch"\)/);
    const primary = source.split('\n').find(line => line.includes('objectName: "lego-primary"')) || '';
    assert.match(primary, /active: true/);
    assert.match(primary, /foreground: Commons.Color.accent/);
});

test('Local preview failures stay legible and selection has a distinct accent border', () => {
    const tile = source.slice(source.indexOf('objectName: "lego-result"'), source.indexOf('ColumnLayout {\n                        visible: !card.compact'));
    assert.ok(tile.length > 0, 'Result delegate is inspectable');
    const border = tile.match(/border.color: ([^\n]+)/)[1];
    for (const selected of [0, 1]) {
        assert.equal(vm.runInNewContext(border, {index: 0, root: {selected}, Commons: {Color: {accent: 'accent', menu: {border: 'border'}}}, tileMouse: {containsMouse: false}}), selected === 0 ? 'accent' : 'transparent');
    }
    assert.match(tile, /border.width: index === root.selected \? 2 : 1/);
    assert.match(tile, /Style.hoverFillFor/);
    const thumb = source.split('\n').find(line => line.includes('thumbImage.status !== Image.Ready')) || '';
    const preview = source.split('\n').find(line => line.includes('detailImage.status !== Image.Ready')) || '';
    for (const [line, image] of [[thumb, 'thumbImage'], [preview, 'detailImage']]) {
        assert.ok(line.includes('"♟"'), 'Missing preview uses tool icon, not a giant initial');
        const expression = line.match(/visible: ([^;]+)/)[1];
        for (const status of [0, 1, 2, 3]) {
            const context = {modelData: {color: ''}, root: {selectedRow: {color: ''}}, [image]: {status}, Image: {Ready: 1}};
            assert.equal(vm.runInNewContext(expression, context), status !== 1);
            context.modelData.color = context.root.selectedRow.color = '#abcdef';
            assert.equal(vm.runInNewContext(expression, context), false);
        }
    }
});

test('Selected labels and authoritative detail remain readable in bounded wide and compact panes', () => {
    assert.ok(source.includes('objectName: "lego-detail"'), 'Wide details need an inspectable scrolling area');
    assert.ok(source.includes('objectName: "lego-compact-detail"'), 'Compact mode must not discard full selected metadata');
    assert.ok((source.match(/contentHeight: \w+.implicitHeight/g) || []).length >= 2);
    assert.ok((source.match(/wrapMode: Text.Wrap; elide: Text.ElideNone/g) || []).length >= 4);
    assert.doesNotMatch(source, /charAt\(0\)/);
});

test('Compact presets reserve space for three choices without dropping selected metadata', () => {
    const height = evaluate('cellHeight', {root: {presetMode: true, glyphMode: false}, card: {compact: true}});
    assert.ok(height <= 76, 'Compact preset rows must fit three choices');
    assert.ok(source.includes('spacing: card.compact ? Style.space(8) : Style.space(12)'));
    const hint = source.split('\n').find(line => line.includes('strings.t("keys")')) || '';
    assert.match(hint, /visible: !card.compact/);
});

test('Preview sizing avoids feedback and compact detail grows with readable content within a cap', () => {
    assert.doesNotMatch(source, /Layout.maximumHeight: parent.height/);
    const compact = source.slice(source.indexOf('objectName: "lego-compact-detail"'));
    const expression = compact.match(/Layout.preferredHeight: ([^\n]+)/)[1];
    for (const [implicitHeight, expected] of [[32, 32], [43, 43], [160, 64]]) {
        assert.equal(vm.runInNewContext(expression, {Style: {space: x => x}, compactLabels: {implicitHeight}}), expected);
    }
    assert.doesNotMatch(expression, /parent\.height/);
    assert.match(source, /anchors.verticalCenter: root.presetMode \? parent.verticalCenter : undefined/);
});
