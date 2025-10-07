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
from caption_client import CaptionClient
from rear_camera import RearCamera
from openai_voice_assistant import OpenAIRealtimeAssistant
from wake_word_detector import WakeWordDetector

import logging
logger = logging.getLogger(__name__)

class VideoImageProvider(QQuickImageProvider):
    """Image provider for video frames"""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.current_image = QImage()
        self.lock = threading.Lock()

    def requestImage(self, id, size, requestedSize):
        """Provide image to QML"""
        with self.lock:
            if not self.current_image.isNull():
                # Return a copy to avoid threading issues
                return self.current_image.copy()
            else:
                # Return empty image if no frame available
                empty = QImage(640, 480, QImage.Format_RGB888)
                empty.fill(0)
                return empty

    def setImage(self, image):
        """Update the current image"""
        with self.lock:
            self.current_image = image

class RearCameraImageProvider(QQuickImageProvider):
    """Image provider for rear camera frames"""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self.current_image = QImage()
        self.lock = threading.Lock()
        self.request_count = 0

    def requestImage(self, id, size, requestedSize):
        """Provide image to QML"""
        with self.lock:
            self.request_count += 1
            if self.request_count <= 3:
                print(f"RearCameraImageProvider.requestImage called - id: {id}, has_image: {not self.current_image.isNull()}")
                if not self.current_image.isNull():
                    print(f"  Returning image: {self.current_image.width()}x{self.current_image.height()}, format: {self.current_image.format()}")

            if not self.current_image.isNull():
                return self.current_image.copy()
            else:
                # Return empty image if no frame available
                empty = QImage(240, 180, QImage.Format_RGB888)
                empty.fill(0)
                if self.request_count <= 3:
                    print(f"  Returning empty image")
                return empty

    def setImage(self, image):
        """Update the current image"""
        with self.lock:
            self.current_image = image

