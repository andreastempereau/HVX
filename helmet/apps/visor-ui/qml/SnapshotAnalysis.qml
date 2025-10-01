import QtQuick 2.15
import QtQuick.Controls 2.15

// Snapshot analysis widget - shows captured frame with Claude AI analysis
Item {
    id: snapshotWidget
    anchors.bottom: parent.bottom
    anchors.left: parent.left
    anchors.margins: 20
    width: 500
    height: column.implicitHeight
    visible: false
    opacity: 0
    z: 1000  // Ensure it's above everything else

    property string snapshotPath: ""
    property string analysisText: ""
    property bool analyzing: false

    Behavior on opacity {
        NumberAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }

    Column {
        id: column
        spacing: 8
        width: parent.width

        // Snapshot thumbnail with glassy border
        Rectangle {
            width: parent.width
            height: 280
            color: "#0d0d0d"
            border.color: analyzing ? "#888888" : "#666666"
            border.width: 2
            radius: 0

            // Frosted glass effect overlay
            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                color: "#ffffff"
                opacity: 0.03
                radius: 0
            }

            Image {
                id: snapshotImage
                anchors.fill: parent
                anchors.margins: 4
                source: snapshotPath
                fillMode: Image.PreserveAspectFit
                smooth: true
                cache: false
            }

            // Analyzing indicator
            Rectangle {
                anchors.centerIn: parent
                width: 120
                height: 40
                color: "#1a1a1a"
                border.color: "#666666"
                border.width: 1
                radius: 0
                opacity: analyzing ? 0.95 : 0
                visible: analyzing

                Behavior on opacity {
                    NumberAnimation { duration: 200 }
                }

                Row {
                    anchors.centerIn: parent
                    spacing: 10

                    Rectangle {
                        width: 20
                        height: 20
                        color: "transparent"
                        border.color: "#aaaaaa"
                        border.width: 2
                        radius: 0

                        RotationAnimator on rotation {
                            running: analyzing
                            from: 0
                            to: 360
                            duration: 1500
                            loops: Animation.Infinite
                        }
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "ANALYZING"
                        font.family: "Consolas"
                        font.pixelSize: 10
                        color: "#aaaaaa"
                    }
                }
            }

            // Header bar with close button
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 24
                color: "#1a1a1a"
                border.color: "#666666"
                border.width: 1
                radius: 0

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: "SNAPSHOT ANALYSIS"
                    font.family: "Consolas"
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: "#aaaaaa"
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 24
                    color: closeMouseArea.containsMouse ? "#333333" : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "X"
                        font.family: "Consolas"
                        font.pixelSize: 10
                        font.bold: true
                        color: "#888888"
                    }

                    MouseArea {
                        id: closeMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: hide()
                    }
                }
            }
        }

        // Analysis text panel with glass effect
        Rectangle {
            width: parent.width
            height: Math.min(400, Math.max(120, analysisTextArea.contentHeight + 50))
            color: "#0d0d0d"
            border.color: "#666666"
            border.width: 1
            radius: 0
            opacity: 0.95
            visible: analysisText !== ""

            // Subtle frosted glass overlay
            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                color: "#ffffff"
                opacity: 0.03
                radius: 0
            }

            Column {
                anchors.fill: parent
                spacing: 0

                // Header
                Rectangle {
                    width: parent.width
                    height: 24
                    color: "#1a1a1a"
                    border.color: "#555555"
                    border.width: 1
                    radius: 0

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: "AI ANALYSIS"
                        font.family: "Consolas"
                        font.pixelSize: 9
                        font.weight: Font.Bold
                        color: "#aaaaaa"
                    }
                }

                // Content
                Flickable {
                    id: analysisFlickable
                    width: parent.width
                    height: parent.height - 24
                    contentWidth: width
                    contentHeight: analysisTextArea.contentHeight + 30
                    clip: true
                    flickableDirection: Flickable.VerticalFlick
                    boundsBehavior: Flickable.StopAtBounds

                    Text {
                        id: analysisTextArea
                        width: parent.width - 30
                        x: 15
                        y: 15
                        text: analysisText
                        font.family: "Consolas"
                        font.pixelSize: 12
                        color: "#cccccc"
                        wrapMode: Text.WordWrap
                        lineHeight: 1.4
                    }

                    // Scroll indicator
                    Rectangle {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.margins: 4
                        width: 4
                        color: "#1a1a1a"
                        radius: 0
                        visible: analysisFlickable.contentHeight > analysisFlickable.height

                        Rectangle {
                            width: parent.width
                            height: Math.max(20, (analysisFlickable.height / analysisFlickable.contentHeight) * parent.height)
                            y: (analysisFlickable.contentY / analysisFlickable.contentHeight) * parent.height
                            color: "#666666"
                            radius: 0
                        }
                    }
                }
            }
        }
    }

    function show(imagePath) {
        snapshotPath = imagePath
        analysisText = ""
        analyzing = true
        visible = true
        opacity = 1.0
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
        interval: 300
        onTriggered: {
            snapshotWidget.visible = false
            snapshotPath = ""
            analysisText = ""
            analyzing = false
        }
    }
}
