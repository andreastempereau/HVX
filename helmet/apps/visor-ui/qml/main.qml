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
    visibility: Window.FullScreen  // Start in fullscreen

    // Remove window decorations for fullscreen
    flags: Qt.FramelessWindowHint
    color: "black"

    property bool systemReady: false
    property bool widgetsDeployed: false
    property int orientationUpdateCount: 0
    property bool thermalActive: false

    // Main content - single 16:9 display
    Rectangle {
        id: mainDisplay
        anchors.fill: parent
        color: "black"
        visible: window.systemReady

        // Camera feed - COMMENTED OUT / DISABLED
        /*
        Image {
            id: videoFeed
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            cache: false
            asynchronous: false
            smooth: false

            function updateFrame(framePath) {
                source = framePath
            }
        }
        */

        // Thermal camera overlay (full screen)
        Image {
            id: thermalFeed
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            cache: false
            asynchronous: false
            smooth: false
            visible: window.thermalActive
            z: 1  // Above black background, below widgets

            function updateThermalFrame(framePath) {
                source = framePath
            }
        }
    }

    // Minimal status (top-right)
    MinimalStatus {
        id: minimalStatus
        parent: mainDisplay
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        visible: window.systemReady && currentHUDPreset !== 1
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
        parent: mainDisplay
        anchors.fill: parent
        visible: window.systemReady && currentHUDPreset !== 1
        opacity: window.systemReady && window.widgetsDeployed && currentHUDPreset !== 1 ? 0.8 : 0
        enabled: window.systemReady
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

    // Voice feedback overlay
    VoiceOverlay {
        id: voiceOverlay
        parent: mainDisplay
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 50
        visible: false
        enabled: window.systemReady
    }

    // Detection overlay
    DetectionOverlay {
        id: detectionOverlay
        parent: mainDisplay
        anchors.fill: parent
        visible: false
        opacity: 0
        enabled: window.systemReady
    }

    // Snapshot analysis widget
    SnapshotAnalysis {
        id: snapshotAnalysis
        parent: mainDisplay
        enabled: window.systemReady
    }

    // Closed captions widget
    ClosedCaptions {
        id: closedCaptions
        parent: mainDisplay
        enabled: window.systemReady
    }

    // Orientation crosshair
    OrientationCrosshair {
        id: orientationCrosshair
        parent: mainDisplay
        anchors.fill: parent
        visible: window.systemReady && currentHUDPreset !== 1
        z: 100
    }

    // GPS Minimap (bottom-left corner)
    Minimap {
        id: minimap
        parent: mainDisplay
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 20
        anchors.bottomMargin: 20
        width: 300
        height: 300
        visible: window.systemReady && currentHUDPreset !== 1
        z: 800
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
                case Qt.Key_S:  // 'S' key also quits
                    Qt.quit()
                    break
                case Qt.Key_F:
                    if (window.visibility === Window.FullScreen) {
                        window.showNormal()
                    } else {
                        window.showFullScreen()
                    }
                    break
                case Qt.Key_T:  // 'T' key toggles thermal overlay
                    window.thermalActive = !window.thermalActive
                    visorApp.toggleThermal()
                    break
                case Qt.Key_N:  // 'N' key triggers thermal NUC calibration
                    visorApp.triggerThermalNUC()
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
            // Camera feed disabled - do nothing
            // videoFeed.updateFrame(framePath)
        }

        function onThermalFrameUpdated(framePath) {
            thermalFeed.updateThermalFrame(framePath)
        }

        function onDetectionsUpdated(detections) {
            detectionOverlay.updateDetections(detections)
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

        function onOrientationUpdated(headingAngle, rollAngle, pitchAngle) {
            if (orientationUpdateCount < 5) {
                console.log("QML received orientation: heading=" + headingAngle.toFixed(2) + "°, roll=" + rollAngle.toFixed(2) + "°, pitch=" + pitchAngle.toFixed(2) + "°")
                orientationUpdateCount++
            }
            orientationCrosshair.headingAngle = headingAngle
            orientationCrosshair.rollAngle = rollAngle
            orientationCrosshair.pitchAngle = pitchAngle

            // Update preset wheel with orientation
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
        var shouldHide = (detailedHUD.visible && detailedHUD.opacity > 0)

        if (shouldHide) {
            detailedHUD.opacity = 0
            detailedHUD.visible = false
        } else {
            detailedHUD.visible = true
            detailedHUD.opacity = 0.8
        }
    }

    function toggleDetections() {
        var shouldHide = detectionOverlay.visible

        if (shouldHide) {
            detectionOverlay.opacity = 0
            detectionOverlay.visible = false
        } else {
            detectionOverlay.visible = true
            detectionOverlay.opacity = 0.9
        }
    }

    function hideAllOverlays() {
        detailedHUD.visible = false
        detailedHUD.opacity = 0
        detectionOverlay.visible = false
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
        // Start in fullscreen mode
        window.visibility = Window.FullScreen
    }
}