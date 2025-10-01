import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: startupScreen
    anchors.fill: parent
    color: "#000000"

    property bool animationRunning: true
    property int loadingProgress: 0
    property string statusText: "Initializing HVX Systems..."
    property var terminalLines: []
    property int maxTerminalLines: 25

    signal startupComplete()

    // Dark terminal-style background
    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
    }

    // Scanline effect overlay
    Rectangle {
        id: scanlineOverlay
        anchors.fill: parent
        opacity: 0.05
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "#000000" }
            GradientStop { position: 0.5; color: "#ffffff" }
            GradientStop { position: 1.0; color: "#000000" }
        }

        NumberAnimation on y {
            running: startupScreen.animationRunning
            from: -parent.height
            to: parent.height
            duration: 3000
            loops: Animation.Infinite
        }
    }

    // Main content
    Item {
        anchors.fill: parent
        anchors.margins: 40

        // HVX Logo - simple greyscale
        Item {
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            width: 400
            height: 120

            // Simple bordered box
            Rectangle {
                anchors.centerIn: parent
                width: 280
                height: 100
                color: "transparent"
                border.color: "#666666"
                border.width: 2
                radius: 2

                Text {
                    text: "HVX"
                    font.family: "Consolas"
                    font.pixelSize: 60
                    font.weight: Font.Bold
                    color: "#cccccc"
                    anchors.centerIn: parent
                    style: Text.Normal
                }
            }

            // Subtitle
            Text {
                text: "HELMET VISION SYSTEM v1.0.0"
                font.family: "Consolas"
                font.pixelSize: 12
                font.letterSpacing: 2
                color: "#777777"
                anchors.top: parent.bottom
                anchors.topMargin: 15
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }

        // Terminal output area
        Rectangle {
            id: terminalArea
            anchors.top: parent.top
            anchors.topMargin: 180
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 100
            color: "#0d0d0d"
            border.color: "#333333"
            border.width: 1
            radius: 2

            // Terminal content
            Flickable {
                id: terminalFlickable
                anchors.fill: parent
                anchors.margins: 15
                contentHeight: terminalColumn.height
                clip: true
                flickableDirection: Flickable.VerticalFlick

                Column {
                    id: terminalColumn
                    width: parent.width
                    spacing: 2

                    Repeater {
                        model: terminalLines

                        Text {
                            text: modelData
                            font.family: "Consolas"
                            font.pixelSize: 11
                            color: "#aaaaaa"
                            wrapMode: Text.NoWrap
                        }
                    }

                    // Cursor
                    Row {
                        spacing: 2
                        Text {
                            text: ">"
                            font.family: "Consolas"
                            font.pixelSize: 11
                            color: "#cccccc"
                        }

                        Rectangle {
                            width: 8
                            height: 14
                            color: "#cccccc"
                            y: 2

                            SequentialAnimation on opacity {
                                running: startupScreen.animationRunning
                                loops: Animation.Infinite
                                PropertyAnimation { to: 0; duration: 500 }
                                PropertyAnimation { to: 1; duration: 500 }
                            }
                        }
                    }
                }
            }
        }

        // Progress bar at bottom
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 60
            color: "#0d0d0d"
            border.color: "#333333"
            border.width: 1
            radius: 2

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -5
                spacing: 10
                width: parent.width - 40

                // Status text
                Text {
                    text: startupScreen.statusText
                    font.family: "Consolas"
                    font.pixelSize: 11
                    color: "#999999"
                    width: parent.width
                    elide: Text.ElideRight
                }

                // Progress bar
                Row {
                    spacing: 10
                    width: parent.width

                    Rectangle {
                        width: parent.width - 60
                        height: 12
                        color: "#1a1a1a"
                        border.color: "#333333"
                        border.width: 1

                        Rectangle {
                            width: (parent.width - 2) * startupScreen.loadingProgress / 100
                            height: parent.height - 2
                            color: "#666666"
                            anchors.left: parent.left
                            anchors.leftMargin: 1
                            anchors.verticalCenter: parent.verticalCenter

                            Behavior on width {
                                NumberAnimation { duration: 200; easing.type: Easing.Linear }
                            }
                        }
                    }

                    Text {
                        text: startupScreen.loadingProgress + "%"
                        font.family: "Consolas"
                        font.pixelSize: 11
                        color: "#999999"
                        width: 50
                    }
                }
            }
        }
    }

    // Functions
    function updateProgress(progress, status) {
        loadingProgress = progress
        statusText = status
    }

    function addTerminalLine(line) {
        var lines = terminalLines
        lines.push(line)
        if (lines.length > maxTerminalLines) {
            lines.shift()
        }
        terminalLines = lines

        // Auto-scroll to bottom
        terminalFlickable.contentY = Math.max(0, terminalColumn.height - terminalFlickable.height)
    }

    function completeStartup() {
        animationRunning = false
        fadeOutAnimation.start()
    }

    // Fade out animation
    NumberAnimation {
        id: fadeOutAnimation
        target: startupScreen
        property: "opacity"
        to: 0
        duration: 800
        easing.type: Easing.OutQuad
        onFinished: {
            startupScreen.startupComplete()
        }
    }

    // Simulated terminal commands
    Timer {
        id: commandTimer
        interval: 150
        repeat: true
        running: true
        property int commandIndex: 0
        property var commands: [
            "[BOOT] HVX System initializing...",
            "[BIOS] Checking hardware compatibility... OK",
            "[INIT] Loading kernel modules",
            "[KERN] module: video_capture.ko loaded",
            "[KERN] module: perception_ai.ko loaded",
            "[KERN] module: voice_engine.ko loaded",
            "[KERN] module: hud_compositor.ko loaded",
            "[SYS ] Mounting filesystems",
            "[SYS ] /dev/video0: OK",
            "[SYS ] /dev/perception: OK",
            "[NET ] Initializing gRPC services...",
            "[NET ] localhost:50051 - video service: ONLINE",
            "[NET ] localhost:50052 - perception service: ONLINE",
            "[NET ] localhost:50053 - voice service: ONLINE",
            "[NET ] localhost:50054 - orchestrator: ONLINE",
            "[GPU ] Initializing display compositor",
            "[GPU ] Resolution: 1920x1080 @ 60Hz",
            "[GPU ] OpenGL 4.5 detected",
            "[AI  ] Loading YOLOv8n model... OK",
            "[AI  ] Model weights: 6.2 MB",
            "[AI  ] Inference backend: CPU",
            "[HUD ] Initializing overlay widgets",
            "[HUD ] Detection overlay: READY",
            "[HUD ] Status display: READY",
            "[SYS ] All systems operational",
            "[BOOT] HVX ready for deployment"
        ]

        onTriggered: {
            if (commandIndex < commands.length) {
                addTerminalLine(commands[commandIndex])

                // Update progress based on command index
                var progress = Math.floor((commandIndex / commands.length) * 100)
                var statusMessages = [
                    "Initializing core systems...",
                    "Loading kernel modules...",
                    "Starting network services...",
                    "Initializing AI models...",
                    "Loading HUD components...",
                    "System ready"
                ]
                var statusIndex = Math.floor((commandIndex / commands.length) * (statusMessages.length - 1))
                updateProgress(progress, statusMessages[statusIndex])

                commandIndex++
            } else {
                updateProgress(100, "System ready")
                commandTimer.stop()
                Qt.callLater(completeStartup)
            }
        }
    }
}
