import QtQuick 2.15
import QtQuick.Controls 2.15

// Closed captions widget - iOS 26 Military Glass style
Item {
    id: captionWidget
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottomMargin: 20
    anchors.leftMargin: 40
    anchors.rightMargin: 940  // 900px snapshot width + 40px spacing
    height: 80
    visible: false
    opacity: 0
    z: 1500

    property string currentText: ""
    property string finalizedText: ""  // Only finalized captions
    property string interimText: ""     // Current interim caption
    property string targetText: ""      // Text we're typing towards
    property int typingIndex: 0
    property bool isFinal: false
    property bool systemReady: false

    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
    }

    // Typing animation timer
    Timer {
        id: typingTimer
        interval: 10  // 10ms per character for fast typing
        repeat: true
        running: false
        onTriggered: {
            if (typingIndex < targetText.length) {
                currentText = targetText.substring(0, typingIndex + 1)
                typingIndex++
            } else {
                typingTimer.stop()
            }
        }
    }


    // Glass background
    Rectangle {
        id: glassBackground
        anchors.fill: parent
        color: "#1a1a1a"
        opacity: 0.4
        radius: 16

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#15ffffff" }
                GradientStop { position: 0.5; color: "#08ffffff" }
                GradientStop { position: 1.0; color: "#03ffffff" }
            }
        }
    }

    // Border
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        radius: 16
        border.width: 1
        border.color: isFinal ? "#4000ff88" : "#4000d4ff"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            radius: parent.radius - 1
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.06)
        }
    }

    // Listening indicator (animated dot)
    Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 16
        width: 8
        height: 8
        radius: 4
        color: isFinal ? "#00ff88" : "#00d4ff"
        visible: !isFinal

        SequentialAnimation on opacity {
            running: !isFinal
            loops: Animation.Infinite
            PropertyAnimation { to: 0.3; duration: 800 }
            PropertyAnimation { to: 1.0; duration: 800 }
        }
    }

    // Caption text with scrolling
    Flickable {
        id: captionFlickable
        anchors.fill: parent
        anchors.margins: 20
        anchors.leftMargin: 32
        contentWidth: captionText.width
        contentHeight: captionText.height
        clip: true
        flickableDirection: Flickable.HorizontalFlick
        boundsBehavior: Flickable.StopAtBounds

        Text {
            id: captionText
            // Let text determine its own width
            text: currentText || "Live captions will appear here..."
            font.family: "SF Pro Display"
            font.pixelSize: 18
            font.weight: isFinal ? 60 : 50
            color: currentText ? "#ffffff" : "#666666"
            opacity: isFinal ? 1.0 : 0.85
            wrapMode: Text.NoWrap
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            lineHeight: 1.4
            elide: Text.ElideNone
        }

        // Keep at left (no auto-scroll)
        contentX: 0
    }

    // Final caption badge
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 8
        width: badgeText.width + 16
        height: 20
        radius: 10
        color: "#00ff88"
        opacity: 0.2
        visible: isFinal

        Text {
            id: badgeText
            anchors.centerIn: parent
            text: "AI"
            font.family: "SF Pro Display"
            font.pixelSize: 10
            font.weight: 65
            color: "#00ff88"
        }
    }

    function show(text, isFinalized) {
        console.log("ClosedCaptions.show() called with:", text, "final:", isFinalized)
        isFinal = isFinalized

        var newTargetText = ""

        if (isFinalized) {
            // Finalized caption - append to permanent text
            if (finalizedText === "") {
                finalizedText = text
            } else {
                finalizedText += " " + text
            }
            interimText = ""  // Clear interim
            newTargetText = finalizedText

            // Check if text width would exceed container - if so, clear and start fresh
            // Note: We check before typing animation starts
            if (finalizedText.length > 150) {  // Rough estimate
                console.log("Text getting long, clearing...")
                finalizedText = text
                newTargetText = text
            }
        } else {
            // Interim caption - replace previous interim
            interimText = text
            if (finalizedText === "") {
                newTargetText = interimText
            } else {
                newTargetText = finalizedText + " " + interimText
            }
        }

        // Start typing animation towards new target
        targetText = newTargetText
        typingIndex = currentText.length  // Start from current position
        typingTimer.restart()

        // Show widget on first caption after system is ready
        if (systemReady && !visible) {
            console.log("Making caption widget visible")
            visible = true
            opacity = 0.9
        }
    }

    function enableWhenReady() {
        systemReady = true
    }
}
