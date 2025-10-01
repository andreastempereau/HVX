#!/usr/bin/env python3
"""
Helmet Visor UI - Qt/QML dual-eye compositor with AR overlays
"""

import sys
import asyncio
import threading
from pathlib import Path
from typing import Optional
import os

from PySide6.QtCore import QObject, Signal, QTimer, Property, QThread, QUrl, QSize, Slot
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtQml import qmlRegisterType, QQmlApplicationEngine, QQmlImageProviderBase
from PySide6.QtQuick import QQuickView, QQuickImageProvider
from PySide6.QtOpenGL import QOpenGLBuffer

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
except ImportError:
    print("python-dotenv not installed, skipping .env file loading")

# Add libs to path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from utils.config import get_config
from utils.logging_utils import setup_logging

from video_client import VideoClient
from perception_client import PerceptionClient
from hud_controller import HUDController
from voice_listener import VoiceListener

import logging
logger = logging.getLogger(__name__)

class VideoImageProvider(QQuickImageProvider):
    """Image provider for video frames"""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.current_image = QImage()

    def requestImage(self, id, size, requestedSize):
        """Provide image to QML"""
        print(f"QML requesting image: {id}, has image: {not self.current_image.isNull()}")
        if not self.current_image.isNull():
            print(f"Returning image: {self.current_image.width()}x{self.current_image.height()}")
            return self.current_image
        else:
            # Return empty image if no frame available
            print("Returning empty image")
            empty = QImage(640, 480, QImage.Format_RGB888)
            empty.fill(0)
            return empty

    def setImage(self, image):
        """Update the current image"""
        print(f"Setting new image: {image.width()}x{image.height()}")
        self.current_image = image

