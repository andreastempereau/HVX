import QtQuick 2.15
import QtQuick.Controls 2.15

// Rearview mirror widget - small camera preview at top center
Item {
    id: rearviewMirror
    anchors.top: parent.top
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.topMargin: 20
    width: 400
    height: 300
    visible: true
    opacity: 0.95
    z: 1000

    // Glass background
    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
        opacity: 0.6
        radius: 12
    }

    // Border with gradient
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        radius: 12
        border.width: 2
        border.color: "#00d4ff"
        opacity: 0.6
    }

    // Video feed
    Image {
        id: rearCamera
        anchors.fill: parent
        anchors.margins: 4
        fillMode: Image.PreserveAspectCrop
        cache: false
        asynchronous: false
        smooth: true
        mipmap: true
    }

    function updateFrame(framePath) {
        // Force refresh by updating source
        rearCamera.source = ""
        rearCamera.source = framePath
    }

    // Label
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 8
        width: labelText.width + 16
        height: 20
        radius: 10
        color: "#0a0a0a"
        opacity: 0.8

        Text {
            id: labelText
            anchors.centerIn: parent
            text: "REAR VIEW"
            font.family: "SF Pro Display"
            font.pixelSize: 10
            font.weight: 65
            color: "#00d4ff"
        }
    }
}
