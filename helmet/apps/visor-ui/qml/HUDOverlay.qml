import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: hudOverlay

    property var statusData: ({})
    property var detections: []

    // Widget deployment states
    property bool timeWidgetDeployed: false
    property bool systemWidgetDeployed: false
    property bool envWidgetDeployed: false
    property bool faceWidgetDeployed: false

    // Military-style tactical widget component
    component TacticalWidget: Rectangle {
        property alias content: contentLoader.sourceComponent
        property real widgetOpacity: 0.9

        color: "#0d0d0d"
        border.color: "#555555"
        border.width: 1
        radius: 0
        opacity: widgetOpacity

        Loader {
            id: contentLoader
            anchors.fill: parent
            anchors.margins: 10
        }
    }

    // Time Widget (Top Left) - Deploys from center
    TacticalWidget {
        id: timeWidget
        width: 220
        height: 90
        widgetOpacity: 0.9

        // Initial position (center) and final position (top-left)
        property real finalX: 20
        property real finalY: 20

        x: hudOverlay.timeWidgetDeployed ? finalX : parent.width / 2 - width / 2
        y: hudOverlay.timeWidgetDeployed ? finalY : parent.height / 2 - height / 2
        scale: hudOverlay.timeWidgetDeployed ? 1.0 : 0.1
        opacity: hudOverlay.timeWidgetDeployed ? widgetOpacity : 0

        Behavior on x { NumberAnimation { duration: 600; easing.type: Easing.OutQuad } }
        Behavior on y { NumberAnimation { duration: 600; easing.type: Easing.OutQuad } }
        Behavior on scale { NumberAnimation { duration: 400; easing.type: Easing.OutQuad } }
        Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.OutQuad } }

        content: Column {
            spacing: 6

            Text {
                text: "TIME"
                font.family: "Consolas"
                font.pixelSize: 8
                font.weight: Font.Bold
                color: "#888888"
            }

            Rectangle {
                width: 200
                height: 1
                color: "#333333"
            }

            Text {
                text: Qt.formatDateTime(new Date(), "hh:mm:ss")
                font.family: "Consolas"
                font.pixelSize: 20
                font.weight: Font.Bold
                color: "#cccccc"
            }

            Text {
                text: Qt.formatDateTime(new Date(), "yyyy-MM-dd")
                font.family: "Consolas"
                font.pixelSize: 10
                color: "#aaaaaa"
            }
        }

        Timer {
            id: timeUpdateTimer
            interval: 1000
            running: true
            repeat: true
            onTriggered: {
                // Update time text safely
                if (timeWidget.content && timeWidget.content.item) {
                    var timeColumn = timeWidget.content.item
                    if (timeColumn.children && timeColumn.children[0]) {
                        timeColumn.children[0].text = Qt.formatDateTime(new Date(), "hh:mm:ss")
                    }
                }
            }
        }
    }

    // System Status Widget (Top Right) - Deploys from center
    TacticalWidget {
        id: systemWidget
        width: 260
        height: 140
        widgetOpacity: 0.85

        // Final position (top-right)
        property real finalX: parent.width - width - 20
        property real finalY: 20

        x: hudOverlay.systemWidgetDeployed ? finalX : parent.width / 2 - width / 2
        y: hudOverlay.systemWidgetDeployed ? finalY : parent.height / 2 - height / 2
        scale: hudOverlay.systemWidgetDeployed ? 1.0 : 0.1
        opacity: hudOverlay.systemWidgetDeployed ? widgetOpacity : 0

        Behavior on x { NumberAnimation { duration: 900; easing.type: Easing.OutBack } }
        Behavior on y { NumberAnimation { duration: 900; easing.type: Easing.OutBack } }
        Behavior on scale { NumberAnimation { duration: 700; easing.type: Easing.OutBack } }
        Behavior on opacity { NumberAnimation { duration: 500; easing.type: Easing.OutQuad } }

        content: Column {
            spacing: 10

            Text {
                text: "SYSTEM STATUS"
                font.family: "Arial"
                font.pixelSize: 14
                font.weight: Font.Bold
                color: "#00BCD4"
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Row {
                spacing: 15
                anchors.horizontalCenter: parent.horizontalCenter

                // CPU indicator
                Column {
                    spacing: 4
                    Text {
                        text: "CPU"
                        font.pixelSize: 10
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 6
                        radius: 3
                        color: "#333333"
                        anchors.horizontalCenter: parent.horizontalCenter

                        Rectangle {
                            width: parent.width * ((statusData.cpu_usage || 25) / 100)
                            height: parent.height
                            radius: parent.radius
                            color: statusData.cpu_usage > 80 ? "#FF6B6B" : "#4ECDC4"
                        }
                    }
                    Text {
                        text: Math.round(statusData.cpu_usage || 25) + "%"
                        font.pixelSize: 10
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                // Memory indicator
                Column {
                    spacing: 4
                    Text {
                        text: "MEM"
                        font.pixelSize: 10
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Rectangle {
                        width: 40
                        height: 6
                        radius: 3
                        color: "#333333"
                        anchors.horizontalCenter: parent.horizontalCenter

                        Rectangle {
                            width: parent.width * ((statusData.memory_usage || 45) / 100)
                            height: parent.height
                            radius: parent.radius
                            color: statusData.memory_usage > 80 ? "#FF6B6B" : "#4ECDC4"
                        }
                    }
                    Text {
                        text: Math.round(statusData.memory_usage || 45) + "%"
                        font.pixelSize: 10
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                // Temperature
                Column {
                    spacing: 4
                    Text {
                        text: "TEMP"
                        font.pixelSize: 10
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: Math.round(statusData.temperature || 45) + "°"
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: statusData.temperature > 70 ? "#FF6B6B" : "#4ECDC4"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }
    }

    // Environmental Widget (Middle Left) - Deploys from center
    TacticalWidget {
        id: envWidget
        width: 200
        height: 110
        widgetOpacity: 0.82

        // Final position (middle-left)
        property real finalX: 20
        property real finalY: parent.height / 2 - height / 2

        x: hudOverlay.envWidgetDeployed ? finalX : parent.width / 2 - width / 2
        y: hudOverlay.envWidgetDeployed ? finalY : parent.height / 2 - height / 2
        scale: hudOverlay.envWidgetDeployed ? 1.0 : 0.1
        opacity: hudOverlay.envWidgetDeployed ? widgetOpacity : 0

        Behavior on x { NumberAnimation { duration: 1000; easing.type: Easing.OutBack } }
        Behavior on y { NumberAnimation { duration: 1000; easing.type: Easing.OutBack } }
        Behavior on scale { NumberAnimation { duration: 800; easing.type: Easing.OutBack } }
        Behavior on opacity { NumberAnimation { duration: 600; easing.type: Easing.OutQuad } }

        content: Column {
            spacing: 8

            Text {
                text: "ENVIRONMENT"
                font.family: "Arial"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#00BCD4"
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Row {
                spacing: 20
                anchors.horizontalCenter: parent.horizontalCenter

                Column {
                    Text {
                        text: "LIGHT"
                        font.pixelSize: 9
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "NORMAL"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#4ECDC4"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                Column {
                    Text {
                        text: "OBJECTS"
                        font.pixelSize: 9
                        color: "#CCCCCC"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: (statusData.detection_count || detections.length || 0)
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: "#00BCD4"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }
    }

    // Facial Recognition Widget (Only appears when person detected)
    TacticalWidget {
        id: faceWidget
        width: 220
        height: 100
        widgetOpacity: 0.88
        visible: detections.some(d => d.label === "person") && hudOverlay.faceWidgetDeployed

        // Final position (middle-right)
        property real finalX: parent.width - width - 20
        property real finalY: parent.height / 2 - height / 2

        x: hudOverlay.faceWidgetDeployed ? finalX : parent.width / 2 - width / 2
        y: hudOverlay.faceWidgetDeployed ? finalY : parent.height / 2 - height / 2
        scale: hudOverlay.faceWidgetDeployed ? 1.0 : 0.1
        opacity: (hudOverlay.faceWidgetDeployed && detections.some(d => d.label === "person")) ? widgetOpacity : 0

        Behavior on x { NumberAnimation { duration: 1100; easing.type: Easing.OutBack } }
        Behavior on y { NumberAnimation { duration: 1100; easing.type: Easing.OutBack } }
        Behavior on scale { NumberAnimation { duration: 900; easing.type: Easing.OutBack } }
        Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.OutQuad } }

        content: Column {
            spacing: 8

            Row {
                spacing: 10
                anchors.horizontalCenter: parent.horizontalCenter

                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    color: "#00BCD4"
                    opacity: 0.8

                    Text {
                        anchors.centerIn: parent
                        text: "👤"
                        font.pixelSize: 18
                    }
                }

                Column {
                    Text {
                        text: "PERSON DETECTED"
                        font.family: "Arial"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#00BCD4"
                    }
                    Text {
                        text: "Unknown Individual"
                        font.pixelSize: 9
                        color: "#CCCCCC"
                    }
                    Text {
                        text: "Confidence: " + Math.round((detections.find(d => d.label === "person")?.confidence || 0.85) * 100) + "%"
                        font.pixelSize: 8
                        color: "#4ECDC4"
                    }
                }
            }
        }

        // Subtle pulse animation
        SequentialAnimation on opacity {
            running: faceWidget.visible
            loops: Animation.Infinite
            PropertyAnimation { to: 0.15; duration: 2000 }
            PropertyAnimation { to: 0.25; duration: 2000 }
        }
    }

    // Voice Command Widget (Bottom Center, appears when listening)
    TacticalWidget {
        id: voiceWidget
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 40
        width: 300
        height: 70
        widgetOpacity: 0.9
        visible: statusData.mic_active || false

        content: Row {
            spacing: 15
            anchors.centerIn: parent

            Rectangle {
                width: 20
                height: 20
                radius: 10
                color: "#FF6B6B"

                SequentialAnimation on opacity {
                    running: voiceWidget.visible
                    loops: Animation.Infinite
                    PropertyAnimation { to: 0.4; duration: 500 }
                    PropertyAnimation { to: 1.0; duration: 500 }
                }
            }

            Column {
                Text {
                    text: "JARVIS LISTENING..."
                    font.family: "Arial"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#00BCD4"
                }
                Text {
                    text: "Say a command"
                    font.pixelSize: 10
                    color: "#CCCCCC"
                    opacity: 0.8
                }
            }

            // Audio level bars
            Row {
                spacing: 2
                Repeater {
                    model: 8
                    Rectangle {
                        width: 3
                        height: 4 + index * 3
                        radius: 1
                        color: index < (statusData.mic_level || 0.4) * 8 ? "#4ECDC4" : "#333333"
                    }
                }
            }
        }
    }

    // Connection Status (Floating dots in top area)
    Row {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 15
        spacing: 8

        Rectangle {
            width: 8
            height: 8
            radius: 4
            color: "#4ECDC4"
            opacity: 0.8
        }
        Rectangle {
            width: 8
            height: 8
            radius: 4
            color: "#4ECDC4"
            opacity: 0.8
        }
        Rectangle {
            width: 8
            height: 8
            radius: 4
            color: "#4ECDC4"
            opacity: 0.8
        }
    }

    // Object Detection Badges (Dynamic positioning over detected objects)
    Repeater {
        model: detections

        TacticalWidget {
            x: Math.min(parent.width - 120, Math.max(10, (modelData && modelData.x) ? modelData.x : 100))
            y: Math.min(parent.height - 60, Math.max(10, (modelData && modelData.y) ? modelData.y - 30 : 100))
            width: 120
            height: 40
            widgetOpacity: 0.6

            content: Row {
                spacing: 8
                anchors.centerIn: parent

                Rectangle {
                    width: 16
                    height: 16
                    radius: 8
                    color: _getObjectColor(modelData ? modelData.label : "unknown")
                }

                Text {
                    text: modelData ? modelData.label.toUpperCase() : "OBJECT"
                    font.family: "Arial"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
            }

            // Appear animation
            NumberAnimation on opacity {
                running: true
                from: 0
                to: widgetOpacity
                duration: 300
            }
        }
    }

    // Functions
    function updateStatus(status) {
        statusData = status || {}
    }

    function updateDetections(newDetections) {
        detections = newDetections || []
    }

    function _getObjectColor(label) {
        var colors = {
            "person": "#FF6B6B",
            "car": "#4ECDC4",
            "truck": "#45B7D1",
            "bike": "#96CEB4",
            "traffic light": "#FECA57",
            "stop sign": "#FF9FF3"
        }
        return colors[label] || "#00BCD4"
    }

    // Widget deployment sequence
    function deployWidgets() {
        deploymentSequence.start()
    }

    SequentialAnimation {
        id: deploymentSequence

        PauseAnimation { duration: 200 }
        ScriptAction { script: hudOverlay.timeWidgetDeployed = true }

        PauseAnimation { duration: 300 }
        ScriptAction { script: hudOverlay.systemWidgetDeployed = true }

        PauseAnimation { duration: 300 }
        ScriptAction { script: hudOverlay.envWidgetDeployed = true }

        PauseAnimation { duration: 300 }
        ScriptAction { script: hudOverlay.faceWidgetDeployed = true }
    }
}