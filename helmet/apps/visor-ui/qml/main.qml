import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import HelmetUI 1.0

ApplicationWindow {
    id: window
    visible: true
    width: 1920
    height: 1080
    title: "Helmet Visor UI"

    // Remove window decorations for fullscreen
    flags: Qt.FramelessWindowHint
    color: "black"

    property bool systemReady: false
    property bool widgetsDeployed: false
    property int orientationUpdateCount: 0

    // Main content - fullscreen video
    Rectangle {
        anchors.fill: parent
        color: "black"
        visible: window.systemReady

        // Single fullscreen video
        Image {
            id: fullscreenVideo
            anchors.fill: parent
            fillMode: Image.PreserveAspectCrop
            cache: false
            asynchronous: false  // Synchronous for lower latency
            smooth: false        // Disable smoothing for performance

            function updateFrame(framePath) {
                source = framePath
            }
        }
    }

    // MINIMAL persistent status (top-right corner only)
    MinimalStatus {
        id: minimalStatus
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        visible: window.systemReady && currentHUDPreset !== 1  // Hide in clear mode
    }

    // Startup screen - shown initially
    StartupScreen {
        id: startupScreen
        anchors.fill: parent
        visible: !window.systemReady

        onStartupComplete: {
            window.systemReady = true
            // Start widget deployment animation after brief delay
            widgetDeployTimer.start()
        }
    }

    // HUD overlay with deployment animation
    HUDOverlay {
        id: detailedHUD
        anchors.fill: parent
        visible: window.systemReady && currentHUDPreset !== 1  // Hide in clear mode
        opacity: window.systemReady && window.widgetsDeployed && currentHUDPreset !== 1 ? 0.8 : 0
        enabled: window.systemReady

        // Widget deployment properties
        property bool deploying: false

        Behavior on opacity {
            NumberAnimation { duration: 800; easing.type: Easing.OutQuad }
        }
    }

    // Widget deployment timer
    Timer {
        id: widgetDeployTimer
        interval: 500
        onTriggered: {
            detailedHUD.deploying = true
            widgetSequence.start()
        }
    }

    // Sequential widget deployment animation
    SequentialAnimation {
        id: widgetSequence

        ScriptAction {
            script: {
                console.log("Starting widget deployment sequence")
                detailedHUD.deployWidgets()
                window.widgetsDeployed = true
                // Enable captions after startup
                closedCaptions.enableWhenReady()
            }
        }

    }

    // Voice feedback overlay (appears during voice interaction)
    VoiceOverlay {
        id: voiceOverlay
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 50
        visible: false
        enabled: window.systemReady
    }

    // Detection overlay (shows/hides based on voice commands)
    DetectionOverlay {
        id: detectionOverlay
        anchors.fill: parent
        visible: false
        opacity: 0
        enabled: window.systemReady
    }

    // Snapshot analysis widget
    SnapshotAnalysis {
        id: snapshotAnalysis
        enabled: window.systemReady
    }

    // Closed captions widget
    ClosedCaptions {
        id: closedCaptions
        enabled: window.systemReady
    }

    // Rearview mirror widget
    RearviewMirror {
        id: rearviewMirror
        visible: window.systemReady && currentHUDPreset !== 1  // Hide in clear mode
    }

    // Orientation crosshair
    OrientationCrosshair {
        id: orientationCrosshair
        visible: window.systemReady && currentHUDPreset !== 1  // Hide in clear mode
        z: 100  // Above video but below overlays
    }

    // HUD Preset Wheel (always enabled, even in clear mode)
    HUDPresetWheel {
        id: hudPresetWheel
        z: 1000  // On top of everything
        enabled: true  // Always active so you can switch out of clear mode

        onPresetChanged: function(presetIndex) {
            console.log("HUD Preset changed to:", presetIndex)
            window.currentHUDPreset = presetIndex
        }
    }

    // Track current HUD preset
    property int currentHUDPreset: 0  // 0=full, 1=clear, 2=custom


    // Keyboard handler - invisible item that captures all keyboard input
    Item {
        id: keyHandler
        anchors.fill: parent
        focus: true
        z: 10000

        Keys.onPressed: function(event) {
            switch (event.key) {
                case Qt.Key_Escape:
                    Qt.quit()
                    break
                case Qt.Key_F:
                    if (window.visibility === Window.FullScreen) {
                        window.showNormal()
                    } else {
                        window.showFullScreen()
                    }
                    break
                case Qt.Key_H:
                    toggleDetailedHUD()
                    break
                case Qt.Key_D:
                    toggleDetections()
                    break
                case Qt.Key_C:
                    hideAllOverlays()
                    break
                case Qt.Key_P:
                    captureAndAnalyze()
                    break
                case Qt.Key_Space:
                    voiceOverlay.show("Listening...", true)
                    break
            }
            event.accepted = true
        }
    }

    // Connect signals from Python visorApp instance (provided as context property)
    Connections {
        target: visorApp

        function onFrameUpdated(framePath) {
            fullscreenVideo.updateFrame(framePath)
        }

        function onDetectionsUpdated(detections) {
            // Always update detection overlay (it will handle visibility internally)
            detectionOverlay.updateDetections(detections)
            // Always update HUD with detections for facial recognition and object badges
            detailedHUD.updateDetections(detections)
        }

        function onHudStatusUpdated(status) {
            minimalStatus.updateStatus(status)
            detailedHUD.updateStatus(status)
        }

        function onSnapshotAnalyzed(snapshotPath, analysisText) {
            snapshotAnalysis.show(snapshotPath)
            snapshotAnalysis.setAnalysis(analysisText)
        }

        function onCaptionReceived(text, isFinal) {
            console.log("QML received caption:", text, "final:", isFinal)
            closedCaptions.show(text, isFinal)
        }

        function onRearFrameUpdated(framePath) {
            rearviewMirror.updateFrame(framePath)
        }

        function onOrientationUpdated(headingAngle, rollAngle, pitchAngle) {
            if (orientationUpdateCount < 5) {
                console.log("QML received orientation: heading=" + headingAngle.toFixed(2) + "°, roll=" + rollAngle.toFixed(2) + "°, pitch=" + pitchAngle.toFixed(2) + "°")
                orientationUpdateCount++
            }
            orientationCrosshair.headingAngle = headingAngle
            orientationCrosshair.rollAngle = rollAngle
            orientationCrosshair.pitchAngle = pitchAngle

            // Update preset wheel with orientation (pass heading, roll, pitch)
            hudPresetWheel.updateOrientation(headingAngle, rollAngle, pitchAngle)
        }
    }

    // Voice command handlers
    property var overlayStates: {
        "show_hud": false,
        "show_detections": false,
        "show_navigation": false
    }

    function handleVoiceCommand(command) {
        switch (command) {
            case "show_hud":
            case "show_status":
                toggleDetailedHUD()
                break
            case "show_detections":
            case "show_objects":
                toggleDetections()
                break
            case "hide_overlays":
            case "clear_display":
                hideAllOverlays()
                break
            case "voice_mode":
                voiceOverlay.show("Listening...", true)
                break
        }
    }

    function toggleDetailedHUD() {
        if (detailedHUD.visible && detailedHUD.opacity > 0) {
            detailedHUD.opacity = 0
            detailedHUD.visible = false
        } else {
            detailedHUD.visible = true
            detailedHUD.opacity = 0.8
        }
    }

    function toggleDetections() {
        if (detectionOverlay.visible) {
            detectionOverlay.opacity = 0
            detectionOverlay.visible = false
        } else {
            detectionOverlay.visible = true
            detectionOverlay.opacity = 0.9
        }
    }

    function hideAllOverlays() {
        detailedHUD.visible = false
        detectionOverlay.visible = false
        detailedHUD.opacity = 0
        detectionOverlay.opacity = 0
    }

    function captureAndAnalyze() {
        console.log("============================================")
        console.log("QML: P KEY PRESSED - Capture and analyze")
        console.log("============================================")
        // Request snapshot analysis from Python backend
        visorApp.captureAndAnalyze()
    }

    Component.onCompleted: {
        keyHandler.forceActiveFocus()
    }
}