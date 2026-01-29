"""
Orbbec Gemini 335 depth camera interface
Provides RGB, depth, IR streams and IMU data for AR anchoring and gesture detection
"""
import numpy as np
import cv2
import threading
import time
import math
from typing import Optional, Tuple, Callable
from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat


class Gemini335Camera:
    """Interface for Orbbec Gemini 335 depth camera with IMU support"""

    def __init__(self,
                 depth_width=640,
                 depth_height=480,
                 color_width=1280,
                 color_height=800,
                 fps=30,
                 enable_imu=True):
        """
        Initialize Gemini 335 camera

        Args:
            depth_width: Depth stream width (default 640)
            depth_height: Depth stream height (default 480)
            color_width: Color stream width (default 1280)
            color_height: Color stream height (default 800)
            fps: Frame rate (default 30)
            enable_imu: Enable IMU (accelerometer/gyroscope) streams (default True)
        """
        self.depth_width = depth_width
        self.depth_height = depth_height
        self.color_width = color_width
        self.color_height = color_height
        self.fps = fps
        self.enable_imu = enable_imu

        self.pipeline = None
        self.config = None
        self.device = None

        self.running = False
        self.capture_thread = None
        self.imu_thread = None

        # Latest frames (thread-safe with locks)
        self.color_frame = None
        self.depth_frame = None
        self.ir_frame = None
        self.frame_lock = threading.Lock()

        # IMU data (thread-safe with lock)
        self.accel_data = None  # [x, y, z] in m/s²
        self.gyro_data = None   # [x, y, z] in rad/s
        self.imu_lock = threading.Lock()

        # Orientation estimation (complementary filter)
        self.orientation = {'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0}  # degrees
        self.orientation_lock = threading.Lock()
        self._last_imu_time = None
        self._alpha = 0.95  # Complementary filter coefficient (lower = more accel smoothing)

        # IMU callback
        self.imu_callback = None
        self._last_callback_time = 0
        self._callback_interval = 1.0 / 30.0  # Throttle callback to 30Hz max

        # Frame counters for debugging
        self.color_frame_count = 0
        self.depth_frame_count = 0
        self.imu_sample_count = 0

    def start(self) -> bool:
        """
        Start camera capture

        Returns:
            True if successful, False otherwise
        """
        try:
            print("[Gemini335] Initializing Orbbec Gemini 335...")

            # Create pipeline and config
            self.pipeline = Pipeline()
            self.config = Config()

            # Get device info
            self.device = self.pipeline.get_device()
            device_info = self.device.get_device_info()
            print(f"[Gemini335] Device: {device_info.get_name()}")
            print(f"[Gemini335] Serial: {device_info.get_serial_number()}")
            print(f"[Gemini335] Firmware: {device_info.get_firmware_version()}")

            # Enable depth stream - use first available profile if requested doesn't match
            try:
                depth_profile_list = self.pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
                if depth_profile_list and depth_profile_list.get_count() > 0:
                    depth_profile = None
                    # Try requested resolution first
                    try:
                        depth_profile = depth_profile_list.get_video_stream_profile(
                            self.depth_width, self.depth_height, OBFormat.Y16, self.fps
                        )
                    except:
                        pass
                    # Fallback: use first available profile
                    if depth_profile is None:
                        depth_profile = depth_profile_list.get_stream_profile_by_index(0).as_video_stream_profile()
                        print(f"[Gemini335] Using default depth profile")
                    self.config.enable_stream(depth_profile)
                    print(f"[Gemini335] Depth stream enabled")
                else:
                    print("[Gemini335] Warning: No depth profiles available")
            except Exception as e:
                print(f"[Gemini335] Warning: Could not enable depth stream: {e}")

            # Enable color stream - use first available profile if requested doesn't match
            try:
                color_profile_list = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
                if color_profile_list and color_profile_list.get_count() > 0:
                    color_profile = None
                    # Try requested resolution first
                    try:
                        color_profile = color_profile_list.get_video_stream_profile(
                            self.color_width, self.color_height, OBFormat.RGB, self.fps
                        )
                    except:
                        pass
                    # Fallback: use first available profile
                    if color_profile is None:
                        color_profile = color_profile_list.get_stream_profile_by_index(0).as_video_stream_profile()
                        print(f"[Gemini335] Using default color profile")
                    self.config.enable_stream(color_profile)
                    print(f"[Gemini335] Color stream enabled")
                else:
                    print("[Gemini335] Warning: No color profiles available")
            except Exception as e:
                print(f"[Gemini335] Warning: Could not enable color stream: {e}")

            # Enable IR stream (optional, for low-light detection)
            try:
                ir_profile_list = self.pipeline.get_stream_profile_list(OBSensorType.IR_SENSOR)
                if ir_profile_list and ir_profile_list.get_count() > 0:
                    ir_profile = None
                    try:
                        ir_profile = ir_profile_list.get_video_stream_profile(
                            self.depth_width, self.depth_height, OBFormat.Y8, self.fps
                        )
                    except:
                        pass
                    if ir_profile is None:
                        ir_profile = ir_profile_list.get_stream_profile_by_index(0).as_video_stream_profile()
                        print(f"[Gemini335] Using default IR profile")
                    self.config.enable_stream(ir_profile)
                    print(f"[Gemini335] IR stream enabled")
                else:
                    print("[Gemini335] Warning: No IR profiles available")
            except Exception as e:
                print(f"[Gemini335] Warning: Could not enable IR stream: {e}")

            # Start pipeline
            self.pipeline.start(self.config)
            print("[Gemini335] Pipeline started successfully")

            # Start capture thread
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            print("[Gemini335] Capture thread started")

            # Setup IMU if enabled
            if self.enable_imu:
                self._setup_imu()

            return True

        except Exception as e:
            print(f"[Gemini335] ERROR: Failed to start camera: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _setup_imu(self):
        """Setup IMU (accelerometer and gyroscope) streams"""
        try:
            # Get sensor list from device
            sensor_list = self.device.get_sensor_list()
            has_accel = False
            has_gyro = False

            for i in range(sensor_list.get_count()):
                sensor = sensor_list.get_sensor_by_index(i)
                sensor_type = sensor.get_type()
                if sensor_type == OBSensorType.ACCEL_SENSOR:
                    has_accel = True
                    print("[Gemini335] Found accelerometer sensor")
                elif sensor_type == OBSensorType.GYRO_SENSOR:
                    has_gyro = True
                    print("[Gemini335] Found gyroscope sensor")

            if has_accel and has_gyro:
                # Start IMU polling thread
                self.imu_thread = threading.Thread(target=self._imu_loop, daemon=True)
                self.imu_thread.start()
                print("[Gemini335] IMU thread started")
            else:
                print(f"[Gemini335] IMU not available (accel={has_accel}, gyro={has_gyro})")
                self.enable_imu = False

        except Exception as e:
            print(f"[Gemini335] Warning: Could not setup IMU: {e}")
            self.enable_imu = False

    def _imu_loop(self):
        """Background thread for IMU data polling"""
        print("[Gemini335] IMU loop started")

        try:
            # Get accel and gyro sensors
            sensor_list = self.device.get_sensor_list()
            accel_sensor = None
            gyro_sensor = None

            for i in range(sensor_list.get_count()):
                sensor = sensor_list.get_sensor_by_index(i)
                if sensor.get_type() == OBSensorType.ACCEL_SENSOR:
                    accel_sensor = sensor
                elif sensor.get_type() == OBSensorType.GYRO_SENSOR:
                    gyro_sensor = sensor

            if not accel_sensor or not gyro_sensor:
                print("[Gemini335] IMU sensors not found in loop")
                return

            # Configure and start IMU streams using frame callbacks
            def accel_callback(frame):
                try:
                    data = frame.get_data()
                    if data is not None and len(data) >= 3:
                        # Data is typically [x, y, z] acceleration in m/s²
                        accel = np.array(data[:3], dtype=np.float32)
                        with self.imu_lock:
                            self.accel_data = accel
                        self._update_orientation()
                except Exception as e:
                    pass  # Silently handle frame errors

            def gyro_callback(frame):
                try:
                    data = frame.get_data()
                    if data is not None and len(data) >= 3:
                        # Data is typically [x, y, z] angular velocity in rad/s or deg/s
                        gyro = np.array(data[:3], dtype=np.float32)
                        with self.imu_lock:
                            self.gyro_data = gyro
                            self.imu_sample_count += 1
                except Exception as e:
                    pass  # Silently handle frame errors

            # Try to start sensor streams with callbacks
            try:
                accel_profiles = accel_sensor.get_stream_profile_list()
                if accel_profiles and accel_profiles.get_count() > 0:
                    accel_profile = accel_profiles.get_stream_profile_by_index(0)
                    accel_sensor.start(accel_profile, accel_callback)
                    print("[Gemini335] Accelerometer stream started")

                gyro_profiles = gyro_sensor.get_stream_profile_list()
                if gyro_profiles and gyro_profiles.get_count() > 0:
                    gyro_profile = gyro_profiles.get_stream_profile_by_index(0)
                    gyro_sensor.start(gyro_profile, gyro_callback)
                    print("[Gemini335] Gyroscope stream started")

            except Exception as e:
                print(f"[Gemini335] Could not start IMU streams: {e}")
                # Fall back to polling mode
                self._imu_poll_loop(accel_sensor, gyro_sensor)
                return

            # Keep thread alive while running
            while self.running:
                time.sleep(0.1)

        except Exception as e:
            print(f"[Gemini335] IMU loop error: {e}")
            import traceback
            traceback.print_exc()

        print("[Gemini335] IMU loop stopped")

    def _imu_poll_loop(self, accel_sensor, gyro_sensor):
        """Fallback polling mode for IMU if streaming doesn't work"""
        print("[Gemini335] Using IMU polling mode")

        while self.running:
            try:
                # Poll at ~100Hz
                time.sleep(0.01)
                # Note: Direct polling may not be supported by all SDK versions
                # This is a fallback that may need adjustment
            except Exception as e:
                time.sleep(0.1)

    def _update_orientation(self):
        """Update orientation estimate using complementary filter"""
        current_time = time.time()

        with self.imu_lock:
            if self.accel_data is None or self.gyro_data is None:
                return

            accel = self.accel_data.copy()
            gyro = self.gyro_data.copy()

        # Calculate time delta
        if self._last_imu_time is None:
            self._last_imu_time = current_time
            return

        dt = current_time - self._last_imu_time
        self._last_imu_time = current_time

        if dt <= 0 or dt > 1.0:  # Skip if invalid dt
            return

        # Calculate pitch and roll from accelerometer (gravity vector)
        ax, ay, az = accel
        accel_pitch = math.atan2(ax, math.sqrt(ay*ay + az*az)) * 180 / math.pi
        accel_roll = math.atan2(ay, math.sqrt(ax*ax + az*az)) * 180 / math.pi

        # Get gyro rates (convert to deg/s if in rad/s)
        gx, gy, gz = gyro
        # Assuming gyro data is in deg/s (adjust if rad/s)
        gyro_pitch_rate = gx
        gyro_roll_rate = gy
        gyro_yaw_rate = gz

        with self.orientation_lock:
            # Complementary filter: combine gyro integration with accel angles
            self.orientation['pitch'] = self._alpha * (self.orientation['pitch'] + gyro_pitch_rate * dt) + (1 - self._alpha) * accel_pitch
            self.orientation['roll'] = self._alpha * (self.orientation['roll'] + gyro_roll_rate * dt) + (1 - self._alpha) * accel_roll
            # Yaw from gyro only (no magnetometer)
            self.orientation['yaw'] += gyro_yaw_rate * dt

            # Normalize yaw to -180 to 180
            while self.orientation['yaw'] > 180:
                self.orientation['yaw'] -= 360
            while self.orientation['yaw'] < -180:
                self.orientation['yaw'] += 360

        # Call callback if set (throttled to avoid overwhelming the system)
        if self.imu_callback:
            now = time.time()
            if now - self._last_callback_time >= self._callback_interval:
                self._last_callback_time = now
                try:
                    self.imu_callback(self.get_orientation())
                except Exception as e:
                    pass  # Don't crash on callback errors

    def _capture_loop(self):
        """Background thread for continuous frame capture"""
        print("[Gemini335] Capture loop started")
        error_count = 0
        max_errors_to_log = 3

        while self.running:
            try:
                # Wait for frames with 1000ms timeout
                frames = self.pipeline.wait_for_frames(1000)
                if not frames:
                    continue

                # Get color frame
                color_frame = frames.get_color_frame()
                if color_frame:
                    width = color_frame.get_width()
                    height = color_frame.get_height()
                    data = np.asanyarray(color_frame.get_data())
                    expected_size = height * width * 3

                    if data.size == expected_size:
                        # Raw RGB data
                        color_image = data.reshape((height, width, 3))
                        color_image = cv2.cvtColor(color_image, cv2.COLOR_RGB2BGR)
                        with self.frame_lock:
                            self.color_frame = color_image.copy()
                            self.color_frame_count += 1
                    elif data.size < expected_size:
                        # Likely MJPEG compressed - try to decode
                        try:
                            color_image = cv2.imdecode(data, cv2.IMREAD_COLOR)
                            if color_image is not None:
                                with self.frame_lock:
                                    self.color_frame = color_image.copy()
                                    self.color_frame_count += 1
                        except:
                            pass  # Skip frame silently

                # Get depth frame
                depth_frame = frames.get_depth_frame()
                if depth_frame:
                    width = depth_frame.get_width()
                    height = depth_frame.get_height()
                    data = np.asanyarray(depth_frame.get_data())
                    expected_size = height * width

                    if data.size == expected_size * 2:  # 16-bit depth
                        depth_image = data.view(np.uint16).reshape((height, width))
                        with self.frame_lock:
                            self.depth_frame = depth_image.copy()
                            self.depth_frame_count += 1
                    elif data.size == expected_size:
                        depth_image = data.reshape((height, width)).astype(np.uint16)
                        with self.frame_lock:
                            self.depth_frame = depth_image.copy()
                            self.depth_frame_count += 1

                # Get IR frame (optional)
                ir_frame = frames.get_ir_frame()
                if ir_frame:
                    width = ir_frame.get_width()
                    height = ir_frame.get_height()
                    data = np.asanyarray(ir_frame.get_data())
                    expected_size = height * width

                    if data.size == expected_size:
                        ir_image = data.reshape((height, width))
                        with self.frame_lock:
                            self.ir_frame = ir_image.copy()

                error_count = 0  # Reset on success

            except Exception as e:
                error_count += 1
                if error_count <= max_errors_to_log:
                    print(f"[Gemini335] Frame capture error: {e}")
                elif error_count == max_errors_to_log + 1:
                    print("[Gemini335] Suppressing further frame errors...")
                time.sleep(0.01)

        print("[Gemini335] Capture loop stopped")

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get latest color, depth, and IR frames

        Returns:
            Tuple of (color_frame, depth_frame, ir_frame)
            Any can be None if not available
        """
        with self.frame_lock:
            return (
                self.color_frame.copy() if self.color_frame is not None else None,
                self.depth_frame.copy() if self.depth_frame is not None else None,
                self.ir_frame.copy() if self.ir_frame is not None else None
            )

    def get_color_frame(self) -> Optional[np.ndarray]:
        """Get latest color frame (BGR format)"""
        with self.frame_lock:
            return self.color_frame.copy() if self.color_frame is not None else None

    def get_depth_frame(self) -> Optional[np.ndarray]:
        """Get latest depth frame (uint16, values in mm)"""
        with self.frame_lock:
            return self.depth_frame.copy() if self.depth_frame is not None else None

    def get_ir_frame(self) -> Optional[np.ndarray]:
        """Get latest IR frame"""
        with self.frame_lock:
            return self.ir_frame.copy() if self.ir_frame is not None else None

    def get_depth_at_point(self, x: int, y: int) -> Optional[float]:
        """
        Get depth value at specific pixel coordinates

        Args:
            x: X coordinate (column)
            y: Y coordinate (row)

        Returns:
            Depth in meters, or None if unavailable
        """
        with self.frame_lock:
            if self.depth_frame is None:
                return None

            h, w = self.depth_frame.shape
            if 0 <= x < w and 0 <= y < h:
                depth_mm = self.depth_frame[y, x]
                return depth_mm / 1000.0  # Convert mm to meters
            return None

    def get_orientation(self) -> dict:
        """
        Get current orientation estimate from IMU

        Returns:
            Dict with 'pitch', 'roll', 'yaw' in degrees
        """
        with self.orientation_lock:
            return self.orientation.copy()

    def get_imu_data(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get raw IMU data

        Returns:
            Tuple of (accel_xyz, gyro_xyz) or (None, None) if unavailable
        """
        with self.imu_lock:
            accel = self.accel_data.copy() if self.accel_data is not None else None
            gyro = self.gyro_data.copy() if self.gyro_data is not None else None
            return accel, gyro

    def set_imu_callback(self, callback: Optional[Callable[[dict], None]]):
        """
        Set callback for orientation updates

        Args:
            callback: Function that receives orientation dict with pitch, roll, yaw
        """
        self.imu_callback = callback

    def reset_orientation(self):
        """Reset yaw to zero (pitch/roll are gravity-referenced)"""
        with self.orientation_lock:
            self.orientation['yaw'] = 0.0
        print("[Gemini335] Orientation yaw reset to 0")

    def is_imu_available(self) -> bool:
        """Check if IMU is available and providing data"""
        with self.imu_lock:
            return self.enable_imu and self.accel_data is not None and self.gyro_data is not None

    def stop(self):
        """Stop camera capture and cleanup"""
        print("[Gemini335] Stopping camera...")
        self.running = False

        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)

        if self.imu_thread:
            self.imu_thread.join(timeout=2.0)

        if self.pipeline:
            try:
                self.pipeline.stop()
                print("[Gemini335] Pipeline stopped")
            except Exception as e:
                print(f"[Gemini335] Error stopping pipeline: {e}")

        print("[Gemini335] Camera stopped")

    def get_stats(self) -> dict:
        """Get camera statistics"""
        stats = {
            'color_frames': self.color_frame_count,
            'depth_frames': self.depth_frame_count,
            'running': self.running,
            'imu_enabled': self.enable_imu,
            'imu_samples': self.imu_sample_count
        }
        if self.enable_imu:
            stats['orientation'] = self.get_orientation()
        return stats
