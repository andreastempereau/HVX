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

# Fix Qt plugin conflict with OpenCV - must be done BEFORE Qt imports
# OpenCV sets QT_QPA_PLATFORM_PLUGIN_PATH which breaks PySide6

# CRITICAL: Set Qt platform BEFORE importing cv2 or any Qt
# Try linuxfb first (works on Jetson with framebuffer), fall back to offscreen
# You can override with: export QT_QPA_PLATFORM=eglfs (or xcb if X11 is available)
platform = os.environ.get('QT_QPA_PLATFORM', 'linuxfb')
os.environ['QT_QPA_PLATFORM'] = platform
print(f"Using Qt platform: {platform}")

import cv2

# Remove OpenCV's bad Qt plugin path
if 'QT_QPA_PLATFORM_PLUGIN_PATH' in os.environ:
    del os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']

# Set correct PySide6 plugin path
import PySide6
pyside6_plugins = str(Path(PySide6.__file__).parent / 'Qt' / 'plugins')
os.environ['QT_PLUGIN_PATH'] = pyside6_plugins

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

from hud_controller import HUDController
from voice_listener import VoiceListener
# from rear_camera import RearCamera  # Kept for future use, not currently in HUD
from direct_camera import DirectCamera  # Native GStreamer for main camera
from thermal_camera import ThermalCamera  # FLIR Boson thermal camera
from openai_voice_assistant import OpenAIRealtimeAssistant
from wake_word_detector import WakeWordDetector
from gyro_sensor import GyroSensor
from system_monitor import SystemMonitor
from full_recorder import FullRecorder
from gps_client import GPSClient
from minimap_controller import MinimapController, MinimapImageProvider

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

