import QtQuick 2.15
import QtQuick.Controls 2.15

// Modern JARVIS-style detection overlay for fullscreen video
Item {
    id: detectionOverlay

    property var detections: []
    property string sceneAnalysis: ""
    property var smoothedDetections: []
    property var detectionHistory: ({})

    // Smooth detection updates to prevent flickering
    Timer {
        id: smoothingTimer
        interval: 100
        repeat: true
        running: visible
        onTriggered: {
            smoothDetections()
        }
    }

    // Compact object list panel (right side, below minimal status)
    Rectangle {
        id: objectListPanel
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 20
        anchors.topMargin: 60  // Below minimal status
        width: 220
        height: Math.min(400, objectList.implicitHeight + 30)
        color: "#0d0d0d"
        border.color: "#555555"
        border.width: 1
        radius: 0
        opacity: 0.9
        visible: detections.length > 0

        Column {
            id: objectList
            anchors.fill: parent
            anchors.margins: 15
            spacing: 10

            // Header
            Row {
                width: parent.width
                spacing: 10

                Rectangle {
                    width: 2
                    height: 16
                    color: "#888888"
                    radius: 0
                }

                Text {
                    text: "TARGETS"
                    font.family: "Consolas"
                    font.pixelSize: 10
                    font.weight: 75
                    color: "#aaaaaa"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: "[" + detections.length.toString() + "]"
                    font.family: "Consolas"
                    font.pixelSize: 10
                    font.weight: 75
                    color: "#cccccc"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Object count summary by type
            Column {
                width: parent.width
                spacing: 6

                Repeater {
                    model: _getObjectSummary()

                    Row {
                        width: parent.width
                        spacing: 8

                        Rectangle {
                            width: 4
                            height: 4
                            radius: 0
                            color: "#888888"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: modelData.label.toUpperCase()
                            font.family: "Consolas"
                            font.pixelSize: 9
                            color: "#aaaaaa"
                            width: 100
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Rectangle {
                            width: 28
                            height: 14
                            color: "#1a1a1a"
                            border.color: "#444444"
                            border.width: 1
                            radius: 0
                            anchors.verticalCenter: parent.verticalCenter

                            Text {
                                text: "×" + modelData.count
                                font.family: "Consolas"
                                font.pixelSize: 8
                                font.weight: 75
                                color: "#cccccc"
                                anchors.centerIn: parent
                            }
                        }

                        Text {
                            text: Math.round(modelData.avgConfidence * 100) + "%"
                            font.family: "Consolas"
                            font.pixelSize: 8
                            color: modelData.avgConfidence > 0.7 ? "#999999" : "#666666"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }

    // Scene analysis panel (bottom-center)
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 40
        width: Math.max(300, sceneText.implicitWidth + 40)
        height: 40
        color: "#0d0d0d"
        border.color: "#555555"
        border.width: 1
        radius: 0
        opacity: 0.9
        visible: sceneAnalysis !== ""

        Row {
            anchors.centerIn: parent
            spacing: 12

            Rectangle {
                width: 4
                height: 16
                radius: 0
                color: "#888888"
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                id: sceneText
                text: sceneAnalysis.toUpperCase()
                font.family: "Consolas"
                font.pixelSize: 11
                color: "#aaaaaa"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // Detection boxes overlay
    Repeater {
        model: smoothedDetections

        Item {
            id: detectionBox
            // Convert normalized coordinates to screen coordinates
            x: modelData.x * parent.width
            y: modelData.y * parent.height
            width: modelData.width * parent.width
            height: modelData.height * parent.height

            // Smooth position changes
            Behavior on x { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
            Behavior on y { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
            Behavior on width { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }
            Behavior on height { NumberAnimation { duration: 100; easing.type: Easing.OutQuad } }

            // Main box
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.color: "#888888"
                border.width: 2
                radius: 0
                opacity: 0.7
            }

            // Corner brackets (military style)
            Repeater {
                model: 4
                Rectangle {
                    width: index % 2 === 0 ? 20 : 2
                    height: index % 2 === 0 ? 2 : 20
                    color: "#cccccc"
                    x: index === 0 || index === 3 ? 0 : parent.width - width
                    y: index < 2 ? 0 : parent.height - height
                }
            }

            // Label bar (top)
            Rectangle {
                anchors.bottom: parent.top
                anchors.left: parent.left
                anchors.bottomMargin: 2
                width: labelText.implicitWidth + 10
                height: 16
                color: "#1a1a1a"
                border.color: "#666666"
                border.width: 1
                radius: 0
                opacity: 0.9

                Text {
                    id: labelText
                    anchors.centerIn: parent
                    text: modelData.label.toUpperCase()
                    font.family: "Consolas"
                    font.pixelSize: 9
                    font.weight: 75
                    color: "#cccccc"
                }
            }

            // Confidence bar (bottom right)
            Rectangle {
                anchors.top: parent.bottom
                anchors.right: parent.right
                anchors.topMargin: 2
                width: 40
                height: 6
                color: "#1a1a1a"
                border.color: "#666666"
                border.width: 1
                radius: 0

                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 1
                    width: (parent.width - 2) * modelData.confidence
                    height: parent.height - 2
                    color: "#888888"
                }
            }

            // Crosshair center (for high confidence targets)
            Rectangle {
                visible: modelData.confidence > 0.8
                anchors.centerIn: parent
                width: 12
                height: 2
                color: "#999999"
                opacity: 0.7

                Rectangle {
                    width: 2
                    height: 12
                    color: "#999999"
                    anchors.centerIn: parent
                }
            }
        }
    }

    // Functions
    function updateDetections(newDetections) {
        detections = newDetections || []

        // Update scene analysis if we have detections
        if (detections.length > 0) {
            sceneAnalysis = _generateSceneAnalysis(detections)
        } else {
            sceneAnalysis = ""
        }
    }

    function smoothDetections() {
        // Smooth detection transitions to prevent flicker
        var current = {}
        var result = []

        // Index current detections by label+position
        for (var i = 0; i < detections.length; i++) {
            var det = detections[i]
            var key = det.label + "_" + Math.round(det.x * 10) + "_" + Math.round(det.y * 10)
            current[key] = det
        }

        // Update history with decay
        for (var histKey in detectionHistory) {
            if (current[histKey]) {
                // Still present, update position with smoothing
                var curr = current[histKey]
                var hist = detectionHistory[histKey]
                detectionHistory[histKey] = {
                    x: hist.x * 0.7 + curr.x * 0.3,
                    y: hist.y * 0.7 + curr.y * 0.3,
                    width: hist.width * 0.7 + curr.width * 0.3,
                    height: hist.height * 0.7 + curr.height * 0.3,
                    confidence: curr.confidence,
                    label: curr.label,
                    age: 0
                }
            } else {
                // Not present, age out
                detectionHistory[histKey].age++
                if (detectionHistory[histKey].age < 3) {
                    // Keep for a few frames to smooth disappearance
                    detectionHistory[histKey].confidence *= 0.7
                } else {
                    delete detectionHistory[histKey]
                }
            }
        }

        // Add new detections
        for (var newKey in current) {
            if (!detectionHistory[newKey]) {
                var newDet = current[newKey]
                detectionHistory[newKey] = {
                    x: newDet.x,
                    y: newDet.y,
                    width: newDet.width,
                    height: newDet.height,
                    confidence: newDet.confidence,
                    label: newDet.label,
                    age: 0
                }
            }
        }

        // Build output array
        for (var outKey in detectionHistory) {
            result.push(detectionHistory[outKey])
        }

        smoothedDetections = result
    }

    function _getObjectSummary() {
        // Group detections by label and count them
        var summary = {}
        for (var i = 0; i < detections.length; i++) {
            var label = detections[i].label
            if (!summary[label]) {
                summary[label] = {
                    label: label,
                    count: 0,
                    totalConfidence: 0
                }
            }
            summary[label].count++
            summary[label].totalConfidence += detections[i].confidence
        }

        // Convert to array and calculate averages
        var result = []
        for (var key in summary) {
            result.push({
                label: summary[key].label,
                count: summary[key].count,
                avgConfidence: summary[key].totalConfidence / summary[key].count
            })
        }

        // Sort by count descending
        result.sort(function(a, b) { return b.count - a.count })
        return result
    }

    function _getObjectColor(label) {
        var colors = {
            "person": "#FF6B6B",
            "car": "#4ECDC4",
            "truck": "#45B7D1",
            "motorcycle": "#9C27B0",
            "bicycle": "#96CEB4",
            "traffic light": "#FECA57",
            "stop sign": "#FF5722",
            "laptop": "#00BCD4",
            "keyboard": "#8BC34A",
            "mouse": "#607D8B",
            "cell phone": "#E91E63",
            "book": "#795548",
            "cup": "#FF9800",
            "bottle": "#2196F3"
        }
        return colors[label] || "#FFFFFF"
    }


    function _generateSceneAnalysis(detections) {
        var personCount = detections.filter(d => d.label === "person").length
        var vehicleCount = detections.filter(d => ["car", "truck", "motorcycle", "bus"].includes(d.label)).length
        var totalObjects = detections.length

        if (personCount > 0) {
            if (personCount === 1) {
                return "Person detected - maintain spatial awareness"
            } else {
                return personCount + " people in view - crowded environment"
            }
        } else if (vehicleCount > 0) {
            return vehicleCount + " vehicle(s) detected - traffic environment"
        } else if (totalObjects > 5) {
            return "Complex scene - " + totalObjects + " objects detected"
        } else if (detections.some(d => ["laptop", "keyboard", "monitor"].includes(d.label))) {
            return "Workspace environment - productivity setup detected"
        } else if (totalObjects > 0) {
            return totalObjects + " object(s) in view - monitoring surroundings"
        }
        return "Clear environment - no objects detected"
    }

    // Smooth appearance animation
    opacity: 0
    PropertyAnimation on opacity {
        running: visible
        to: 1.0
        duration: 400
        easing.type: Easing.OutQuad
    }
}