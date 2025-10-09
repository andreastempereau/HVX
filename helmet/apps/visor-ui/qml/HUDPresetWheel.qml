import QtQuick 2.15

Item {
    id: root
    anchors.fill: parent
    visible: wheelVisible  // Always present, visibility controlled by gesture

    // Gesture state
    property real headingAngle: 0.0
    property real pitchAngle: 0.0
    property real rollAngle: 0.0
    property bool wheelVisible: false
    property int selectedPreset: -1  // -1 = none, 0=full HUD, 1=clear, 2=custom
    property int currentPreset: 0  // Start with full HUD (0)
    property bool selectionMade: false
    property real baseHeading: 0.0  // Heading when wheel first appears

    // Thresholds
    property real pitchDownThreshold: -50.0  // degrees down to show wheel (negative = looking down)
    property real pitchResetThreshold: -10.0  // degrees to reset (looking up from down position)
    property real pitchTopSelectThreshold: -20.0  // degrees to select top preset (looking up while wheel is open)
    property real headingLeftThreshold: 20.0  // degrees right (positive) to select left preset
    property real headingRightThreshold: -20.0  // degrees left (negative) to select right preset

    signal presetChanged(int presetIndex)

    // Update function called when orientation changes
    function updateOrientation(heading, roll, pitch) {
        headingAngle = heading
        rollAngle = roll
        pitchAngle = pitch

        // Reset when looking up past reset threshold
        if (pitch > pitchResetThreshold) {
            if (wheelVisible || selectionMade) {
                wheelVisible = false
                selectionMade = false
            }
            return
        }

        // Show wheel when looking down past threshold (pitch is negative when looking down)
        if (pitch < pitchDownThreshold && !selectionMade) {
            if (!wheelVisible) {
                wheelVisible = true
                baseHeading = heading  // Capture initial heading
                selectedPreset = -1  // Reset selection
                console.log("Wheel opened - base heading: " + baseHeading.toFixed(1) + "°")
            }

            // Calculate heading delta from base
            var headingDelta = heading - baseHeading

            // Handle 360-degree wraparound
            if (headingDelta > 180) {
                headingDelta -= 360
            } else if (headingDelta < -180) {
                headingDelta += 360
            }

            // Determine selected preset based on pitch AND heading
            // Top preset requires looking back up (pitch > -20)
            if (pitch > pitchTopSelectThreshold) {
                selectedPreset = 0  // Top preset (Full HUD) - looked up
            } else if (headingDelta > headingLeftThreshold) {
                selectedPreset = 2  // Left preset (turned right to +20)
            } else if (headingDelta < headingRightThreshold) {
                selectedPreset = 1  // Right preset (turned left to -20 - clear)
            } else {
                // If still looking down and centered, no selection
                selectedPreset = -1
            }
        }
    }

    // Apply preset selection
    function confirmSelection() {
        if (wheelVisible) {
            if (selectedPreset !== currentPreset) {
                currentPreset = selectedPreset
                presetChanged(selectedPreset)
            }

            // Always mark as selected and hide wheel
            selectionMade = true
            wheelVisible = false
            console.log("Selection confirmed: preset " + selectedPreset)
        }
    }

    // Auto-confirm when dwelling on a preset
    Timer {
        id: selectionTimer
        interval: 250  // 250ms dwell time
        running: wheelVisible && selectedPreset >= 0  // Only run when a valid preset is selected
        onTriggered: confirmSelection()
    }

    // Semi-transparent background
    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: 0.3
    }

    // Half-circle preset wheel at bottom
    Item {
        id: presetWheel
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 50
        width: 600
        height: 300

        opacity: wheelVisible ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }

        // Top preset - Current HUD
        Item {
            id: topPreset
            x: parent.width / 2 - 100
            y: 0
            width: 200
            height: 100

            Rectangle {
                anchors.fill: parent
                color: selectedPreset === 0 ? "#E0E0E0" : "#404040"
                opacity: selectedPreset === 0 ? 0.95 : 0.8
                border.color: currentPreset === 0 ? "#FFFFFF" : "#808080"
                border.width: 3
                radius: 10

                Behavior on color {
                    ColorAnimation { duration: 150 }
                }

                Behavior on opacity {
                    NumberAnimation { duration: 150 }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 5

                    // Dashboard icon
                    Canvas {
                        width: 40
                        height: 40
                        anchors.horizontalCenter: parent.horizontalCenter
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.strokeStyle = "white"
                            ctx.fillStyle = "white"
                            ctx.lineWidth = 2

                            // Draw grid icon (3x3)
                            for (var i = 0; i < 3; i++) {
                                for (var j = 0; j < 3; j++) {
                                    ctx.fillRect(i * 14, j * 14, 10, 10)
                                }
                            }
                        }
                    }

                    Text {
                        text: "Full HUD"
                        color: "white"
                        font.pixelSize: 16
                        font.bold: true
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }

        // Right preset - Clear Display
        Item {
            id: rightPreset
            x: parent.width - 220
            y: 150
            width: 200
            height: 100

            Rectangle {
                anchors.fill: parent
                color: selectedPreset === 1 ? "#E0E0E0" : "#404040"
                opacity: selectedPreset === 1 ? 0.95 : 0.8
                border.color: currentPreset === 1 ? "#FFFFFF" : "#808080"
                border.width: 3
                radius: 10

                Behavior on color {
                    ColorAnimation { duration: 150 }
                }

                Behavior on opacity {
                    NumberAnimation { duration: 150 }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 5

                    // Circle icon (clear/minimal)
                    Canvas {
                        width: 40
                        height: 40
                        anchors.horizontalCenter: parent.horizontalCenter
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.strokeStyle = "white"
                            ctx.lineWidth = 3

                            // Draw circle outline
                            ctx.beginPath()
                            ctx.arc(20, 20, 15, 0, 2 * Math.PI)
                            ctx.stroke()
                        }
                    }

                    Text {
                        text: "Clear"
                        color: "white"
                        font.pixelSize: 16
                        font.bold: true
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }

        // Left preset - Placeholder
        Item {
            id: leftPreset
            x: 20
            y: 150
            width: 200
            height: 100

            Rectangle {
                anchors.fill: parent
                color: selectedPreset === 2 ? "#E0E0E0" : "#404040"
                opacity: selectedPreset === 2 ? 0.95 : 0.8
                border.color: currentPreset === 2 ? "#FFFFFF" : "#808080"
                border.width: 3
                radius: 10

                Behavior on color {
                    ColorAnimation { duration: 150 }
                }

                Behavior on opacity {
                    NumberAnimation { duration: 150 }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 5

                    // Star icon
                    Canvas {
                        width: 40
                        height: 40
                        anchors.horizontalCenter: parent.horizontalCenter
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.strokeStyle = "white"
                            ctx.fillStyle = "white"
                            ctx.lineWidth = 2

                            // Draw star
                            ctx.beginPath()
                            for (var i = 0; i < 5; i++) {
                                var angle = (i * 4 * Math.PI / 5) - Math.PI / 2
                                var radius = (i % 2 === 0) ? 15 : 7
                                var x = 20 + radius * Math.cos(angle)
                                var y = 20 + radius * Math.sin(angle)
                                if (i === 0) ctx.moveTo(x, y)
                                else ctx.lineTo(x, y)
                            }
                            ctx.closePath()
                            ctx.fill()
                        }
                    }

                    Text {
                        text: "Custom"
                        color: "white"
                        font.pixelSize: 16
                        font.bold: true
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }

        // Connecting arc (visual only)
        Canvas {
            id: arcCanvas
            anchors.fill: parent

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()

                ctx.strokeStyle = "#808080"
                ctx.lineWidth = 2

                // Draw semi-circle arc
                ctx.beginPath()
                ctx.arc(width/2, height, width/2 - 50, Math.PI, 2*Math.PI, false)
                ctx.stroke()
            }
        }

        // Selection indicator
        Text {
            anchors.top: parent.bottom
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            text: selectedPreset === 0 ? "◄ Full HUD ►" :
                  selectedPreset === 1 ? "◄ Clear Display ►" :
                  "◄ Custom ►"
            color: "#FFFFFF"
            font.pixelSize: 20
            font.bold: true
        }
    }

    // Debug info
    Text {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 20
        text: {
            var delta = headingAngle - baseHeading
            if (delta > 180) delta -= 360
            else if (delta < -180) delta += 360
            return "Pitch: " + pitchAngle.toFixed(1) + "° | Heading Δ: " + delta.toFixed(1) + "°"
        }
        color: "white"
        font.pixelSize: 14
        visible: wheelVisible
        opacity: 0.7
    }
}