class VisorApp(QObject):
    """Main visor application controller"""

    # Signals for QML
    frameUpdated = Signal(str)  # Now passes image path
    detectionsUpdated = Signal('QVariantList')
    hudStatusUpdated = Signal('QVariantMap')
    snapshotAnalyzed = Signal(str, str)  # snapshot path, analysis text
    voiceCommandReceived = Signal(str)  # voice command

    def __init__(self, config=None):
        super().__init__()
        self.config = config
        self.video_client = None
        self.perception_client = None
        self.hud_controller = None
        self.running = False
        self.frame_counter = 0

        # Frame processing
        self._current_frame = None
        self._current_detections = []
        self._current_qimage = None

        # Voice listener
        self.voice_listener = None

        # Setup components
        if self.config:
            self._setup_clients()
            self._setup_timers()
            self._setup_voice()

    def _setup_clients(self):
        """Initialize service clients"""
        try:
            # Video client
            video_port = self.config.get('services.video_port', 50051)
            print(f"Connecting to video service at localhost:{video_port}")
            self.video_client = VideoClient(f'localhost:{video_port}')
            print("Video client connected")

            # Perception client
            perception_port = self.config.get('services.perception_port', 50052)
            print(f"Connecting to perception service at localhost:{perception_port}")
            self.perception_client = PerceptionClient(f'localhost:{perception_port}')
            print("Perception client connected")

            # HUD controller
            self.hud_controller = HUDController(self.config)
            print("HUD controller initialized")

            logger.info("Service clients initialized")

        except Exception as e:
            print(f"Failed to setup clients: {e}")
            logger.error(f"Failed to setup clients: {e}")

    def _setup_timers(self):
        """Setup update timers"""
        # Frame update timer
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self._update_frame)

        # HUD update timer
        self.hud_timer = QTimer()
        self.hud_timer.timeout.connect(self._update_hud)

    def _setup_voice(self):
        """Setup voice listener"""
        try:
            # Get microphone device from config
            mic_device = self.config.get('voice.mic_device_index', None)

            self.voice_listener = VoiceListener(device_index=mic_device)
            logger.info("Voice listener initialized")

        except Exception as e:
            logger.warning(f"Voice listener not available: {e}")

    def start(self):
        """Start the visor application"""
        if self.running:
            return

        print("Starting visor app...")
        self.running = True

        try:
            # Start frame updates - reduce FPS for smoother display via file approach
            target_fps = 15  # Lower FPS for better performance with file-based approach
            frame_interval = int(1000 / target_fps)
            self.frame_timer.start(frame_interval)

            # Start HUD updates (lower frequency)
            print("Starting HUD timer")
            self.hud_timer.start(1000)  # 1 second intervals

            # Start voice listener
            if self.voice_listener:
                print("Starting voice listener...")
                self.voice_listener.start(self._on_voice_command)

            print("Visor app started successfully")
            logger.info("Visor app started")

        except Exception as e:
            print(f"Failed to start visor app: {e}")
            logger.error(f"Failed to start visor app: {e}")
            self.running = False

    def stop(self):
        """Stop the visor application"""
        self.running = False
        self.frame_timer.stop()
        self.hud_timer.stop()

        if self.voice_listener:
            self.voice_listener.stop()

        if self.video_client:
            self.video_client.disconnect()
        if self.perception_client:
            self.perception_client.disconnect()

        logger.info("Visor app stopped")

    def _update_frame(self):
        """Update video frame and run perception"""
        if not self.running or not self.video_client:
            print("Frame update: not running or no video client")
            return

        try:
            # Get frame from video service
            frame_meta = self.video_client.get_frame()
            if frame_meta is None:
                return

            # Convert to QImage
            qimage = self._frame_to_qimage(frame_meta)
            if qimage is None:
                return

            self._current_frame = frame_meta
            self._current_qimage = qimage.copy()  # Store for snapshot

            # Use faster JPEG format and reuse single temp file
            import tempfile
            import os

            # Use single temp file path to avoid file system overhead
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "helmet_current_frame.jpg")

            # Save as JPEG for better performance (smaller files, faster encoding)
            if qimage.save(temp_file, "JPG", 85):  # 85% quality for speed
                # Emit signal with file path + timestamp to force reload
                file_url = f"file:///{temp_file.replace(os.sep, '/')}?t={self.frame_counter}"
                self.frameUpdated.emit(file_url)
                self.frame_counter += 1

            # Run perception inference
            if self.perception_client:
                self._run_perception_async(frame_meta)

        except Exception as e:
            print(f"Frame update error: {e}")
            logger.error(f"Frame update error: {e}")

    def _run_perception_async(self, frame_meta):
        """Run perception inference asynchronously"""
        def run_perception():
            try:
                result = self.perception_client.infer(frame_meta)
                if result and result.detections:
                    detections = []
                    for det in result.detections:
                        detection_dict = {
                            'x': det.x,
                            'y': det.y,
                            'width': det.width,
                            'height': det.height,
                            'label': det.label,
                            'confidence': det.confidence
                        }
                        detections.append(detection_dict)

                    self._current_detections = detections
                    self.detectionsUpdated.emit(detections)
                else:
                    # Emit empty detections to clear overlay
                    self.detectionsUpdated.emit([])

            except Exception as e:
                logger.error(f"Perception error: {e}")

        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=run_perception)
        thread.daemon = True
        thread.start()

    def _update_hud(self):
        """Update HUD status information"""
        if not self.running or not self.hud_controller:
            return

        try:
            status = self.hud_controller.get_status()
            self.hudStatusUpdated.emit(status)

        except Exception as e:
            logger.error(f"HUD update error: {e}")

    def _frame_to_qimage(self, frame_meta) -> Optional[QImage]:
        """Convert frame metadata to QImage"""
        try:
            import numpy as np

            # Convert bytes to numpy array
            frame_data = np.frombuffer(frame_meta.data, dtype=np.uint8)

            if frame_meta.format == 'RGB':
                frame = frame_data.reshape((frame_meta.height, frame_meta.width, 3))
                qimage = QImage(
                    frame.data,
                    frame_meta.width,
                    frame_meta.height,
                    frame_meta.width * 3,
                    QImage.Format_RGB888
                )
            else:
                logger.warning(f"Unsupported frame format: {frame_meta.format}")
                return None

            return qimage

        except Exception as e:
            logger.error(f"Frame conversion error: {e}")
            return None

    # Properties for QML
    @Property('QVariantMap', notify=hudStatusUpdated)
    def hudStatus(self):
        """Current HUD status for QML"""
        if self.hud_controller:
            return self.hud_controller.get_status()
        return {}

    def _on_voice_command(self, command: str):
        """Handle voice commands"""
        logger.info(f"Voice command received: {command}")
        print(f"Voice command: {command}")

        # Emit signal to QML
        self.voiceCommandReceived.emit(command)

        # Handle specific commands
        if command == 'analyze':
            self.captureAndAnalyze()

    @Slot()
    def captureAndAnalyze(self):
        """Capture current frame and analyze with Claude API"""
        print("Capture and analyze triggered...")
        logger.info("Capture and analyze triggered")

        if self._current_qimage is None:
            logger.warning("No frame available to capture")
            print("ERROR: No frame available")
            return

        print("Frame available, starting analysis...")

        def analyze_async():
            try:
                import tempfile
                import os
                import base64

                # Save snapshot
                import time as time_module
                temp_dir = tempfile.gettempdir()
                snapshot_path = os.path.join(temp_dir, f"helmet_snapshot_{int(time_module.time())}.jpg")

                if self._current_qimage.save(snapshot_path, "JPG", 95):
                    snapshot_url = f"file:///{snapshot_path.replace(os.sep, '/')}"

                    # Read image as base64
                    with open(snapshot_path, "rb") as img_file:
                        img_data = base64.standard_b64encode(img_file.read()).decode("utf-8")

                    # Call Claude API
                    analysis = self._analyze_with_claude(img_data)

                    # Emit result
                    self.snapshotAnalyzed.emit(snapshot_url, analysis)
                else:
                    logger.error("Failed to save snapshot")

            except Exception as e:
                logger.error(f"Snapshot analysis error: {e}")
                self.snapshotAnalyzed.emit("", f"Analysis failed: {str(e)}")

        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=analyze_async)
        thread.daemon = True
        thread.start()

    def _analyze_with_claude(self, image_base64: str) -> str:
        """Analyze image using Claude API"""
        try:
            import anthropic
            import os

            # Get API key from environment or config
            api_key = os.environ.get('ANTHROPIC_API_KEY') or self.config.get('claude.api_key', '')

            if not api_key:
                return "Error: ANTHROPIC_API_KEY not set. Set environment variable or add to config."

            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "What am I looking at? Provide a brief, concise description."
                            }
                        ],
                    }
                ],
            )

            return message.content[0].text

        except ImportError:
            return "Error: anthropic package not installed. Run: pip install anthropic"
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"Analysis error: {str(e)}"

