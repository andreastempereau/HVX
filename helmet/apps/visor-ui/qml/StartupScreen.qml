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
                    font.weight: 75
                    color: "#cccccc"
                    anchors.centerIn: parent
                    style: Text.Normal
                }
            }

            // Subtitle
            Text {
                text: "HELMET VISION SYSTEM v1.1.1"
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
            anchors.bottomMargin: 80
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
                contentWidth: width
                clip: true
                flickableDirection: Flickable.VerticalFlick
                interactive: false

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
        terminalLines = lines

        // Auto-scroll to bottom only when content height exceeds visible area
        Qt.callLater(function() {
            if (terminalFlickable.contentHeight > terminalFlickable.height) {
                terminalFlickable.contentY = terminalFlickable.contentHeight - terminalFlickable.height
            }
        })
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
        interval: 80
        repeat: true
        running: true
        property int commandIndex: 0
        property var commands: [
            "[BOOT] HVX System initializing...",
            "[BIOS] Checking hardware compatibility... OK",
            "[BIOS] CPU: ARM Cortex-A57 @ 1.43GHz",
            "[BIOS] RAM: 4096 MB LPDDR4",
            "[BIOS] GPU: NVIDIA Maxwell (128 CUDA cores)",
            "[INIT] Loading kernel modules",
            "[KERN] module: video_capture.ko loaded",
            "[KERN] module: perception_ai.ko loaded",
            "[KERN] module: voice_engine.ko loaded",
            "[KERN] module: hud_compositor.ko loaded",
            "[KERN] module: neural_accel.ko loaded",
            "[KERN] module: csi_camera.ko loaded",
            "[SYS ] Mounting filesystems",
            "[SYS ] /dev/video0: CSI Camera detected",
            "[SYS ] /dev/video1: USB Camera detected",
            "[SYS ] /dev/perception: OK",
            "[SYS ] /dev/i2c-0: IMU sensor connected",
            "[SYS ] /dev/i2c-1: Environmental sensors OK",
            "[DRV ] Initializing camera drivers",
            "[DRV ] CSI-0: IMX219 8MP sensor initialized",
            "[DRV ] CSI-1: IMX219 8MP sensor initialized",
            "[DRV ] Setting camera mode: 1920x1080@30fps",
            "[DRV ] Auto-exposure enabled",
            "[DRV ] Auto-white-balance enabled",
            "[NET ] Initializing network stack",
            "[NET ] gRPC service discovery starting...",
            "[NET ] localhost:50051 - video service: ONLINE",
            "[NET ] localhost:50052 - perception service: ONLINE",
            "[NET ] localhost:50053 - voice service: ONLINE",
            "[NET ] localhost:50054 - orchestrator: ONLINE",
            "[NET ] localhost:50055 - telemetry: ONLINE",
            "[NET ] WebSocket server: ws://0.0.0.0:8080",
            "[GPU ] Initializing display compositor",
            "[GPU ] Resolution: 1920x1080 @ 60Hz",
            "[GPU ] OpenGL 4.5 detected",
            "[GPU ] CUDA Toolkit 10.2 loaded",
            "[GPU ] cuDNN 8.0.0 initialized",
            "[GPU ] TensorRT 7.1.3 ready",
            "[MEM ] Allocating shared memory buffers",
            "[MEM ] Video buffer: 64 MB (ring buffer)",
            "[MEM ] AI inference buffer: 128 MB",
            "[MEM ] HUD composition buffer: 32 MB",
            "[AI  ] Loading neural network models...",
            "[AI  ] YOLOv8n object detection: loading...",
            "[AI  ] Model weights: 6.2 MB",
            "[AI  ] Inference backend: TensorRT",
            "[AI  ] Quantization: INT8",
            "[AI  ] Model compiled for GPU acceleration",
            "[AI  ] YOLOv8n: READY (avg 45ms latency)",
            "[AI  ] Depth estimation model: loading...",
            "[AI  ] MiDaS depth network: READY",
            "[AUDIO] Initializing audio subsystem",
            "[AUDIO] ALSA version 1.2.4",
            "[AUDIO] Input device: USB Microphone Array",
            "[AUDIO] Sample rate: 16000 Hz",
            "[AUDIO] Channels: 1 (mono)",
            "[AUDIO] Buffer size: 512 frames",
            "[VOICE] Loading speech recognition engine",
            "[VOICE] Deepgram API: connected",
            "[VOICE] Wake word detection: active",
            "[VOICE] Voice activity detection: enabled",
            "[HUD ] Initializing overlay widgets",
            "[HUD ] Detection bounding boxes: READY",
            "[HUD ] Rearview mirror widget: READY",
            "[HUD ] Status display: READY",
            "[HUD ] Closed captions: READY",
            "[HUD ] Snapshot analysis: READY",
            "[CAL ] Running camera calibration",
            "[CAL ] Intrinsic matrix computed",
            "[CAL ] Distortion coefficients loaded",
            "[CAL ] Stereo rectification: OK",
            "[SAFE] Safety systems check",
            "[SAFE] Emergency shutdown handler: armed",
            "[SAFE] Thermal monitoring: active (CPU: 42°C)",
            "[SAFE] Power monitor: battery 98%",
            "[SAFE] Watchdog timer: enabled (5s timeout)",
            "[SYS ] All systems operational",
            "[SYS ] Total boot time: 4.2 seconds",
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
