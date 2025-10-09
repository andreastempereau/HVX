import QtQuick 2.15

Item {
    id: root
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.margins: 20
    width: 240
    height: 100

    // Deployment animation properties
    property real deployProgress: 0.0
    property bool deployed: false

    // Orientation data
    property real headingAngle: 0.0
    property real rollAngle: 0.0
    property real pitchAngle: 0.0

    opacity: deployProgress
    scale: 0.8 + (0.2 * deployProgress)

    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
    }

    Behavior on scale {
        NumberAnimation { duration: 400; easing.type: Easing.OutBack }
    }

    // Glass background with layered effect
    Rectangle {
        id: background
        anchors.fill: parent
        color: "#1A1A1A"
        opacity: 0.7
        radius: 12
        border.color: "#00FF00"
        border.width: 1
    }

    // Inner glow effect
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        radius: 11
        border.color: "#00FF00"
        border.width: 1
        opacity: 0.2
    }

    // Content
    Column {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 3

        // Title
        Text {
            text: "ORIENTATION"
            color: "#00FF00"
            font.pixelSize: 12
            font.bold: true
            font.letterSpacing: 1
            opacity: 0.8
        }

        // Separator
        Rectangle {
            width: parent.width
            height: 1
            color: "#00FF00"
            opacity: 0.3
        }

        // Sensor readings
        Column {
            width: parent.width
            spacing: 2

            Row {
                width: parent.width
                spacing: 5

                Text {
                    text: "HDG:"
                    color: "#808080"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    width: 45
                }

                Text {
                    text: headingAngle.toFixed(1) + "°"
                    color: "#00FF00"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    font.bold: true
                }
            }

            Row {
                width: parent.width
                spacing: 5

                Text {
                    text: "ROLL:"
                    color: "#808080"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    width: 45
                }

                Text {
                    text: rollAngle.toFixed(1) + "°"
                    color: "#00FF00"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    font.bold: true
                }
            }

            Row {
                width: parent.width
                spacing: 5

                Text {
                    text: "PITCH:"
                    color: "#808080"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    width: 45
                }

                Text {
                    text: pitchAngle.toFixed(1) + "°"
                    color: "#00FF00"
                    font.pixelSize: 13
                    font.family: "Monospace"
                    font.bold: true
                }
            }
        }
    }

    // Deploy animation
    function deploy() {
        deployed = true
        deployProgress = 1.0
    }

    function hide() {
        deployed = false
        deployProgress = 0.0
    }
}
