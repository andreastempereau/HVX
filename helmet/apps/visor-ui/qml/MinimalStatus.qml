import QtQuick 2.15
import QtQuick.Controls 2.15

// Minimal persistent battery/power indicator - iOS 26 Military Glass style
Item {
    id: minimalStatus
    width: 280
    height: 60

    property var statusData: ({})

    // Glass panel background
    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
        opacity: 0.15
        radius: 16

        // Gradient overlay
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#20ffffff" }
                GradientStop { position: 1.0; color: "#05ffffff" }
            }
        }
    }

    // Glass border
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        radius: 16
        border.width: 1.5
        border.color: "#3000ff88"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            radius: parent.radius - 1
            border.width: 1
            border.color: "#15ffffff"
        }
    }

    // Top highlight
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 8
        height: 1
        radius: 0.5
        color: "#25ffffff"
    }

    // Content
    Row {
        anchors.centerIn: parent
        spacing: 12

        // FPS indicator
        Column {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            visible: statusData.show_fps

            Text {
                text: "FPS"
                font.family: "SF Pro Display"
                font.pixelSize: 8
                font.weight: 57
                color: "#00ff88"
                opacity: 0.6
            }

            Text {
                text: (statusData.fps || 0).toFixed(0)
                font.family: "SF Pro Display"
                font.pixelSize: 20
                font.weight: 25
                color: statusData.fps < 20 ? "#ff3b30" : (statusData.fps < 25 ? "#ffcc00" : "#00ff88")
                opacity: 0.9
            }
        }

        // Divider
        Rectangle {
            width: 1
            height: 30
            color: "#ffffff"
            opacity: 0.1
            anchors.verticalCenter: parent.verticalCenter
            visible: statusData.show_fps
        }

        // Temperature indicator
        Column {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            visible: statusData.show_temp

            Text {
                text: "TEMP"
                font.family: "SF Pro Display"
                font.pixelSize: 8
                font.weight: 57
                color: "#00ff88"
                opacity: 0.6
            }

            Text {
                text: Math.round(statusData.temperature || 48) + "°"
                font.family: "SF Pro Display"
                font.pixelSize: 20
                font.weight: 25
                color: statusData.temperature > 70 ? "#ff3b30" : "#ffffff"
                opacity: 0.9
            }
        }

        // Divider
        Rectangle {
            width: 1
            height: 30
            color: "#ffffff"
            opacity: 0.1
            anchors.verticalCenter: parent.verticalCenter
            visible: statusData.show_temp
        }

        // Power indicator
        Column {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter

            Text {
                text: "POWER"
                font.family: "SF Pro Display"
                font.pixelSize: 8
                font.weight: 57
                color: "#00ff88"
                opacity: 0.6
            }

            Row {
                spacing: 6
                Text {
                    text: Math.round(statusData.battery_level || 87)
                    font.family: "SF Pro Display"
                    font.pixelSize: 22
                    font.weight: 25
                    color: statusData.battery_level < 20 ? "#ff3b30" : "#ffffff"
                    opacity: 0.9
                }
                Text {
                    text: "%"
                    font.family: "SF Pro Display"
                    font.pixelSize: 12
                    font.weight: 25
                    color: "#ffffff"
                    opacity: 0.5
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 2
                }
            }
        }
    }

    function updateStatus(status) {
        statusData = status || {}
    }
}
