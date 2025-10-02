import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: hudOverlay

    property var statusData: ({})
    property var detections: []

    // Widget deployment states
    property bool widgetsDeployed: false

    // iOS 26 Military Glass Effect Component
    component MilitaryGlassPanel: Item {
        id: glassPanel
        property alias content: contentLoader.sourceComponent
        property color accentColor: "#00ff88"
        property real glassOpacity: 0.15

        Rectangle {
            id: glassBackground
            anchors.fill: parent
            color: "#0a0a0a"
            opacity: glassOpacity
            radius: 20

            // Subtle gradient overlay for depth
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#20ffffff" }
                    GradientStop { position: 0.5; color: "#10ffffff" }
                    GradientStop { position: 1.0; color: "#05ffffff" }
                }
            }
        }

        // Glass border with accent glow
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            radius: 20
            border.width: 1.5
            border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.4)

            // Inner glow
            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                color: "transparent"
                radius: parent.radius - 1
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.08)
            }
        }

        // Subtle top highlight
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 10
            height: 1
            radius: 0.5
            color: Qt.rgba(1, 1, 1, 0.15)
        }

        Loader {
            id: contentLoader
            anchors.fill: parent
            anchors.margins: 20
        }
    }

    // LEFT SIDE WIDGETS

    // Time Widget (Top Left)
    MilitaryGlassPanel {
        id: timeWidget
        x: widgetsDeployed ? 30 : -width
        y: 30
        width: 240
        height: 120
        accentColor: "#00ff88"

        Behavior on x {
            NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 8

            Text {
                text: "MISSION TIME"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#00ff88"
                opacity: 0.7
            }

            Text {
                id: timeText
                text: Qt.formatDateTime(new Date(), "HH:mm:ss")
                font.family: "SF Pro Display"
                font.pixelSize: 38
                font.weight: 25
                color: "#ffffff"
                opacity: 0.95
            }

            Text {
                text: Qt.formatDateTime(new Date(), "dd MMM yyyy").toUpperCase()
                font.family: "SF Pro Display"
                font.pixelSize: 12
                font.weight: 57
                color: "#ffffff"
                opacity: 0.5
            }

            Timer {
                interval: 1000
                running: true
                repeat: true
                onTriggered: timeText.text = Qt.formatDateTime(new Date(), "HH:mm:ss")
            }
        }
    }

    // System Vitals (Left, below time)
    MilitaryGlassPanel {
        id: systemWidget
        x: widgetsDeployed ? 30 : -width
        y: 170
        width: 240
        height: 180
        accentColor: "#00ff88"

        Behavior on x {
            NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 14

            Text {
                text: "SYSTEM VITALS"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#00ff88"
                opacity: 0.7
            }

            // CPU
            Column {
                spacing: 6
                width: parent.width

                Row {
                    spacing: 8
                    width: parent.width

                    Text {
                        text: "CPU"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.6
                        width: 60
                    }

                    Text {
                        text: Math.round(statusData.cpu_usage || 28) + "%"
                        font.family: "SF Pro Display"
                        font.pixelSize: 20
                        font.weight: 25
                        color: statusData.cpu_usage > 80 ? "#ff3b30" : "#00ff88"
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 4
                    radius: 2
                    color: "#1a1a1a"

                    Rectangle {
                        width: parent.width * ((statusData.cpu_usage || 28) / 100)
                        height: parent.height
                        radius: parent.radius
                        color: statusData.cpu_usage > 80 ? "#ff3b30" : "#00ff88"
                        opacity: 0.8
                    }
                }
            }

            // Memory
            Column {
                spacing: 6
                width: parent.width

                Row {
                    spacing: 8
                    width: parent.width

                    Text {
                        text: "MEMORY"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.6
                        width: 60
                    }

                    Text {
                        text: Math.round(statusData.memory_usage || 42) + "%"
                        font.family: "SF Pro Display"
                        font.pixelSize: 20
                        font.weight: 25
                        color: statusData.memory_usage > 80 ? "#ff3b30" : "#00ff88"
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 4
                    radius: 2
                    color: "#1a1a1a"

                    Rectangle {
                        width: parent.width * ((statusData.memory_usage || 42) / 100)
                        height: parent.height
                        radius: parent.radius
                        color: statusData.memory_usage > 80 ? "#ff3b30" : "#00ff88"
                        opacity: 0.8
                    }
                }
            }

            // Temperature
            Column {
                spacing: 6
                width: parent.width

                Row {
                    spacing: 8
                    width: parent.width

                    Text {
                        text: "TEMP"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.6
                        width: 60
                    }

                    Text {
                        text: Math.round(statusData.temperature || 48) + "°C"
                        font.family: "SF Pro Display"
                        font.pixelSize: 20
                        font.weight: 25
                        color: statusData.temperature > 70 ? "#ff3b30" : "#00ff88"
                    }
                }
            }
        }
    }

    // Network Status (Left, below system)
    MilitaryGlassPanel {
        id: networkWidget
        x: widgetsDeployed ? 30 : -width
        y: 370
        width: 240
        height: 140
        accentColor: "#00d4ff"

        Behavior on x {
            NumberAnimation { duration: 800; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 12

            Text {
                text: "NETWORK STATUS"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#00d4ff"
                opacity: 0.7
            }

            Row {
                spacing: 10

                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: "#00ff88"
                    anchors.verticalCenter: parent.verticalCenter

                    SequentialAnimation on opacity {
                        running: true
                        loops: Animation.Infinite
                        PropertyAnimation { to: 0.3; duration: 1000 }
                        PropertyAnimation { to: 1.0; duration: 1000 }
                    }
                }

                Text {
                    text: "LINK ACTIVE"
                    font.family: "SF Pro Display"
                    font.pixelSize: 14
                    font.weight: 57
                    color: "#ffffff"
                    opacity: 0.8
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Text {
                text: "SECURE • ENCRYPTED"
                font.family: "SF Pro Display"
                font.pixelSize: 11
                font.weight: 50
                color: "#ffffff"
                opacity: 0.4
            }

            Column {
                spacing: 6
                Text {
                    text: "LATENCY"
                    font.family: "SF Pro Display"
                    font.pixelSize: 9
                    color: "#ffffff"
                    opacity: 0.5
                }
                Text {
                    text: "12ms"
                    font.family: "SF Pro Display"
                    font.pixelSize: 18
                    font.weight: 25
                    color: "#00d4ff"
                }
            }
        }
    }

    // GPS/Location (Left, bottom)
    MilitaryGlassPanel {
        id: locationWidget
        x: widgetsDeployed ? 30 : -width
        y: 530
        width: 240
        height: 140
        accentColor: "#ffcc00"

        Behavior on x {
            NumberAnimation { duration: 900; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 10

            Text {
                text: "LOCATION"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#ffcc00"
                opacity: 0.7
            }

            Text {
                text: "37.7749° N"
                font.family: "SF Pro Display"
                font.pixelSize: 16
                font.weight: 25
                color: "#ffffff"
                opacity: 0.9
            }

            Text {
                text: "122.4194° W"
                font.family: "SF Pro Display"
                font.pixelSize: 16
                font.weight: 25
                color: "#ffffff"
                opacity: 0.9
            }

            Row {
                spacing: 8
                Text {
                    text: "ALTITUDE"
                    font.family: "SF Pro Display"
                    font.pixelSize: 9
                    color: "#ffffff"
                    opacity: 0.5
                }
                Text {
                    text: "52m"
                    font.family: "SF Pro Display"
                    font.pixelSize: 14
                    font.weight: 25
                    color: "#ffcc00"
                }
            }
        }
    }

    // RIGHT SIDE WIDGETS

    // Tactical Awareness (Top Right)
    MilitaryGlassPanel {
        id: tacticalWidget
        x: widgetsDeployed ? parent.width - width - 30 : parent.width
        y: 30
        width: 280
        height: 200
        accentColor: "#00d4ff"

        Behavior on x {
            NumberAnimation { duration: 600; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 12

            Text {
                text: "TACTICAL AWARENESS"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#00d4ff"
                opacity: 0.7
            }

            Row {
                spacing: 12

                Text {
                    text: detections.length
                    font.family: "SF Pro Display"
                    font.pixelSize: 48
                    font.weight: 25
                    color: "#ffffff"
                    opacity: 0.95
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: "OBJECTS"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.5
                    }
                    Text {
                        text: "TRACKED"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.5
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: "#ffffff"
                opacity: 0.1
            }

            Grid {
                columns: 2
                columnSpacing: 16
                rowSpacing: 10
                width: parent.width

                Repeater {
                    model: _getDetectionSummary()

                    Row {
                        spacing: 8

                        Rectangle {
                            width: 6
                            height: 6
                            radius: 3
                            color: _getObjectAccentColor(modelData.label)
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: modelData.label.toUpperCase()
                            font.family: "SF Pro Display"
                            font.pixelSize: 11
                            font.weight: 57
                            color: "#ffffff"
                            opacity: 0.7
                            width: 80
                        }

                        Text {
                            text: modelData.count
                            font.family: "SF Pro Display"
                            font.pixelSize: 18
                            font.weight: 25
                            color: _getObjectAccentColor(modelData.label)
                        }
                    }
                }
            }
        }
    }

    // Mission Status (Right, below tactical)
    MilitaryGlassPanel {
        id: missionWidget
        x: widgetsDeployed ? parent.width - width - 30 : parent.width
        y: 250
        width: 280
        height: 160
        accentColor: "#ff9500"

        Behavior on x {
            NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 12

            Text {
                text: "MISSION STATUS"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: "#ff9500"
                opacity: 0.7
            }

            Row {
                spacing: 12
                Text {
                    text: "OPERATIONAL"
                    font.family: "SF Pro Display"
                    font.pixelSize: 16
                    font.weight: 63
                    color: "#00ff88"
                }
            }

            Column {
                spacing: 8
                width: parent.width

                Row {
                    spacing: 8
                    width: parent.width
                    Text {
                        text: "DURATION"
                        font.family: "SF Pro Display"
                        font.pixelSize: 10
                        color: "#ffffff"
                        opacity: 0.5
                        width: 80
                    }
                    Text {
                        text: "02:34:12"
                        font.family: "SF Pro Display"
                        font.pixelSize: 14
                        font.weight: 25
                        color: "#ffffff"
                        opacity: 0.9
                    }
                }

                Row {
                    spacing: 8
                    width: parent.width
                    Text {
                        text: "RECORDING"
                        font.family: "SF Pro Display"
                        font.pixelSize: 10
                        color: "#ffffff"
                        opacity: 0.5
                        width: 80
                    }

                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: "#ff3b30"
                        anchors.verticalCenter: parent.verticalCenter

                        SequentialAnimation on opacity {
                            running: statusData.recording || false
                            loops: Animation.Infinite
                            PropertyAnimation { to: 0.3; duration: 800 }
                            PropertyAnimation { to: 1.0; duration: 800 }
                        }
                    }

                    Text {
                        text: statusData.recording ? "ACTIVE" : "STANDBY"
                        font.family: "SF Pro Display"
                        font.pixelSize: 14
                        font.weight: 25
                        color: statusData.recording ? "#ff3b30" : "#ffffff"
                        opacity: 0.9
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }

    // Threat Level (Right, below mission)
    MilitaryGlassPanel {
        id: threatWidget
        x: widgetsDeployed ? parent.width - width - 30 : parent.width
        y: 430
        width: 280
        height: 140
        accentColor: detections.some(d => d.label === "person") ? "#ff3b30" : "#00ff88"

        Behavior on x {
            NumberAnimation { duration: 800; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 12

            Text {
                text: "THREAT ASSESSMENT"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: detections.some(d => d.label === "person") ? "#ff3b30" : "#00ff88"
                opacity: 0.7
            }

            Text {
                text: detections.some(d => d.label === "person") ? "ELEVATED" : "NOMINAL"
                font.family: "SF Pro Display"
                font.pixelSize: 24
                font.weight: 63
                color: detections.some(d => d.label === "person") ? "#ff3b30" : "#00ff88"
            }

            Row {
                spacing: 8
                visible: detections.some(d => d.label === "person")

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#ff3b30"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: "PERSON DETECTED"
                    font.family: "SF Pro Display"
                    font.pixelSize: 12
                    font.weight: 57
                    color: "#ffffff"
                    opacity: 0.8
                }
            }

            Text {
                text: "All systems monitoring"
                font.family: "SF Pro Display"
                font.pixelSize: 11
                color: "#ffffff"
                opacity: 0.4
            }
        }
    }

    // Battery/Power (Right, bottom)
    MilitaryGlassPanel {
        id: powerWidget
        x: widgetsDeployed ? parent.width - width - 30 : parent.width
        y: 590
        width: 280
        height: 120
        accentColor: statusData.battery_level < 20 ? "#ff3b30" : "#00ff88"

        Behavior on x {
            NumberAnimation { duration: 900; easing.type: Easing.OutCubic }
        }

        content: Column {
            spacing: 12

            Text {
                text: "POWER SYSTEMS"
                font.family: "SF Pro Display"
                font.pixelSize: 10
                font.weight: 57
                color: statusData.battery_level < 20 ? "#ff3b30" : "#00ff88"
                opacity: 0.7
            }

            Row {
                spacing: 12

                Text {
                    text: Math.round(statusData.battery_level || 87) + "%"
                    font.family: "SF Pro Display"
                    font.pixelSize: 42
                    font.weight: 25
                    color: statusData.battery_level < 20 ? "#ff3b30" : "#ffffff"
                    opacity: 0.95
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: "BATTERY"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: "#ffffff"
                        opacity: 0.6
                    }
                    Text {
                        text: statusData.battery_level < 20 ? "LOW" : "NOMINAL"
                        font.family: "SF Pro Display"
                        font.pixelSize: 11
                        font.weight: 57
                        color: statusData.battery_level < 20 ? "#ff3b30" : "#00ff88"
                    }
                }
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

    function _getDetectionSummary() {
        var summary = {}
        for (var i = 0; i < detections.length; i++) {
            var label = detections[i].label
            if (summary[label]) {
                summary[label]++
            } else {
                summary[label] = 1
            }
        }

        var result = []
        for (var key in summary) {
            result.push({label: key, count: summary[key]})
        }

        result.sort((a, b) => b.count - a.count)
        return result.slice(0, 4)
    }

    function _getObjectAccentColor(label) {
        var colors = {
            "person": "#ff3b30",
            "car": "#00d4ff",
            "truck": "#00d4ff",
            "bike": "#00ff88",
            "traffic light": "#ffcc00",
            "stop sign": "#ff3b30"
        }
        return colors[label] || "#00d4ff"
    }

    function deployWidgets() {
        widgetsDeployed = true
    }
}
