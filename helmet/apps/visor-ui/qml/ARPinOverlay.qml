import QtQuick 2.15

/**
 * AR Pin Overlay - Displays spatial pins anchored in 3D space
 * Pins are placed with fist gesture and removed with open palm
 */
Item {
    id: root
    anchors.fill: parent

    // Ensure this overlay is always on top and visible
    z: 1000
    visible: true

    // List of AR pins with screen positions
    property var pins: []


    // Repeater to display all pins
    Repeater {
        id: pinRepeater
        model: root.pins

        delegate: Item {
            id: pinDelegate
            x: modelData.x - 60  // Center the pin marker
            y: modelData.y - 60
            width: 120
            height: 120
            z: 100  // Ensure pin is on top

            // Outer glow ring
            Rectangle {
                anchors.centerIn: parent
                width: 100
                height: 100
                radius: 50
                color: "transparent"
                border.color: modelData.color || "#00ff00"
                border.width: 4
                opacity: 0.3
            }

            // Middle ring
            Rectangle {
                anchors.centerIn: parent
                width: 70
                height: 70
                radius: 35
                color: "transparent"
                border.color: modelData.color || "#00ff00"
                border.width: 3
                opacity: 0.5
            }

            // Pin marker (main circle)
            Rectangle {
                id: pinMarker
                anchors.centerIn: parent
                width: 50
                height: 50
                radius: 25
                color: modelData.color || "#00ff00"
                border.color: "white"
                border.width: 4
                opacity: 0.9

                // Pulsing animation
                SequentialAnimation on scale {
                    running: true
                    loops: Animation.Infinite
                    NumberAnimation {
                        from: 1.0
                        to: 1.15
                        duration: 1000
                        easing.type: Easing.InOutQuad
                    }
                    NumberAnimation {
                        from: 1.15
                        to: 1.0
                        duration: 1000
                        easing.type: Easing.InOutQuad
                    }
                }
            }

            // Pin label (if provided)
            Rectangle {
                id: labelBackground
                anchors.top: pinMarker.bottom
                anchors.topMargin: 12
                anchors.horizontalCenter: pinMarker.horizontalCenter
                width: labelText.width + 16
                height: labelText.height + 8
                color: "#DD000000"
                radius: 6
                visible: modelData.label && modelData.label !== ""
                z: 101

                Text {
                    id: labelText
                    anchors.centerIn: parent
                    text: modelData.label || ""
                    color: "white"
                    font.pixelSize: 18
                    font.bold: true
                }
            }

            // Entrance animation
            ParallelAnimation {
                running: true
                NumberAnimation {
                    target: pinDelegate
                    property: "scale"
                    from: 0
                    to: 1
                    duration: 300
                    easing.type: Easing.OutBack
                }
                NumberAnimation {
                    target: pinDelegate
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: 300
                }
            }
        }
    }

    // Debug info (top-left corner) - ALWAYS visible for debugging
    Rectangle {
        id: debugInfo
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 10
        width: debugText.width + 20
        height: debugText.height + 12
        color: "#EE000000"
        radius: 6
        visible: true  // Always show for debugging
        z: 9999
        border.color: "lime"
        border.width: 1

        Text {
            id: debugText
            anchors.centerIn: parent
            text: "AR: " + root.pins.length + " pins | X=add Z=clear"
            color: "lime"
            font.pixelSize: 16
            font.family: "monospace"
            font.bold: true
        }
    }

    // Function to update pins from Python backend
    function updatePins(newPins) {
        root.pins = newPins
    }

}
