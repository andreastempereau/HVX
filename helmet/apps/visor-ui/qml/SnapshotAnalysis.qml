import QtQuick 2.15
import QtQuick.Controls 2.15

// Snapshot analysis widget - iOS 26 Military Glass style
Item {
    id: snapshotWidget
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.rightMargin: 20
    anchors.bottomMargin: 20
    width: 900
    height: 600
    visible: false
    opacity: 0
    z: 2000
    focus: true

    property string snapshotPath: ""
    property string analysisText: ""
    property bool analyzing: false

    Behavior on opacity {
        NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
    }

    // Main glass panel
    Rectangle {
        id: glassBackground
        anchors.fill: parent
        color: "#0a0a0a"
        opacity: 0.2
        radius: 24

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#20ffffff" }
                GradientStop { position: 0.5; color: "#10ffffff" }
                GradientStop { position: 1.0; color: "#05ffffff" }
            }
        }
    }

    // Glass border
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        radius: 24
        border.width: 1.5
        border.color: analyzing ? "#4000d4ff" : "#4000ff88"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            radius: parent.radius - 1
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
        }
    }

    // Top highlight
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 12
        height: 1
        radius: 0.5
        color: Qt.rgba(1, 1, 1, 0.15)
    }

    // Content
    Row {
        anchors.fill: parent
        anchors.margins: 30
        spacing: 24

        // Left side - Snapshot image
        Column {
            width: parent.width * 0.5
            height: parent.height
            spacing: 12

            // Header
            Text {
                text: "SNAPSHOT CAPTURE"
                font.family: "SF Pro Display"
                font.pixelSize: 11
                font.weight: 57
                color: "#00d4ff"
                opacity: 0.7
            }

            // Image container
            Rectangle {
                width: parent.width
                height: parent.height - 30
                color: "#0d0d0d"
                radius: 16
                border.width: 1
                border.color: "#333333"

                Image {
                    id: snapshotImage
                    anchors.fill: parent
                    anchors.margins: 8
                    source: snapshotPath
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    cache: false
                }

                // Analyzing overlay
                Rectangle {
                    anchors.centerIn: parent
                    width: 180
                    height: 60
                    color: "#0a0a0a"
                    opacity: analyzing ? 0.95 : 0
                    visible: analyzing
                    radius: 12
                    border.width: 1.5
                    border.color: "#00d4ff"

                    Behavior on opacity {
                        NumberAnimation { duration: 300 }
                    }

                    Row {
                        anchors.centerIn: parent
                        spacing: 12

                        Rectangle {
                            width: 24
                            height: 24
                            color: "transparent"
                            border.color: "#00d4ff"
                            border.width: 2
                            radius: 12
                            anchors.verticalCenter: parent.verticalCenter

                            RotationAnimator on rotation {
                                running: analyzing
                                from: 0
                                to: 360
                                duration: 1500
                                loops: Animation.Infinite
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                text: "ANALYZING"
                                font.family: "SF Pro Display"
                                font.pixelSize: 12
                                font.weight: 63
                                color: "#00d4ff"
                            }
                            Text {
                                text: "Claude Vision AI"
                                font.family: "SF Pro Display"
                                font.pixelSize: 10
                                font.weight: 50
                                color: "#ffffff"
                                opacity: 0.5
                            }
                        }
                    }
                }
            }
        }

        // Right side - Analysis text
        Column {
            width: parent.width * 0.5 - 24
            height: parent.height
            spacing: 12

            // Header
            Row {
                spacing: 12
                width: parent.width

                Text {
                    text: "AI ANALYSIS"
                    font.family: "SF Pro Display"
                    font.pixelSize: 11
                    font.weight: 57
                    color: "#00ff88"
                    opacity: 0.7
                }

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: "#00ff88"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: !analyzing && analysisText !== ""

                    SequentialAnimation on opacity {
                        running: !analyzing && analysisText !== ""
                        loops: 3
                        PropertyAnimation { to: 0.3; duration: 500 }
                        PropertyAnimation { to: 1.0; duration: 500 }
                    }
                }
            }

            // Analysis container
            Rectangle {
                width: parent.width
                height: parent.height - 30
                color: "#0d0d0d"
                radius: 16
                border.width: 1
                border.color: "#333333"

                Flickable {
                    id: analysisFlickable
                    anchors.fill: parent
                    anchors.margins: 20
                    contentWidth: width
                    contentHeight: analysisTextArea.contentHeight
                    clip: true
                    flickableDirection: Flickable.VerticalFlick
                    boundsBehavior: Flickable.StopAtBounds

                    Text {
                        id: analysisTextArea
                        width: parent.width - 20
                        text: analysisText || "Press 'P' to capture and analyze the current view.\n\nClaude Vision AI will provide detailed insights about what you're looking at."
                        font.family: "SF Pro Display"
                        font.pixelSize: 14
                        font.weight: 50
                        color: analysisText ? "#ffffff" : "#666666"
                        opacity: analysisText ? 0.95 : 0.5
                        wrapMode: Text.WordWrap
                        lineHeight: 1.5
                    }

                    // Scroll indicator
                    Rectangle {
                        anchors.right: parent.right
                        anchors.rightMargin: -8
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 4
                        color: "#1a1a1a"
                        radius: 2
                        visible: analysisFlickable.contentHeight > analysisFlickable.height

                        Rectangle {
                            width: parent.width
                            height: Math.max(20, (analysisFlickable.height / analysisFlickable.contentHeight) * parent.height)
                            y: (analysisFlickable.contentY / analysisFlickable.contentHeight) * parent.height
                            color: "#00ff88"
                            radius: 2
                            opacity: 0.6
                        }
                    }
                }
            }
        }
    }

    // Close button (top right)
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 20
        width: 40
        height: 40
        radius: 20
        color: closeMouseArea.containsMouse ? "#1a1a1a" : "transparent"
        border.width: 1
        border.color: "#333333"

        Text {
            anchors.centerIn: parent
            text: "✕"
            font.family: "SF Pro Display"
            font.pixelSize: 18
            color: closeMouseArea.containsMouse ? "#ff3b30" : "#ffffff"
            opacity: closeMouseArea.containsMouse ? 1.0 : 0.6
        }

        MouseArea {
            id: closeMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: hide()
        }
    }

    // Keyboard hint (bottom)
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 20
        width: hintText.width + 30
        height: 32
        radius: 16
        color: "#0d0d0d"
        opacity: 0.8
        border.width: 1
        border.color: "#333333"

        Text {
            id: hintText
            anchors.centerIn: parent
            text: "Press ESC or click ✕ to close"
            font.family: "SF Pro Display"
            font.pixelSize: 11
            color: "#ffffff"
            opacity: 0.6
        }
    }

    function show(imagePath) {
        snapshotPath = imagePath
        analysisText = ""
        analyzing = true
        visible = true
        opacity = 1.0
        forceActiveFocus()
    }

    function setAnalysis(text) {
        analysisText = text
        analyzing = false
    }

    function hide() {
        opacity = 0
        hideTimer.start()
    }

    Timer {
        id: hideTimer
        interval: 400
        onTriggered: {
            snapshotWidget.visible = false
            snapshotPath = ""
            analysisText = ""
            analyzing = false
        }
    }

    // Allow ESC key to close
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
            hide()
            event.accepted = true
        }
    }

}
