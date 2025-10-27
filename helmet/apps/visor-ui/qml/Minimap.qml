import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    width: 300
    height: 300

    property bool gpsActive: false
    property real latitude: 0.0
    property real longitude: 0.0
    property real altitude: 0.0
    property real heading: 0.0
    property int satellites: 0
    property int fixQuality: 0
    property real speed: 0.0  // km/h
    property string positioningMethod: "none"  // "gps", "wifi", "none"
    property real accuracy: 0.0  // Accuracy in meters

    // Zoom controls
    property int zoomLevel: 17

    // Minimap image source
    property string minimapSource: ""

    // Border color based on positioning method
    property color borderColor: {
        switch(positioningMethod) {
            case "gps": return "#4CAF50"      // Green - GPS
            case "wifi": return "#FFC107"     // Amber/Yellow - Wi-Fi
            default: return "#FF5252"         // Red - No position
        }
    }

    // Background circle with border
    Rectangle {
        id: background
        anchors.fill: parent
        radius: width / 2
        color: "#282828CC"  // Dark gray with transparency
        border.color: root.borderColor
        border.width: 3
        opacity: 0.95
        clip: true

        // Minimap image (rendered by MinimapController)
        Image {
            id: minimapImage
            anchors.fill: parent
            anchors.margins: 3
            source: minimapSource
            cache: false
            asynchronous: true
            fillMode: Image.PreserveAspectCrop

            // Simple circular clipping using layer
            layer.enabled: true
            layer.smooth: true
        }
    }

    // Status indicator (top of minimap) - shows positioning method
    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 15
        anchors.horizontalCenter: parent.horizontalCenter
        width: statusText.width + 12
        height: 20
        radius: 10
        color: "#CC000000"
        visible: true

        Text {
            id: statusText
            anchors.centerIn: parent
            text: {
                switch(root.positioningMethod) {
                    case "gps": return satellites + " SATS"
                    case "wifi": return "Wi-Fi ±" + Math.round(accuracy) + "m"
                    default: return "NO GPS"
                }
            }
            color: root.borderColor
            font.pixelSize: 11
            font.bold: true
            font.family: "Monospace"
        }
    }

    // Speed indicator (bottom of minimap)
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 15
        anchors.horizontalCenter: parent.horizontalCenter
        width: speedText.width + 12
        height: 20
        radius: 10
        color: "#CC000000"
        visible: gpsActive && speed > 0

        Text {
            id: speedText
            anchors.centerIn: parent
            text: Math.round(speed) + " km/h"
            color: "#FFFFFF"
            font.pixelSize: 11
            font.bold: true
            font.family: "Monospace"
        }
    }

    // Compass indicator (North)
    Item {
        id: compassNorth
        anchors.top: parent.top
        anchors.topMargin: 40
        anchors.horizontalCenter: parent.horizontalCenter
        width: 20
        height: 30
        visible: gpsActive

        // North triangle
        Canvas {
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();

                // Draw triangle
                ctx.fillStyle = "#FF5252";
                ctx.strokeStyle = "#FFFFFF";
                ctx.lineWidth = 1;

                ctx.beginPath();
                ctx.moveTo(width / 2, 0);  // Top point
                ctx.lineTo(0, height);      // Bottom left
                ctx.lineTo(width, height);  // Bottom right
                ctx.closePath();
                ctx.fill();
                ctx.stroke();

                // Draw 'N'
                ctx.fillStyle = "#FFFFFF";
                ctx.font = "bold 10px Arial";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("N", width / 2, height * 0.7);
            }
        }

        // Rotate based on heading (inverse of map rotation)
        rotation: -heading
    }

    // Zoom controls
    Column {
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        spacing: 5

        // Zoom in button
        Rectangle {
            width: 30
            height: 30
            radius: 15
            color: "#CC000000"
            border.color: "#FFFFFF"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "+"
                color: "#FFFFFF"
                font.pixelSize: 18
                font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (root.zoomLevel < 19) {
                        root.zoomLevel++;
                        if (visorApp.minimap_controller) {
                            visorApp.minimap_controller.adjustZoom(1);
                        }
                    }
                }
            }
        }

        // Zoom out button
        Rectangle {
            width: 30
            height: 30
            radius: 15
            color: "#CC000000"
            border.color: "#FFFFFF"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "-"
                color: "#FFFFFF"
                font.pixelSize: 18
                font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (root.zoomLevel > 10) {
                        root.zoomLevel--;
                        if (visorApp.minimap_controller) {
                            visorApp.minimap_controller.adjustZoom(-1);
                        }
                    }
                }
            }
        }
    }

    // Coordinate display (for debugging, can be removed)
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.margins: 5
        width: coordText.width + 8
        height: coordText.height + 4
        radius: 3
        color: "#CC000000"
        visible: false  // Set to true to show coordinates

        Text {
            id: coordText
            anchors.centerIn: parent
            text: latitude.toFixed(6) + ", " + longitude.toFixed(6)
            color: "#FFFFFF"
            font.pixelSize: 8
            font.family: "Monospace"
        }
    }

    // Connect to visorApp signals
    Connections {
        target: visorApp

        // GPS position updates
        function onGpsPositionUpdated(lat, lon, alt, hdg) {
            root.latitude = lat;
            root.longitude = lon;
            root.altitude = alt;
            root.heading = hdg;
        }

        // GPS status updates
        function onGpsStatusUpdated(status) {
            root.gpsActive = status.valid;
            root.satellites = status.satellites || 0;
            root.fixQuality = status.fix_quality || 0;
            root.speed = status.speed || 0.0;
            root.positioningMethod = status.positioning_method || "none";
            root.accuracy = status.accuracy || 0.0;
        }

        // Minimap image updates
        function onMinimapUpdated(imagePath) {
            root.minimapSource = imagePath;
        }
    }

    // Pulsing animation when no GPS
    SequentialAnimation on opacity {
        running: !gpsActive
        loops: Animation.Infinite

        NumberAnimation {
            from: 0.7
            to: 1.0
            duration: 1000
            easing.type: Easing.InOutQuad
        }
        NumberAnimation {
            from: 1.0
            to: 0.7
            duration: 1000
            easing.type: Easing.InOutQuad
        }
    }
}
