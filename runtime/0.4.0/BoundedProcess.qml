// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import Quickshell.Io

Item {
    id: owner
    property var command: []
    property int deadlineSeconds: 2
    property int byteLimit: 1048576
    property var current: null
    readonly property bool running: current !== null
    signal completed(int code, int status, string text, string error)

    function start() {
        if (current) return;
        var run = factory.createObject(owner, {argv: command.slice(), limit: byteLimit});
        current = run;
        run.running = true;
    }
    function cancel() {
        var run = current;
        if (!run || run.cancelled) return;
        run.cancelled = true;
        // Keep ownership until the watchdog has drained the command group.
        run.signal(15);
    }
    function stopped(run) {
        if (run && !run.finished && !run.running) finish(run, -1, -1, "startFailed");
    }
    function finish(run, code, status, error) {
        if (run.finished) return;
        run.finished = true;
        var accepted = current === run && !run.cancelled;
        if (current === run) current = null;
        if (run.bytes > run.limit) error = "outputLimit";
        if (accepted) completed(code, status, error ? "" : run.output, error);
        run.destroy();
    }

    Component {
        id: factory
        Process {
            id: run
            required property var argv
            required property int limit
            property bool finished: false
            property bool cancelled: false
            readonly property string output: collected.text
            readonly property int bytes: collected.data.byteLength
            // Bound raw bytes before StdioCollector, including one overflow sentinel byte.
            // Caught signals reset on exec; keep only the supervisor alive until group KILL, even after QML closes its pipes.
            // The inner watchdog survives destruction of the QML-owned outer process.
            command: ["/usr/bin/timeout", "--kill-after=2", String(owner.deadlineSeconds + 2),
                "/usr/bin/timeout", "--kill-after=1", String(owner.deadlineSeconds), "/usr/bin/bash", "-c",
                'trap "while :; do /usr/bin/sleep 1; done" TERM PIPE; set -o pipefail; limit=$1; shift; "$@" 2>/dev/null | /usr/bin/head -c "$limit"',
                "native-overview", String(limit + 1)].concat(argv)
            stdout: StdioCollector { id: collected }
            onExited: (code, status) => owner.finish(run, code, status, "")
            // FailedToStart has no exited; defer until normal exited has had a chance to run.
            onRunningChanged: if (!running) Qt.callLater(function() {
                if (run) owner.stopped(run);
            })
        }
    }
}