class VisorApp(QObject):
    """Main visor application controller"""

    # Signals for QML
    frameUpdated = Signal(str)  # Now passes image path
    rearFrameUpdated = Signal(str)  # Rear camera frame
    detectionsUpdated = Signal('QVariantList')
    hudStatusUpdated = Signal('QVariantMap')
    snapshotAnalyzed = Signal(str, str)  # snapshot path, analysis text
    voiceCommandReceived = Signal(str)  # voice command
    captionReceived = Signal(str, bool)  # caption text, is_final

    def __init__(self, config=None, image_provider=None, rear_image_provider=None):
        super().__init__()
        self.config = config
        self.video_client = None
        self.rear_camera = None
        self.perception_client = None
        self.hud_controller = None
        self.running = False
        self.frame_counter = 0
        self.rear_frame_counter = 0

        # Frame processing
        self._current_frame = None
        self._current_rear_frame = None
        self._current_detections = []
        self._current_qimage = None
        self._current_rear_qimage = None
        self._shared_qimage = None
        self.image_provider = image_provider
        self.rear_image_provider = rear_image_provider

        # Voice listener
        self.voice_listener = None

        # Caption client
        self.caption_client = None

        # Voice assistant
        self.voice_assistant = None

        # Wake word detector
        self.wake_word_detector = None

        # Setup components
        if self.config:
            print("="*60)
            print("VISOR APP INITIALIZATION")
            print("="*60)
            self._setup_clients()
            self._setup_timers()
            self._setup_voice()
            # print("\n--- Setting up captions ---")
            # self._setup_captions()
            # print("--- Caption setup complete ---\n")
            print("\n--- Setting up wake word detector ---")
            self._setup_wake_word()
            print("--- Wake word detector setup complete ---\n")
            print("\n--- Setting up voice assistant ---")
            self._setup_assistant()
            print("--- Voice assistant setup complete ---\n")

    def _setup_clients(self):
        """Initialize service clients"""
        try:
            # Main video client (front camera)
            video_port = self.config.get('services.video_port', 50051)
            print(f"Connecting to video service at localhost:{video_port}")
            self.video_client = VideoClient(f'localhost:{video_port}')
            print("Video client connected")

            # Rear camera (IMX219 CSI camera in CAM0 slot using GStreamer directly)
            rear_camera_sensor_id = 0  # CAM0 slot
            try:
                self.rear_camera = RearCamera(camera_id=rear_camera_sensor_id)
                if self.rear_camera.start(use_gstreamer=True):
                    print(f"Rear camera initialized (sensor-id {rear_camera_sensor_id})")
                else:
                    print("Rear camera not available")
                    self.rear_camera = None
            except Exception as e:
                print(f"Rear camera setup failed: {e}")
                import traceback
                traceback.print_exc()
                self.rear_camera = None

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

        # Rear camera update timer
        self.rear_frame_timer = QTimer()
        self.rear_frame_timer.timeout.connect(self._update_rear_frame)

        # HUD update timer
        self.hud_timer = QTimer()
        self.hud_timer.timeout.connect(self._update_hud)

    def _setup_voice(self):
        """Setup voice listener"""
        try:
            # Disabled - conflicts with Deepgram caption client
            # Get microphone device from config
            # mic_device = self.config.get('voice.mic_device_index', None)
            # self.voice_listener = VoiceListener(device_index=mic_device)
            logger.info("Voice listener disabled (using Deepgram for captions)")

        except Exception as e:
            logger.warning(f"Voice listener not available: {e}")

    def _setup_captions(self):
        """Setup closed caption system"""
        print("ENTERING _setup_captions()")
        try:
            # Get API key
            import os as os_module
            deepgram_key = os_module.environ.get('DEEPGRAM_API_KEY')

            print(f"Deepgram key from env: {deepgram_key[:20] if deepgram_key else 'None'}...")
            print(f"Deepgram key present: {bool(deepgram_key)}")

            if not deepgram_key:
                logger.warning("DEEPGRAM_API_KEY not set - captions disabled")
                print("WARNING: DEEPGRAM_API_KEY not set - captions disabled")
                return

            # Get microphone device from config (use card 0 for Razer Kiyo X)
            mic_device = self.config.get('caption.mic_device_index', 0)

            print(f"Initializing caption client with mic device: {mic_device}")
            self.caption_client = CaptionClient(
                deepgram_api_key=deepgram_key,
                device_index=mic_device,
                parent_app=self  # Pass self for Qt signal access
            )
            logger.info("Caption client initialized")
            print("✓ Caption client initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Caption client not available: {e}")
            print(f"ERROR: Caption client not available: {e}")
            print("TRACEBACK:")
            traceback.print_exc()

    def _setup_wake_word(self):
        """Setup wake word detector (using openWakeWord - no API key needed)"""
        try:
            # Get config
            wake_word = self.config.get('assistant.wake_word', 'hey_jarvis')
            mic_device = self.config.get('assistant.input_device_index', None)

            print(f"Initializing wake word detector (openWakeWord)...")
            print(f"  Wake word: '{wake_word}'")
            print(f"  Mic device: {mic_device or 'default'}")

            self.wake_word_detector = WakeWordDetector(
                keywords=[wake_word],
                device_index=mic_device
            )
            logger.info("Wake word detector initialized")
            print("✓ Wake word detector initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Wake word detector not available: {e}")
            print(f"ERROR: Wake word detector not available: {e}")
            traceback.print_exc()

    def _setup_assistant(self):
        """Setup OpenAI Realtime voice assistant"""
        try:
            # Get API key
            import os as os_module
            openai_key = os_module.environ.get('OPENAI_API_KEY')

            if not openai_key:
                logger.warning("OPENAI_API_KEY not set - voice assistant disabled")
                print("WARNING: OPENAI_API_KEY not set - voice assistant disabled")
                return

            # Get config
            voice = self.config.get('assistant.voice', 'alloy')  # alloy, echo, fable, onyx, nova, shimmer
            input_device = self.config.get('assistant.input_device_index', None)
            output_device = self.config.get('assistant.output_device_index', None)
            system_prompt = self.config.get('assistant.system_prompt',
                "You are a helpful AI assistant integrated into an AR helmet. Provide concise, clear responses suitable for voice interaction.")

            print(f"Initializing OpenAI Realtime voice assistant...")
            print(f"  Voice: {voice}")
            print(f"  Input device: {input_device or 'default'}")
            print(f"  Output device: {output_device or 'default'}")
            print(f"  System prompt: {system_prompt[:50]}...")

            self.voice_assistant = OpenAIRealtimeAssistant(
                openai_api_key=openai_key,
                system_prompt=system_prompt,
                voice=voice,
                input_device_index=input_device,
                output_device_index=output_device,
                wake_word_detector=self.wake_word_detector,  # Pass wake word detector reference
                frame_getter=self.get_current_camera_frame  # Pass frame getter for on-demand vision
            )
            logger.info("OpenAI Realtime voice assistant initialized")
            print("✓ OpenAI Realtime voice assistant initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Voice assistant not available: {e}")
            print(f"ERROR: Voice assistant not available: {e}")
            traceback.print_exc()

    def _on_wake_word_detected(self, keyword: str):
        """Handle wake word detection"""
        logger.info(f"Wake word detected: {keyword}")
        print(f"\n🎤 Wake word '{keyword}' detected! Activating assistant...")

        # Wake word detector has released the microphone
        # Now activate voice assistant (it will open the mic)
        if self.voice_assistant:
            self.voice_assistant.activate()

        # Note: wake_word_detector.resume() will be called when assistant deactivates

    def start(self):
        """Start the visor application"""
        if self.running:
            return

        print("Starting visor app...")
        self.running = True

        try:
            # Start frame updates - using image provider for fast zero-copy updates
            target_fps = 30  # 30 FPS for balanced performance
            frame_interval = int(1000 / target_fps)
            self.frame_timer.start(frame_interval)

            # Start rear camera updates (10 FPS - lower to avoid lag)
            if self.rear_camera:
                self.rear_frame_timer.start(100)  # 10 FPS

            # Start HUD updates (lower frequency)
            print("Starting HUD timer")
            self.hud_timer.start(1000)  # 1 second intervals

            # Start voice listener
            if self.voice_listener:
                print("Starting voice listener...")
                self.voice_listener.start(self._on_voice_command)

            # Start caption client (DISABLED)
            # print(f"Caption client object: {self.caption_client}")
            # if self.caption_client:
            #     print("Starting caption client...")
            #     self.caption_client.start(None)  # Callback not used, uses Qt signal instead
            #     print("Caption client started!")
            # else:
            #     print("WARNING: No caption client to start")

            # Start wake word detector
            if self.wake_word_detector:
                print("Starting wake word detector...")
                self.wake_word_detector.start(self._on_wake_word_detected)
                print("Wake word detector started!")
            else:
                print("WARNING: No wake word detector to start")

            # Start voice assistant
            if self.voice_assistant:
                print("Starting voice assistant...")
                self.voice_assistant.start()
                print("Voice assistant started!")
            else:
                print("WARNING: No voice assistant to start")

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
        self.rear_frame_timer.stop()
        self.hud_timer.stop()

        if self.voice_listener:
            self.voice_listener.stop()

        if self.caption_client:
            self.caption_client.stop()

        if self.wake_word_detector:
            self.wake_word_detector.stop()

        if self.voice_assistant:
            self.voice_assistant.stop()

        if self.rear_camera:
            self.rear_camera.stop()

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
            self._current_qimage = qimage.copy()  # Store for snapshot (used for snapshots and on-demand vision)

            # Use image provider for zero-copy frame updates (fastest)
            if self.image_provider:
                self.image_provider.setImage(qimage)
                # Emit update signal with timestamp to trigger QML refresh
                self.frameUpdated.emit(f"image://video/{self.frame_counter}")
                self.frame_counter += 1

            # Run perception inference (DISABLED - high CPU usage)
            # if self.perception_client:
            #     self._run_perception_async(frame_meta)

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

    def _update_rear_frame(self):
        """Update rear camera frame"""
        if not self.running or not self.rear_camera:
            if self.rear_frame_counter == 0:
                print(f"Rear camera update skipped - running: {self.running}, rear_camera: {self.rear_camera}")
            return

        try:
            # Get frame from rear camera
            frame = self.rear_camera.get_frame()
            if frame is None:
                if self.rear_frame_counter == 0:
                    print("Rear camera: no frame available")
                return

            if self.rear_frame_counter == 0:
                print(f"Rear camera: first frame received - shape: {frame.shape}, dtype: {frame.dtype}")

            # IMPORTANT: Keep numpy array alive by storing it as instance variable
            # QImage is just a wrapper - the underlying data must persist
            self._current_rear_frame = frame.copy()

            import numpy as np
            height, width, channels = self._current_rear_frame.shape
            bytes_per_line = channels * width

            # Create QImage pointing to our persistent numpy array
            qimage = QImage(self._current_rear_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            if qimage.isNull():
                logger.error("Rear camera QImage is null!")
                return

            if self.rear_frame_counter == 0:
                print(f"Rear camera: QImage created - size: {qimage.width()}x{qimage.height()}, format: {qimage.format()}")

            # Use image provider for zero-copy frame updates (no temp files)
            if self.rear_image_provider:
                self.rear_image_provider.setImage(qimage.copy())  # Copy QImage data to image provider
                # Emit update signal with timestamp to trigger QML refresh
                image_path = f"image://rearcamera/{self.rear_frame_counter}"
                if self.rear_frame_counter == 0:
                    print(f"Rear camera: emitting signal with path: {image_path}")
                self.rearFrameUpdated.emit(image_path)
                self.rear_frame_counter += 1
            else:
                print("ERROR: No rear_image_provider!")

        except Exception as e:
            logger.error(f"Rear frame update error: {e}")
            import traceback
            traceback.print_exc()

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

    @Slot(str, bool)
    def _emit_caption_signal(self, text: str, is_final: bool):
        """Thread-safe method to emit caption signal to QML"""
        logger.debug(f"Caption: {text} (final={is_final})")
        print(f"_emit_caption_signal called: '{text}' (final={is_final})")
        print(f"Emitting captionReceived signal...")
        # Emit to QML
        self.captionReceived.emit(text, is_final)
        print(f"Signal emitted!")

        # Send final captions to voice assistant (DISABLED - no caption system)
        # if is_final and self.voice_assistant and len(text.strip()) > 0:
        #     text_lower = text.lower()
        #     wake_word = self.config.get('assistant.wake_word', 'bart').lower()

        #     # Check if assistant is already active
        #     if self.voice_assistant.is_active:
        #         # Already active - send all final captions directly
        #         print(f"[Assistant Active] Processing: '{text}'")
        #         self.voice_assistant.process_transcript(text)
        #     elif wake_word in text_lower:
        #         # Wake word detected - activate and process
        #         wake_word_index = text_lower.find(wake_word)
        #         if wake_word_index != -1:
        #             # Activate assistant
        #             self.voice_assistant.activate()

        #             # Get text after wake word
        #             command = text[wake_word_index + len(wake_word):].strip()

        #             if len(command) > 0:
        #                 print(f"Wake word '{wake_word}' detected! Command: '{command}'")
        #                 self.voice_assistant.process_transcript(command)
        #             else:
        #                 # Just the wake word, acknowledge
        #                 print(f"Wake word '{wake_word}' detected with no command")
        #                 self.voice_assistant.process_transcript("Yes?")
        #     else:
        #         print(f"No wake word detected in: '{text}'")

    def get_current_camera_frame(self):
        """Get current camera frame QImage (for on-demand vision queries)"""
        return self._current_qimage

    @Slot()
    def captureAndAnalyze(self):
        """Capture current frame and analyze with Claude API"""
        print("\n" + "="*60)
        print("=== SNAPSHOT TRIGGERED (P key pressed) ===")
        print("="*60)
        logger.info("Capture and analyze triggered")

        if self._current_qimage is None:
            logger.warning("No frame available to capture")
            print("ERROR: No frame available to capture")
            self.snapshotAnalyzed.emit("", "Error: No frame available to analyze")
            return

        print("✓ Frame available, starting analysis...")
        print(f"✓ Frame size: {self._current_qimage.width()}x{self._current_qimage.height()}")

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

            print("Checking for Anthropic API key...")
            # Get API key from environment or config
            api_key = os.environ.get('ANTHROPIC_API_KEY') or self.config.get('claude.api_key', '')

            if not api_key:
                error_msg = """ANTHROPIC_API_KEY not configured.

To enable AI analysis:
1. Get API key from: https://console.anthropic.com/
2. Set environment variable:
   export ANTHROPIC_API_KEY=sk-ant-...
3. Or add to .env file:
   ANTHROPIC_API_KEY=sk-ant-...
"""
                print(error_msg)
                return error_msg

            print(f"API key found, calling Claude API...")
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

            print("Claude API analysis complete!")
            return message.content[0].text

        except ImportError:
            error_msg = """Anthropic package not installed.

Install with:
  pip install anthropic

Or if using venv:
  source venv/bin/activate
  pip install anthropic
"""
            print(error_msg)
            return error_msg
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            error_msg = f"Analysis error: {str(e)}"
            print(error_msg)
            return error_msg

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

    # Create and register image providers for fast video frames
    image_provider = VideoImageProvider()
    engine.addImageProvider("video", image_provider)

    rear_image_provider = RearCameraImageProvider()
    engine.addImageProvider("rearcamera", rear_image_provider)

    qml_file = Path(__file__).parent / "qml" / "main.qml"

    if not qml_file.exists():
        logger.error(f"QML file not found: {qml_file}")
        sys.exit(1)

    # Create visor app instance with image providers
    visor_app = VisorApp(config, image_provider, rear_image_provider)

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