import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: eyeView

    property int eyeIndex: 0
    property point lensOffset: Qt.point(0, 0)
    property var currentFrame: null
    property var detections: []

    // Video frame display
    Image {
        id: videoFrame
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        cache: false

        // Lens distortion correction (simplified for compatibility)
        transform: Scale {
            xScale: 1.0 + (eyeView.lensOffset.x * 0.1)
            yScale: 1.0 + (eyeView.lensOffset.y * 0.1)
        }
    }

    // MINIMAL crosshair (center reference) - ONLY for aiming
    Rectangle {
        visible: false // Hidden by default, voice-activated
        anchors.centerIn: parent
        width: 12
        height: 1
        color: "white"
        opacity: 0.4
    }

    Rectangle {
        visible: false // Hidden by default, voice-activated
        anchors.centerIn: parent
        width: 1
        height: 12
        color: "white"
        opacity: 0.4
    }

    // Center dot (very minimal)
    Rectangle {
        id: centerDot
        visible: false // Hidden by default
        anchors.centerIn: parent
        width: 2
        height: 2
        radius: 1
        color: "#00BCD4"
        opacity: 0.6
    }

    // Functions
    function updateFrame(framePath) {
        videoFrame.source = framePath
    }

    function updateDetections(newDetections) {
        detections = newDetections || []
    }

    function _getDetectionColor(label) {
        // Color coding for different object types
        var colors = {
            "person": "#ff4444",
            "car": "#44ff44",
            "truck": "#4444ff",
            "bike": "#ffff44",
            "traffic light": "#ff44ff",
            "stop sign": "#ff8844"
        }
        return colors[label] || "#ffffff"
    }
}