import QtQuick 2.15

Item {
    id: root
    anchors.fill: parent

    // Orientation data - updated from Python
    property real headingAngle: 0.0
    property real rollAngle: 0.0
    property real pitchAngle: 0.0

    // Crosshair styling
    property color lineColor: "#808080"  // Light gray
    property int lineWidth: 3
    property int gapSize: 100  // Gap in the middle

    // Horizontal line that rotates with roll (split into two parts with gap)
    Item {
        id: horizontalLine
        anchors.centerIn: parent
        width: parent.width * 0.3  // 30% of screen width
        height: lineWidth

        // Rotate based on roll angle (tilt head left/right)
        // NO animation - instant update!
        rotation: rollAngle

        // Left half of crosshair
        Rectangle {
            width: (parent.width - gapSize) / 2
            height: lineWidth
            color: lineColor
            anchors.right: parent.horizontalCenter
            anchors.rightMargin: gapSize / 2
            anchors.verticalCenter: parent.verticalCenter

            // Tick mark on left end
            Rectangle {
                width: 2
                height: 12
                color: lineColor
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // Right half of crosshair
        Rectangle {
            width: (parent.width - gapSize) / 2
            height: lineWidth
            color: lineColor
            anchors.left: parent.horizontalCenter
            anchors.leftMargin: gapSize / 2
            anchors.verticalCenter: parent.verticalCenter

            // Tick mark on right end
            Rectangle {
                width: 2
                height: 12
                color: lineColor
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // Optional: Add pitch indicator (vertical offset based on pitch)
    // Uncomment to enable pitch-based vertical movement
    /*
    Item {
        id: pitchIndicator
        anchors.centerIn: parent
        y: pitchAngle * 2  // Scale factor for pitch sensitivity

        Behavior on y {
            SmoothedAnimation {
                velocity: 100
                duration: 50
            }
        }

        // Small vertical line to show pitch
        Rectangle {
            width: 2
            height: 30
            color: lineColor
            opacity: 0.5
            anchors.horizontalCenter: parent.horizontalCenter
        }
    }
    */

    // Debug text (can be removed later)
    Text {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 10
        text: "Roll: " + rollAngle.toFixed(1) + "° | Pitch: " + pitchAngle.toFixed(1) + "°"
        color: lineColor
        font.pixelSize: 16
        font.bold: true
        opacity: 0.9
        style: Text.Outline
        styleColor: "black"
    }
}
