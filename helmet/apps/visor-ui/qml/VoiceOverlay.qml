import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: voiceOverlay

    width: 400
    height: 80

    property string currentText: ""
    property bool isListening: false

    // Background
    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: 0.9
        radius: 10
        visible: parent.visible

        // Voice status indicator
        Row {
            anchors.centerIn: parent
            spacing: 15

            // Microphone icon (animated when listening)
            Rectangle {
                width: 20
                height: 30
                radius: 10
                color: isListening ? "red" : "gray"
                opacity: isListening ? 1.0 : 0.5

                SequentialAnimation on opacity {
                    running: isListening
                    loops: Animation.Infinite
                    PropertyAnimation { to: 0.3; duration: 400 }
                    PropertyAnimation { to: 1.0; duration: 400 }
                }

                // Mic "pop filter" circle
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: -5
                    width: 25
                    height: 8
                    radius: 4
                    color: parent.color
                    opacity: 0.7
                }
            }

            // Voice text
            Text {
                id: voiceText
                text: currentText
                color: "white"
                font.pixelSize: 16
                font.bold: true
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
            }
        }

        // Waveform visualization (when listening)
        Row {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottomMargin: 8
            spacing: 2
            visible: isListening

            Repeater {
                model: 20

                Rectangle {
                    width: 3
                    height: 4 + Math.random() * 12
                    color: "cyan"
                    opacity: 0.7

                    SequentialAnimation on height {
                        running: isListening
                        loops: Animation.Infinite
                        PropertyAnimation {
                            to: 4 + Math.random() * 12
                            duration: 100 + Math.random() * 200
                        }
                        PropertyAnimation {
                            to: 4 + Math.random() * 12
                            duration: 100 + Math.random() * 200
                        }
                    }
                }
            }
        }
    }

    // Hide timer
    Timer {
        id: hideTimer
        interval: 3000
        onTriggered: {
            voiceOverlay.visible = false
            isListening = false
        }
    }

    // Functions
    function show(text, listening) {
        currentText = text || ""
        isListening = listening || false
        visible = true
        hideTimer.restart()
    }

    function updateText(text) {
        currentText = text
        hideTimer.restart()
    }

    function setListening(listening) {
        isListening = listening
        if (!listening) {
            hideTimer.restart()
        }
    }

    function hide() {
        visible = false
        isListening = false
        hideTimer.stop()
    }
}