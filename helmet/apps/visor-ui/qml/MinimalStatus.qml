import QtQuick 2.15
import QtQuick.Controls 2.15

// MINIMAL persistent status - military style
Item {
    id: minimalStatus
    width: 140
    height: 80

    property var statusData: ({})

    // Main container
    Rectangle {
        anchors.fill: parent
        color: "#0d0d0d"
        border.color: "#555555"
        border.width: 1
        radius: 0
        opacity: 0.9
    }

    Column {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        // Header
        Text {
            text: "SYSTEM"
            font.family: "Consolas"
            font.pixelSize: 8
            font.weight: Font.Bold
            color: "#888888"
        }

        Rectangle {
            width: parent.width - 16
            height: 1
            color: "#333333"
        }

        // Battery
        Row {
            visible: statusData.battery_level !== undefined
            spacing: 6
            width: parent.width - 16

            Text {
                text: "PWR"
                font.family: "Consolas"
                font.pixelSize: 8
                color: "#888888"
                width: 30
            }

            Rectangle {
                width: 50
                height: 10
                border.color: "#666666"
                border.width: 1
                color: "#1a1a1a"
                radius: 0

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: 1
                    width: (parent.width - 2) * (statusData.battery_level || 0) / 100
                    color: statusData.battery_level > 20 ? "#888888" : "#555555"
                }

                // Battery terminal
                Rectangle {
                    width: 2
                    height: 6
                    color: "#666666"
                    anchors.right: parent.right
                    anchors.rightMargin: -2
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            Text {
                text: Math.round(statusData.battery_level || 0) + "%"
                color: "#aaaaaa"
                font.family: "Consolas"
                font.pixelSize: 8
            }
        }

        // Recording indicator
        Row {
            visible: statusData.recording || false
            spacing: 6
            width: parent.width - 16

            Text {
                text: "REC"
                font.family: "Consolas"
                font.pixelSize: 8
                color: "#888888"
                width: 30
            }

            Rectangle {
                width: 6
                height: 6
                radius: 0
                color: "#999999"
                anchors.verticalCenter: parent.verticalCenter

                SequentialAnimation on opacity {
                    running: statusData.recording || false
                    loops: Animation.Infinite
                    PropertyAnimation { to: 0.3; duration: 500 }
                    PropertyAnimation { to: 1.0; duration: 500 }
                }
            }

            Text {
                text: "ACTIVE"
                font.family: "Consolas"
                font.pixelSize: 8
                color: "#aaaaaa"
            }
        }

        // Service status
        Row {
            spacing: 6
            width: parent.width - 16

            Text {
                text: "NET"
                font.family: "Consolas"
                font.pixelSize: 8
                color: "#888888"
                width: 30
            }

            Row {
                spacing: 3

                Rectangle {
                    width: 4
                    height: 4
                    radius: 0
                    color: "#888888"
                }

                Rectangle {
                    width: 4
                    height: 4
                    radius: 0
                    color: "#888888"
                }

                Rectangle {
                    width: 4
                    height: 4
                    radius: 0
                    color: "#888888"
                }
            }

            Text {
                text: "ONLINE"
                font.family: "Consolas"
                font.pixelSize: 8
                color: "#aaaaaa"
            }
        }
    }

    function updateStatus(status) {
        statusData = status || {}
    }
}