class VisorApp(QObject):
    """Main visor application controller"""

    # Signals for QML
    frameUpdated = Signal(str)  # Now passes image path
    thermalFrameUpdated = Signal(str)  # Thermal camera image path
    detectionsUpdated = Signal('QVariantList')
    hudStatusUpdated = Signal('QVariantMap')
    snapshotAnalyzed = Signal(str, str)  # snapshot path, analysis text
    voiceCommandReceived = Signal(str)  # voice command
    captionReceived = Signal(str, bool)  # caption text, is_final
    orientationUpdated = Signal(float, float, float)  # heading, roll, pitch angles
    gpsPositionUpdated = Signal(float, float, float, float)  # lat, lon, altitude, heading
    gpsStatusUpdated = Signal('QVariantMap')  # GPS status info
    minimapUpdated = Signal(str)  # minimap image path

    def __init__(self, config=None, image_provider=None, qml_window=None):
        super().__init__()
        self.config = config
        self.video_client = None
        self.direct_camera = None  # Direct GStreamer camera
        self.thermal_camera = None  # FLIR thermal camera
        self.thermal_enabled = False  # Thermal overlay toggle
        self.thermal_counter = 0  # Frame counter for thermal
        self.perception_client = None
        self.hud_controller = None
        self.running = False
        self.frame_counter = 0
        self.qml_window = qml_window  # Reference to QML window for screen capture

        # Frame processing
        self._current_frame = None
        self._right_camera_frame = None  # Right camera for snapshots
        self._current_detections = []
        self._current_qimage = None
        self._shared_qimage = None
        self.image_provider = image_provider

        # YOLO person detection
        self.yolo_model = None
        self.detection_frame_skip = 9  # Process every Nth frame (at 30fps: 9 = ~3.3 detections/sec)
        self.detection_frame_counter = 0
        # Camera offset compensation (camera mounted above and to the left of bridge of nose)
        self.camera_vertical_offset_px = 80  # 2-inch camera offset above eyeline (shift detections DOWN)
        self.camera_horizontal_offset_px = 0  # Horizontal offset (shift LEFT if camera is left of center)

        # Voice listener
        self.voice_listener = None

        # Caption client
        self.caption_client = None

        # Voice assistant
        self.voice_assistant = None

        # Wake word detector
        self.wake_word_detector = None

        # Gyroscope sensor
        self.gyro_sensor = None

        # System monitor
        self.system_monitor = None

        # Video recorder
        self.video_recorder = None

        # GPS client
        self.gps_client = None

        # Minimap controller
        self.minimap_controller = None
        self.minimap_image_provider = None

        # Current heading from IMU (for minimap rotation)
        self._current_heading = 0.0

        # Setup components
        if self.config:
            print("="*60)
            print("VISOR APP INITIALIZATION")
            print("="*60)
            print("\n--- Setting up system monitor ---")
            self._setup_system_monitor()
            print("--- System monitor setup complete ---\n")
            print("\n--- Setting up video recorder ---")
            self._setup_video_recorder()
            print("--- Video recorder setup complete ---\n")
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
            print("\n--- Setting up gyroscope sensor ---")
            self._setup_gyro()
            print("--- Gyroscope sensor setup complete ---\n")
            print("\n--- Setting up GPS ---")
            self._setup_gps()
            print("--- GPS setup complete ---\n")

    def _setup_clients(self):
        """Initialize service clients"""
        try:
            # Direct camera (dual USB cameras with split-screen)
            dual_mode = self.config.get('video.dual_mode', True)
            device_left = self.config.get('video.device_left', '/dev/video0')
            device_right = self.config.get('video.device_right', '/dev/video1')
            width = self.config.get('video.width', 1280)
            height = self.config.get('video.height', 720)
            fps = self.config.get('video.fps', 30)

            print(f"Initializing dual camera setup...")
            print(f"  Left camera: {device_left}")
            print(f"  Right camera: {device_right}")
            print(f"  Resolution: {width}x{height}@{fps}fps")

            self.direct_camera = DirectCamera(
                sensor_id=0,  # Not used in dual mode
                width=width,
                height=height,
                fps=fps,
                dual_mode=dual_mode,
                device_left=device_left,
                device_right=device_right
            )

            if self.direct_camera.start():
                print("✓ Dual camera initialized successfully")
            else:
                print("⚠ Dual camera failed to initialize")
                self.direct_camera = None

            # Perception client - REMOVED (using direct inference now)
            # Initialize YOLO model for person-only detection
            try:
                import torch
                from ultralytics import YOLO

                # Fix PyTorch 2.6+ weights_only security issue
                # Add ultralytics classes to safe globals for model loading
                try:
                    import ultralytics.nn.tasks
                    import ultralytics.nn.modules

                    # Add all ultralytics model and module classes to safe globals
                    safe_classes = [
                        ultralytics.nn.tasks.DetectionModel,
                        ultralytics.nn.tasks.SegmentationModel,
                        ultralytics.nn.tasks.ClassificationModel,
                    ]

                    # Try to add additional classes if they exist
                    try:
                        safe_classes.extend([
                            ultralytics.nn.tasks.PoseModel,
                            ultralytics.nn.tasks.OBBModel,
                        ])
                    except AttributeError:
                        pass  # Older ultralytics version

                    # Add common nn modules
                    for name in dir(ultralytics.nn.modules):
                        obj = getattr(ultralytics.nn.modules, name)
                        if isinstance(obj, type):
                            safe_classes.append(obj)

                    torch.serialization.add_safe_globals(safe_classes)
                    print(f"[DETECTION] Added {len(safe_classes)} ultralytics classes to PyTorch safe globals")
                except Exception as e:
                    print(f"[DETECTION] Note: Could not add safe globals (PyTorch < 2.6?): {e}")

                model_path = self.config.get('perception.model_path', 'yolov8n.pt')
                print(f"[DETECTION] Loading YOLO model from {model_path}...")
                logger.info(f"Loading YOLO model from {model_path}")

                # Try loading with safe globals first, fallback to weights_only=False
                try:
                    self.yolo_model = YOLO(model_path)
                except Exception as load_error:
                    print(f"[DETECTION] First load attempt failed: {load_error}")
                    print("[DETECTION] Attempting fallback: patching torch.load with weights_only=False")

                    # Monkeypatch torch.load to use weights_only=False for this model
                    original_load = torch.load
                    def patched_load(*args, **kwargs):
                        kwargs['weights_only'] = False
                        return original_load(*args, **kwargs)

                    torch.load = patched_load
                    try:
                        self.yolo_model = YOLO(model_path)
                    finally:
                        torch.load = original_load  # Restore original
                    print("[DETECTION] Successfully loaded with fallback method")
                # Set model to CPU for stability (GPU can be enabled in config)
                device = self.config.get('perception.device', 'cpu')
                self.yolo_model.to(device)
                print(f"[DETECTION] ✓ YOLO model loaded successfully on {device}")
                print(f"[DETECTION] Person detection enabled (class ID 0 only)")
                print(f"[DETECTION] Using LEFT camera mapped to full HUD (as if camera is at nose bridge)")
                print(f"[DETECTION] Camera offset compensation: vertical={self.camera_vertical_offset_px}px down, horizontal={self.camera_horizontal_offset_px}px left")
                detection_rate = 30.0 / self.detection_frame_skip if self.detection_frame_skip > 0 else 30.0
                print(f"[DETECTION] Frame skip: {self.detection_frame_skip} (~{detection_rate:.1f} detections/sec @ 30fps)")
                logger.info(f"YOLO model loaded on {device} (person detection only, left camera)")
            except Exception as e:
                print(f"[DETECTION] ⚠ Failed to load YOLO model: {e}")
                logger.error(f"Failed to load YOLO model: {e}")
                self.yolo_model = None
            self.perception_client = None
            print("Perception: Using direct inference (service removed)")

            # HUD controller (pass system monitor for real telemetry)
            self.hud_controller = HUDController(self.config, system_monitor=self.system_monitor)
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

        # Thermal frame timer (only runs when enabled)
        self.thermal_timer = QTimer()
        self.thermal_timer.timeout.connect(self._update_thermal_frame)

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

            # Caption client - REMOVED (service deleted)
            # TODO: Re-implement direct Deepgram WebSocket client if needed
            self.caption_client = None
            logger.info("Caption client disabled (service removed)")
            print("⚠ Caption client disabled (service removed)")

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
            output_volume = self.config.get('assistant.output_volume', 3.0)
            system_prompt = self.config.get('assistant.system_prompt',
                "You are a helpful AI assistant integrated into an AR helmet. Provide concise, clear responses suitable for voice interaction.")

            print(f"Initializing OpenAI Realtime voice assistant...")
            print(f"  Voice: {voice}")
            print(f"  Input device: {input_device or 'default'}")
            print(f"  Output device: {output_device or 'default'}")
            print(f"  Output volume: {output_volume}")
            print(f"  System prompt: {system_prompt[:50]}...")

            self.voice_assistant = OpenAIRealtimeAssistant(
                openai_api_key=openai_key,
                system_prompt=system_prompt,
                voice=voice,
                input_device_index=input_device,
                output_device_index=output_device,
                output_volume=output_volume,
                wake_word_detector=self.wake_word_detector,  # Pass wake word detector reference
                frame_getter=self.get_current_camera_frame,  # Pass frame getter for on-demand vision
                system_monitor=self.system_monitor,  # Pass system monitor for telemetry
                video_recorder=self.video_recorder  # Pass video recorder for recording control
            )
            logger.info("OpenAI Realtime voice assistant initialized")
            print("✓ OpenAI Realtime voice assistant initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Voice assistant not available: {e}")
            print(f"ERROR: Voice assistant not available: {e}")
            traceback.print_exc()

    def _setup_gyro(self):
        """Setup gyroscope sensor"""
        try:
            # Get I2C bus from config (default 7, where we detected the BNO055)
            i2c_bus = self.config.get('gyro.i2c_bus', 7)

            print(f"Initializing gyroscope sensor on I2C bus {i2c_bus}...")

            self.gyro_sensor = GyroSensor(i2c_bus=i2c_bus)
            logger.info("Gyroscope sensor initialized")
            print("✓ Gyroscope sensor initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Gyroscope sensor not available: {e}")
            print(f"ERROR: Gyroscope sensor not available: {e}")
            traceback.print_exc()

    def _setup_system_monitor(self):
        """Setup system telemetry monitor"""
        try:
            print(f"Initializing system monitor...")

            self.system_monitor = SystemMonitor()
            logger.info("System monitor initialized")
            print("✓ System monitor initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"System monitor not available: {e}")
            print(f"ERROR: System monitor not available: {e}")
            traceback.print_exc()

    def _setup_gps(self):
        """Setup GPS client and minimap"""
        try:
            # Get GPS config
            gps_port = self.config.get('gps.port', '/dev/ttyUSB0')
            gps_baudrate = self.config.get('gps.baudrate', 115200)

            print(f"Initializing GPS client on {gps_port} at {gps_baudrate} baud...")

            self.gps_client = GPSClient(port=gps_port, baudrate=gps_baudrate)

            # Connect signals
            self.gps_client.positionUpdated.connect(self._on_gps_position_update)
            self.gps_client.statusUpdated.connect(self._on_gps_status_update)

            logger.info("GPS client initialized")
            print("✓ GPS client initialized successfully")

            # Setup minimap (pass minimap image provider from main)
            # Note: minimap_image_provider must be passed from main()

        except Exception as e:
            import traceback
            logger.warning(f"GPS client not available: {e}")
            print(f"ERROR: GPS client not available: {e}")
            traceback.print_exc()

    def _setup_video_recorder(self):
        """Setup full recorder (video + widgets + audio)"""
        try:
            # Get recording directory from config
            recording_dir = self.config.get('system.recording_dir', 'recordings')
            mic_device = self.config.get('assistant.input_device_index', None)

            print(f"Initializing full recorder (video + audio)...")
            print(f"  Output directory: {recording_dir}")
            print(f"  Microphone device: {mic_device or 'default'}")

            self.video_recorder = FullRecorder(
                output_dir=recording_dir,
                fps=30,
                mic_device_index=mic_device,
                enable_audio=True
            )

            # Set up callbacks
            def on_recording_started(filename, duration):
                logger.info(f"Recording started: {filename}")
                print(f"🔴 Recording started: {filename}")

            def on_recording_stopped(filename, frames, duration):
                logger.info(f"Recording saved: {filename} ({frames} frames, {duration:.1f}s)")
                print(f"⏹ Recording saved: {filename} ({frames} frames, {duration:.1f}s)")

            self.video_recorder.on_recording_started = on_recording_started
            self.video_recorder.on_recording_stopped = on_recording_stopped

            logger.info("Video recorder initialized")
            print("✓ Video recorder initialized successfully")

        except Exception as e:
            import traceback
            logger.warning(f"Video recorder not available: {e}")
            print(f"ERROR: Video recorder not available: {e}")
            traceback.print_exc()

    @Slot(float, float, float)
    def _emit_orientation_signal(self, heading: float, roll: float, pitch: float):
        """Thread-safe method to emit orientation signal to QML"""
        # Debug: print first few updates
        if not hasattr(self, '_orientation_debug_count'):
            self._orientation_debug_count = 0

        if self._orientation_debug_count < 5:
            print(f"Orientation update: heading={heading:.2f}°, roll={roll:.2f}°, pitch={pitch:.2f}°")
            self._orientation_debug_count += 1

        # Emit to QML
        self.orientationUpdated.emit(heading, roll, pitch)

    def _on_orientation_update(self, orientation_data: dict):
        """Handle orientation updates from gyroscope (called from sensor thread)"""
        # Extract all euler angles
        heading = orientation_data['euler'][0] or 0.0  # Heading/yaw is index 0
        roll = orientation_data['euler'][1] or 0.0  # Roll is index 1
        pitch = orientation_data['euler'][2] or 0.0  # Pitch is index 2

        # Update current heading for minimap
        self._current_heading = heading

        # Update minimap rotation if available
        if self.minimap_controller:
            self.minimap_controller.update_heading(heading)

        # Use QMetaObject.invokeMethod for thread-safe signal emission
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self,
            "_emit_orientation_signal",
            Qt.QueuedConnection,
            Q_ARG(float, heading),
            Q_ARG(float, roll),
            Q_ARG(float, pitch)
        )

    def _on_gps_position_update(self, lat: float, lon: float, altitude: float, heading: float):
        """Handle GPS position updates"""
        # Emit to QML
        self.gpsPositionUpdated.emit(lat, lon, altitude, heading)

        # Update minimap if available
        if self.minimap_controller:
            self.minimap_controller.update_position(lat, lon)

            # Use GPS heading if IMU not available and GPS has heading data
            if not self.gyro_sensor and heading and heading > 0:
                self.minimap_controller.update_heading(heading)

    def _on_gps_status_update(self, status: dict):
        """Handle GPS status updates"""
        # Emit to QML
        self.gpsStatusUpdated.emit(status)

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

                # Wait for wake word detector to fully initialize before starting voice assistant
                # This prevents microphone/PyAudio resource conflicts
                print("Waiting for wake word detector to initialize...")
                import time
                time.sleep(3)  # Give it 3 seconds to initialize PyAudio and open audio stream
                print("Wake word detector initialization complete")
            else:
                print("WARNING: No wake word detector to start")

            # Start voice assistant (but don't activate it - wake word will activate it)
            if self.voice_assistant:
                print("Starting voice assistant...")
                self.voice_assistant.start()
                print("Voice assistant started!")
            else:
                print("WARNING: No voice assistant to start")

            # Start gyroscope sensor (60 Hz update rate for smooth tracking)
            if self.gyro_sensor:
                print("Starting gyroscope sensor...")
                self.gyro_sensor.start(callback=self._on_orientation_update, rate_hz=60)
                print("Gyroscope sensor started!")
            else:
                print("WARNING: No gyroscope sensor to start")

            # Start system monitor
            if self.system_monitor:
                print("Starting system monitor...")
                self.system_monitor.start()
                print("System monitor started!")
            else:
                print("WARNING: No system monitor to start")

            # Start GPS client
            if self.gps_client:
                print("Starting GPS client...")
                if self.gps_client.start():
                    print("GPS client started!")
                else:
                    print("WARNING: GPS client failed to start (check permissions and connection)")
            else:
                print("WARNING: No GPS client to start")

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

        if self.caption_client:
            self.caption_client.stop()

        if self.wake_word_detector:
            self.wake_word_detector.stop()

        if self.voice_assistant:
            self.voice_assistant.stop()

        if self.gyro_sensor:
            self.gyro_sensor.stop()

        if self.system_monitor:
            self.system_monitor.stop()

        if self.gps_client:
            self.gps_client.stop()

        if self.video_recorder and self.video_recorder.is_recording_active():
            self.video_recorder.stop_recording()

        if self.direct_camera:
            self.direct_camera.stop()

        if self.perception_client:
            self.perception_client.disconnect()

        logger.info("Visor app stopped")

    def _update_frame(self):
        """Update video frame and run perception"""
        if not self.running or not self.direct_camera:
            return

        try:
            # Record frame for FPS tracking
            if self.hud_controller:
                self.hud_controller.record_frame()

            # Get frame from direct camera (numpy array in RGB format)
            frame = self.direct_camera.get_frame()
            if frame is None:
                return

            # IMPORTANT: Keep numpy array alive by storing it as instance variable
            # QImage is just a wrapper - the underlying data must persist
            self._current_frame = frame.copy()

            # Extract right camera only for snapshots (left half of merged frame)
            # Merged frame format: [right_camera | left_camera]
            import numpy as np
            height, width, channels = self._current_frame.shape
            half_width = width // 2
            self._right_camera_frame = self._current_frame[:, :half_width].copy()  # Left half = right camera

            # Convert right camera to QImage for snapshot storage
            right_bytes_per_line = channels * half_width
            right_qimage = QImage(self._right_camera_frame.data, half_width, height, right_bytes_per_line, QImage.Format_RGB888)
            self._current_qimage = right_qimage.copy()  # Store right camera for snapshots

            # Convert full merged frame to QImage for display
            bytes_per_line = channels * width
            qimage = QImage(self._current_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            if qimage.isNull():
                return

            # Add frame to full recorder if recording (capture full screen with widgets)
            if self.video_recorder and self.video_recorder.is_recording_active():
                # Capture the full QML window (includes camera feed + all widgets/overlays)
                if self.qml_window:
                    try:
                        # Grab the QML window framebuffer
                        qml_image = self.qml_window.grabWindow()
                        if not qml_image.isNull():
                            # Convert QImage to numpy array
                            import numpy as np
                            width = qml_image.width()
                            height = qml_image.height()

                            # Convert to RGB888 format if needed
                            if qml_image.format() != QImage.Format_RGB888:
                                qml_image = qml_image.convertToFormat(QImage.Format_RGB888)

                            # Get pointer to image data
                            ptr = qml_image.constBits()
                            frame_array = np.array(ptr).reshape((height, width, 3))

                            # Add full screen capture (with widgets) to recorder
                            self.video_recorder.add_frame(frame_array)
                    except Exception as e:
                        logger.error(f"Error capturing QML window: {e}")

            # Use image provider for zero-copy frame updates (fastest)
            if self.image_provider:
                self.image_provider.setImage(qimage)
                # Emit update signal with timestamp to trigger QML refresh
                self.frameUpdated.emit(f"image://video/{self.frame_counter}")
                self.frame_counter += 1

            # Run person detection with frame skipping
            if self.yolo_model:
                self.detection_frame_counter += 1
                if self.detection_frame_counter >= self.detection_frame_skip:
                    self.detection_frame_counter = 0
                    self._run_person_detection(self._current_frame)
            elif self.frame_counter == 30:  # Only log once after 30 frames
                print("[DETECTION] ⚠ YOLO model not loaded - skipping detection")

        except Exception as e:
            print(f"Frame update error: {e}")
            logger.error(f"Frame update error: {e}")

    def _run_person_detection(self, frame):
        """Run YOLO person detection on frame"""
        try:
            import numpy as np

            # Get camera dimensions from full merged frame
            frame_height, frame_width = frame.shape[:2]

            # Extract left camera only (right half of merged image)
            # Merged frame format: [right_camera | left_camera]
            # Left camera is pixels 1280-2560 (right half)
            half_width = frame_width // 2
            left_camera_frame = frame[:, half_width:]  # Right half = left camera

            # Run YOLO inference on left camera only
            # Use configured NMS threshold to eliminate duplicate detections
            conf_threshold = self.config.get('perception.confidence_threshold', 0.7)
            nms_threshold = self.config.get('perception.nms_threshold', 0.4)
            max_det = self.config.get('perception.max_detections', 100)

            results = self.yolo_model(
                left_camera_frame,
                conf=conf_threshold,
                iou=nms_threshold,
                max_det=max_det,
                verbose=False
            )

            # Extract detections
            detections = []

            # Get left camera dimensions
            left_cam_height, left_cam_width = left_camera_frame.shape[:2]

            for result in results:
                boxes = result.boxes

                for box in boxes:
                    # Get class ID and confidence
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])

                    # Filter for person class only (class ID 0 in COCO dataset)
                    if cls != 0:  # 0 = person
                        continue

                    # Get bounding box coordinates (xyxy format) relative to left camera frame
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                    # Calculate center and dimensions
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    width = x2 - x1
                    height = y2 - y1

                    # Apply offset adjustments to compensate for camera position
                    # Vertical: Camera is 2 inches ABOVE eyeline, so shift detections DOWN
                    # Horizontal: Camera is to the LEFT of nose bridge, so shift detections LEFT (if needed)
                    center_x_adjusted = center_x - self.camera_horizontal_offset_px
                    center_y_adjusted = center_y + self.camera_vertical_offset_px

                    # Ensure adjusted coordinates stay within frame bounds
                    x1_adjusted = max(0, center_x_adjusted - width / 2)
                    x2_adjusted = min(left_cam_width, center_x_adjusted + width / 2)
                    y1_adjusted = max(0, center_y_adjusted - height / 2)
                    y2_adjusted = min(left_cam_height, center_y_adjusted + height / 2)

                    # Convert to normalized coordinates (0.0 to 1.0) relative to left camera frame
                    # This maps the left camera to fill the entire HUD display
                    # Person centered in left camera will appear centered on HUD
                    detection = {
                        'x': float(x1_adjusted / left_cam_width),
                        'y': float(y1_adjusted / left_cam_height),
                        'width': float((x2_adjusted - x1_adjusted) / left_cam_width),
                        'height': float((y2_adjusted - y1_adjusted) / left_cam_height),
                        'label': 'person',
                        'confidence': float(conf)
                    }

                    detections.append(detection)

            # Update stored detections
            self._current_detections = detections

            # Emit signal to QML with detections
            self.detectionsUpdated.emit(detections)

        except Exception as e:
            print(f"[DETECTION] ⚠ Error during detection: {e}")
            logger.error(f"Person detection error: {e}")
            import traceback
            traceback.print_exc()
            # Don't crash - just skip this frame
            pass

    def _update_thermal_frame(self):
        """Update thermal camera frame (only called when thermal is enabled)"""
        if not self.thermal_camera or not self.thermal_enabled:
            return

        try:
            # Get thermal frame
            frame = self.thermal_camera.get_frame()
            if frame is None:
                return

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert to QImage
            height, width, channels = rgb_frame.shape
            bytes_per_line = channels * width
            qimage = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            # Update image provider
            if self.image_provider:
                self.image_provider.setImage(qimage)

            # Emit signal for thermal (use same image provider, just different signal)
            self.thermalFrameUpdated.emit(f"image://video/{self.thermal_counter}")
            self.thermal_counter += 1

        except Exception as e:
            logger.error(f"Thermal frame update error: {e}")

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
    def toggleThermal(self):
        """Toggle thermal camera overlay"""
        self.thermal_enabled = not self.thermal_enabled

        if self.thermal_enabled:
            print("[Thermal] Enabling thermal overlay")
            # Initialize thermal camera if not already done
            if not self.thermal_camera:
                self.thermal_camera = ThermalCamera(device='/dev/video2', width=640, height=512)
                if not self.thermal_camera.start():
                    print("[Thermal] Failed to start thermal camera")
                    self.thermal_enabled = False
                    return

            # Start thermal update timer (30 FPS for low latency)
            self.thermal_timer.start(33)  # ~30 FPS
        else:
            print("[Thermal] Disabling thermal overlay")
            # Stop thermal timer
            self.thermal_timer.stop()

        logger.info(f"Thermal overlay: {'enabled' if self.thermal_enabled else 'disabled'}")

    @Slot()
    def triggerThermalNUC(self):
        """Trigger NUC (Non-Uniformity Correction) on thermal camera"""
        if self.thermal_camera:
            print("[Thermal] Triggering NUC calibration...")
            self.thermal_camera.trigger_nuc()
        else:
            print("[Thermal] Cannot trigger NUC - thermal camera not initialized")
            logger.warning("NUC trigger requested but thermal camera not active")

    @Slot()
    def captureAndAnalyze(self):
        """Capture current frame and analyze with Claude API"""
        print("\n" + "="*60)
        print("=== SNAPSHOT TRIGGERED (P key pressed) ===")
        print("=== Using RIGHT camera for analysis ===")
        print("="*60)
        logger.info("Capture and analyze triggered (right camera)")

        if self._current_qimage is None:
            logger.warning("No frame available to capture")
            print("ERROR: No frame available to capture")
            self.snapshotAnalyzed.emit("", "Error: No frame available to analyze")
            return

        print("✓ Right camera frame available, starting analysis...")
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
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Snapshot analysis error: {e}")
                logger.error(f"Full traceback:\n{error_trace}")
                print(f"ERROR: Snapshot analysis failed:")
                print(error_trace)
                self.snapshotAnalyzed.emit("", f"Analysis failed: {str(e)}\n\nCheck terminal for details.")

        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=analyze_async)
        thread.daemon = True
        thread.start()

    def _analyze_with_claude(self, image_base64: str) -> str:
        """Analyze image using Claude API"""
        import anthropic
        import os

        try:
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

            print(f"API key found (anthropic v{anthropic.__version__})")
            print(f"Initializing Claude API client...")
            client = anthropic.Anthropic(api_key=api_key)

            # Try multiple model names in order of preference
            models_to_try = [
                "claude-sonnet-4-20250514",      # Latest Sonnet 4
                "claude-3-5-sonnet-20250219",    # Latest Claude 3.5 Sonnet
                "claude-3-5-sonnet-20241022",    # Older Claude 3.5 Sonnet
                "claude-3-5-sonnet-latest",      # Generic latest
                "claude-3-5-sonnet",             # Fallback
            ]

            last_error = None
            for model_name in models_to_try:
                try:
                    print(f"Trying model: {model_name}")

                    message = client.messages.create(
                        model=model_name,
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
                                        "text": "What am I looking at? Provide a brief, concise description of the scene, objects, and any people visible."
                                    }
                                ],
                            }
                        ],
                    )

                    print(f"✓ Claude API analysis complete with {model_name}!")
                    return message.content[0].text

                except anthropic.APIStatusError as e:
                    if e.status_code == 404:
                        print(f"  Model {model_name} not found, trying next...")
                        last_error = e
                        continue
                    else:
                        # Other errors (auth, rate limit, etc.) should not try fallback
                        raise

            # If we get here, all models failed
            if last_error:
                raise last_error
            else:
                raise Exception("All model attempts failed")

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
        except anthropic.APIStatusError as e:
            # Handle specific API errors (404, 401, etc.)
            error_msg = f"""Claude API Error ({e.status_code}): {e.message}

Common issues:
- 401: Invalid API key
- 404: Model not found or endpoint incorrect
- 429: Rate limit exceeded

Current model: {model_name if 'model_name' in locals() else 'unknown'}

Check your API key and try again.
"""
            logger.error(f"Claude API status error: {e.status_code} - {e.message}")
            print(f"ERROR: Claude API returned {e.status_code}")
            print(error_msg)
            return error_msg
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Claude API error: {e}")
            logger.error(f"Full traceback:\n{error_trace}")
            print(f"ERROR: Claude API call failed:")
            print(error_trace)
            error_msg = f"Analysis error: {str(e)}\n\nCheck terminal for full error details."
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

    # Create and register minimap image provider
    minimap_image_provider = MinimapImageProvider()
    engine.addImageProvider("minimap", minimap_image_provider)

    # Create visor app instance BEFORE loading QML (qml_window will be set later)
    visor_app = VisorApp(config, image_provider, qml_window=None)

    # Create and setup minimap controller
    visor_app.minimap_image_provider = minimap_image_provider
    visor_app.minimap_controller = MinimapController(minimap_image_provider)
    visor_app.minimap_controller.minimapUpdated.connect(visor_app.minimapUpdated.emit)

    qml_file = Path(__file__).parent / "qml" / "main.qml"

    if not qml_file.exists():
        logger.error(f"QML file not found: {qml_file}")
        sys.exit(1)

    # Set context properties BEFORE loading QML
    engine.rootContext().setContextProperty("config", config.all)
    engine.rootContext().setContextProperty("visorApp", visor_app)

    # Load QML with absolute path
    qml_url = QUrl.fromLocalFile(str(qml_file.resolve()))
    engine.load(qml_url)

    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML file")
        sys.exit(1)

    # Get QML window for screen capture and set it on visor_app
    qml_window = engine.rootObjects()[0]
    visor_app.qml_window = qml_window

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