def main():
    """Main entry point"""
    config = get_config()

    # Setup logging
    log_level = config.get('system.log_level', 'INFO')
    log_dir = Path(config.get('system.log_dir', 'logs'))
    setup_logging('visor-ui', log_level, log_dir)

    # Create Qt application
    app = QGuiApplication(sys.argv)

    # Register QML types
    qmlRegisterType(VisorApp, 'HelmetUI', 1, 0, 'VisorApp')

    # Create QML engine
    engine = QQmlApplicationEngine()
    qml_file = Path(__file__).parent / "qml" / "main.qml"

    if not qml_file.exists():
        logger.error(f"QML file not found: {qml_file}")
        sys.exit(1)

    # Create visor app instance
    visor_app = VisorApp(config)

    # Set context properties
    engine.rootContext().setContextProperty("visorApp", visor_app)
    engine.rootContext().setContextProperty("config", config.all)

    # Load QML with absolute path
    qml_url = QUrl.fromLocalFile(str(qml_file.resolve()))
    engine.load(qml_url)

    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML file")
        sys.exit(1)

    # Start visor app
    visor_app.start()

    try:
        # Run application
        result = app.exec()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        result = 0
    finally:
        visor_app.stop()

    sys.exit(result)

if __name__ == "__main__":
    main()