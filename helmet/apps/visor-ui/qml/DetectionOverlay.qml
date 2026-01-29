import QtQuick 2.15

// Iron Man Mark 2 HUD targeting overlay (performance optimized)
Item {
    id: detectionOverlay

    property var detections: []
    property var targetStates: ({})
    property int nextTargetId: 0

    readonly property color hudColor: "#00D4FF"
    readonly property color hudColorDim: "#0088AA"
    readonly property color hudColorBright: "#66EEFF"

    Timer {
        id: trackingTimer
        interval: 60
        repeat: true
        running: visible
        onTriggered: updateTargetTracking()
    }

    Repeater {
        id: targetRepeater
        model: Object.keys(targetStates).length

        Item {
            id: targetItem

            property var targetData: {
                var keys = Object.keys(targetStates)
                return index < keys.length ? targetStates[keys[index]] : null
            }

            visible: targetData !== null

            property real headCenterX: targetData ? targetData.headX * detectionOverlay.width : 0
            property real headCenterY: targetData ? targetData.headY * detectionOverlay.height : 0

            property real baseRadius: {
                if (!targetData) return 80
                var distance = targetData.distance || 2.0
                return Math.max(60, Math.min(200, 200 / Math.sqrt(distance)))
            }

            property real phase: targetData ? targetData.phase : 0
            property real pulseAmount: 1.0

            SequentialAnimation on pulseAmount {
                running: phase >= 1.0
                loops: Animation.Infinite
                NumberAnimation { to: 1.02; duration: 1500; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
            }

            property real currentRadius: phase < 1.0 ? baseRadius * (0.2 + 0.8 * phase) : baseRadius * pulseAmount

            Behavior on headCenterX { NumberAnimation { duration: 50 } }
            Behavior on headCenterY { NumberAnimation { duration: 50 } }
            Behavior on baseRadius { NumberAnimation { duration: 120 } }

            // === SPINNING RINGS (lock-on phase) ===

            // Ring 1 - Inner fast spin
            Item {
                x: headCenterX - currentRadius * 0.35
                y: headCenterY - currentRadius * 0.35
                width: currentRadius * 0.7
                height: width
                opacity: phase < 0.85 ? 1.0 - phase : 0
                visible: opacity > 0

                NumberAnimation on rotation {
                    running: parent.visible
                    loops: Animation.Infinite
                    from: 0; to: 360; duration: 500
                }

                Repeater {
                    model: 3
                    Rectangle {
                        x: parent.width / 2 - 1.5
                        y: 0
                        width: 3; height: parent.height * 0.22
                        radius: 1.5; color: hudColor
                        transform: Rotation { origin.x: 1.5; origin.y: parent.height / 2; angle: index * 120 }
                    }
                }
            }

            // Ring 2 - Middle counter-spin
            Item {
                x: headCenterX - currentRadius * 0.5
                y: headCenterY - currentRadius * 0.5
                width: currentRadius
                height: width
                opacity: phase < 0.9 ? (1.0 - phase) * 0.7 : 0
                visible: opacity > 0

                NumberAnimation on rotation {
                    running: parent.visible
                    loops: Animation.Infinite
                    from: 360; to: 0; duration: 700
                }

                Repeater {
                    model: 4
                    Rectangle {
                        x: parent.width / 2 - 2
                        y: 2
                        width: 4; height: parent.height * 0.15
                        radius: 2; color: hudColorDim
                        transform: Rotation { origin.x: 2; origin.y: parent.height / 2 - 2; angle: index * 90 }
                    }
                }
            }

            // Ring 3 - Outer slow spin
            Item {
                x: headCenterX - currentRadius * 0.7
                y: headCenterY - currentRadius * 0.7
                width: currentRadius * 1.4
                height: width
                opacity: phase < 1.0 ? (1.0 - phase) * 0.5 : 0
                visible: opacity > 0

                NumberAnimation on rotation {
                    running: parent.visible
                    loops: Animation.Infinite
                    from: 0; to: 360; duration: 900
                }

                Repeater {
                    model: 6
                    Rectangle {
                        x: parent.width / 2 - 1
                        y: 3
                        width: 2; height: parent.height * 0.1
                        radius: 1; color: hudColor
                        transform: Rotation { origin.x: 1; origin.y: parent.height / 2 - 3; angle: index * 60 }
                    }
                }
            }

            // === MAIN CIRCLE (locked state) ===
            Item {
                id: mainCircle
                x: headCenterX - currentRadius * 1.1
                y: headCenterY - currentRadius * 1.1
                width: currentRadius * 2.2
                height: width
                opacity: phase > 0.3 ? Math.min(1.0, (phase - 0.3) * 1.5) : 0
                visible: opacity > 0

                // Outer ring
                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: "transparent"
                    border.width: 2; border.color: hudColor
                }

                // Inner ring
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 0.88; height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 1; border.color: hudColorDim
                    opacity: 0.4
                }

                // Rotating ticks
                Item {
                    anchors.fill: parent
                    NumberAnimation on rotation {
                        running: mainCircle.visible
                        loops: Animation.Infinite
                        from: 0; to: 360; duration: 12000
                    }

                    Repeater {
                        model: 8
                        Rectangle {
                            x: parent.width / 2 - 1.5
                            y: -3
                            width: 3; height: 12
                            radius: 1.5; color: hudColorBright
                            transform: Rotation { origin.x: 1.5; origin.y: parent.height / 2 + 3; angle: index * 45 }
                        }
                    }
                }

                // Corner accents
                Repeater {
                    model: 4
                    Item {
                        anchors.centerIn: parent
                        width: parent.width; height: parent.height
                        rotation: 45 + index * 90

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: -10
                            width: 4; height: 16; radius: 2; color: hudColor
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.horizontalCenterOffset: -12
                            y: -4
                            width: 4; height: 4; radius: 2; color: hudColorBright
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.horizontalCenterOffset: 12
                            y: -4
                            width: 4; height: 4; radius: 2; color: hudColorBright
                        }
                    }
                }

                // Center crosshair
                Rectangle {
                    anchors.centerIn: parent
                    width: 16; height: 2; radius: 1
                    color: hudColor; opacity: 0.3
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 2; height: 16; radius: 1
                    color: hudColor; opacity: 0.3
                }
            }

            // Distance label
            Rectangle {
                visible: phase > 0.9 && targetData && targetData.distance
                x: headCenterX + currentRadius * 0.8
                y: headCenterY + currentRadius * 0.65
                width: distText.implicitWidth + 14
                height: 20
                color: "#0a0a0a"; border.color: hudColorDim; border.width: 1; radius: 2

                Text {
                    id: distText
                    anchors.centerIn: parent
                    text: targetData && targetData.distance ? targetData.distance.toFixed(1) + "m" : ""
                    font.family: "Consolas"; font.pixelSize: 11; font.bold: true
                    color: hudColor
                }
            }
        }
    }

    // Tracking counter
    Rectangle {
        anchors.top: parent.top; anchors.right: parent.right
        anchors.margins: 20; anchors.topMargin: 60
        width: 100; height: 30
        color: "#0a0a0a"; border.color: hudColorDim; border.width: 1
        visible: Object.keys(targetStates).length > 0

        Row {
            anchors.centerIn: parent; spacing: 6
            Rectangle { width: 3; height: 14; color: hudColor }
            Text {
                text: "TRK " + Object.keys(targetStates).length
                font.family: "Consolas"; font.pixelSize: 12; font.bold: true
                color: hudColor; anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    function updateDetections(newDetections) {
        detections = newDetections || []
    }

    function updateTargetTracking() {
        var now = Date.now()
        var matched = {}
        var newStates = {}

        for (var i = 0; i < detections.length; i++) {
            var det = detections[i]
            if (det.label !== "person") continue

            var headX = det.x + det.width / 2
            var headY = det.y + det.height * 0.1

            var bestMatch = null, bestDist = 0.12

            for (var targetId in targetStates) {
                if (matched[targetId]) continue
                var target = targetStates[targetId]
                var dist = Math.sqrt(Math.pow(headX - target.headX, 2) + Math.pow(headY - target.headY, 2))
                if (dist < bestDist) { bestDist = dist; bestMatch = targetId }
            }

            if (bestMatch) {
                matched[bestMatch] = true
                var existing = targetStates[bestMatch]
                newStates[bestMatch] = {
                    headX: headX, headY: headY,
                    distance: det.distance || existing.distance,
                    phase: Math.min(1.0, existing.phase + 0.07),
                    lastSeen: now, id: bestMatch
                }
            } else {
                var newId = "t" + nextTargetId++
                newStates[newId] = {
                    headX: headX, headY: headY,
                    distance: det.distance || null,
                    phase: 0.0, lastSeen: now, id: newId
                }
            }
        }

        for (var oldId in targetStates) {
            if (!newStates[oldId] && now - targetStates[oldId].lastSeen < 350) {
                newStates[oldId] = targetStates[oldId]
            }
        }

        targetStates = newStates
    }
}
