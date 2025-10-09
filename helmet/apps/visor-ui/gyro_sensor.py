#!/usr/bin/env python3
"""
BNO055 Gyroscope/IMU Sensor Service
Uses direct I2C communication via smbus2
"""

import time
import threading
import struct
from typing import Optional, Callable
import logging

try:
    from smbus2 import SMBus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    print("WARNING: smbus2 not available - install with: pip install smbus2")

logger = logging.getLogger(__name__)

# BNO055 Register addresses
BNO055_CHIP_ID_ADDR = 0x00
BNO055_OPR_MODE_ADDR = 0x3D
BNO055_EULER_H_LSB_ADDR = 0x1A
BNO055_QUATERNION_DATA_W_LSB_ADDR = 0x20
BNO055_GYRO_DATA_X_LSB_ADDR = 0x14
BNO055_ACCEL_DATA_X_LSB_ADDR = 0x08
BNO055_MAG_DATA_X_LSB_ADDR = 0x0E
BNO055_TEMP_ADDR = 0x34
BNO055_CALIB_STAT_ADDR = 0x35

# Operation modes
OPERATION_MODE_CONFIG = 0x00
OPERATION_MODE_NDOF = 0x0C  # 9DOF fusion mode (slower, smoothed)
OPERATION_MODE_IMUPLUS = 0x08  # 6DOF IMU mode (faster, gyro+accel only)
OPERATION_MODE_ACCGYRO = 0x05  # Raw accel + gyro (fastest, no fusion)

class GyroSensor:
    """BNO055 9-DOF absolute orientation sensor"""

    def __init__(self, i2c_bus=7, address=0x28):
        """
        Initialize BNO055 sensor

        Args:
            i2c_bus: I2C bus number (default 7, where BNO055 was detected)
            address: I2C address (default 0x28)
        """
        self.i2c_bus = i2c_bus
        self.address = address
        self.sensor = None
        self.running = False
        self.thread = None
        self.callback = None

        # Current orientation data
        self.euler = (0.0, 0.0, 0.0)  # (heading, roll, pitch)
        self.quaternion = (0.0, 0.0, 0.0, 0.0)  # (w, x, y, z)
        self.gyro = (0.0, 0.0, 0.0)  # (x, y, z) rad/s
        self.accel = (0.0, 0.0, 0.0)  # (x, y, z) m/s^2
        self.mag = (0.0, 0.0, 0.0)  # (x, y, z) uT
        self.temperature = 0
        self.calibration = (0, 0, 0, 0)  # (sys, gyro, accel, mag) 0-3

        # Integrated orientation from raw gyro (for instant response)
        self.integrated_roll = 0.0
        self.integrated_pitch = 0.0
        self.last_update_time = None

        self.lock = threading.Lock()

        if not SMBUS_AVAILABLE:
            logger.error("smbus2 not available")
            return

        try:
            # Open I2C bus
            self.bus = SMBus(i2c_bus)

            # Verify chip ID
            chip_id = self.bus.read_byte_data(self.address, BNO055_CHIP_ID_ADDR)
            if chip_id != 0xA0:
                logger.error(f"Invalid chip ID: {chip_id:#x} (expected 0xA0)")
                print(f"ERROR: Invalid BNO055 chip ID: {chip_id:#x}")
                self.bus.close()
                return

            # Reset to config mode
            self.bus.write_byte_data(self.address, BNO055_OPR_MODE_ADDR, OPERATION_MODE_CONFIG)
            time.sleep(0.025)

            # Set to ACCGYRO mode (raw sensors, instant response, no fusion lag)
            # This gives us raw gyro data for immediate head tracking
            self.bus.write_byte_data(self.address, BNO055_OPR_MODE_ADDR, OPERATION_MODE_ACCGYRO)
            time.sleep(0.02)  # Give sensor time to switch modes

            # Verify mode was set
            current_mode = self.bus.read_byte_data(self.address, BNO055_OPR_MODE_ADDR)
            print(f"BNO055 operating mode: {current_mode:#x} (expected 0x05 for ACCGYRO - raw mode)")

            self.sensor = True  # Mark as initialized
            logger.info(f"BNO055 initialized on I2C bus {i2c_bus} at address {address:#x}")
            print(f"✓ BNO055 sensor initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize BNO055: {e}")
            print(f"ERROR: Failed to initialize BNO055: {e}")
            import traceback
            traceback.print_exc()
            self.sensor = None

    def start(self, callback: Optional[Callable] = None, rate_hz: int = 30):
        """
        Start sensor reading thread

        Args:
            callback: Optional callback function(orientation_data) called on each update
            rate_hz: Update rate in Hz (default 30)
        """
        if not self.sensor:
            logger.error("Cannot start - sensor not initialized")
            return False

        if self.running:
            logger.warning("Sensor already running")
            return True

        self.callback = callback
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, args=(rate_hz,), daemon=True)
        self.thread.start()

        logger.info(f"Gyro sensor started at {rate_hz} Hz")
        return True

    def stop(self):
        """Stop sensor reading"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Gyro sensor stopped")

    def _read_loop(self, rate_hz: int):
        """Main sensor reading loop"""
        interval = 1.0 / rate_hz
        read_count = 0

        while self.running:
            try:
                start_time = time.time()
                read_count += 1

                # Read all sensor data
                with self.lock:
                    # In ACCGYRO mode, Euler angles aren't available (fusion disabled)
                    # Instead, calculate roll/pitch from raw accelerometer (gravity vector)
                    # This is INSTANT - no fusion lag!

                    # Read accelerometer (6 bytes: x, y, z as signed 16-bit ints)
                    # Units: 1 m/s^2 = 100 LSB
                    accel_data = self.bus.read_i2c_block_data(self.address, BNO055_ACCEL_DATA_X_LSB_ADDR, 6)
                    ax = struct.unpack('<h', bytes(accel_data[0:2]))[0] / 100.0
                    ay = struct.unpack('<h', bytes(accel_data[2:4]))[0] / 100.0
                    az = struct.unpack('<h', bytes(accel_data[4:6]))[0] / 100.0
                    self.accel = (ax, ay, az)

                    # Calculate roll and pitch from gravity vector (instant response!)
                    import math
                    # Roll: rotation around Y axis (tilt left/right)
                    roll = math.atan2(-ax, math.sqrt(ay*ay + az*az)) * 57.2957795
                    # Pitch: rotation around X axis (tilt forward/back)
                    pitch = math.atan2(ay, az) * 57.2957795

                    # Read gyroscope (6 bytes: x, y, z as signed 16-bit ints)
                    # Units: 1 dps = 16 LSB, convert to rad/s
                    gyro_data = self.bus.read_i2c_block_data(self.address, BNO055_GYRO_DATA_X_LSB_ADDR, 6)
                    gx = struct.unpack('<h', bytes(gyro_data[0:2]))[0] / 16.0 * 0.017453292519943295  # deg to rad
                    gy = struct.unpack('<h', bytes(gyro_data[2:4]))[0] / 16.0 * 0.017453292519943295
                    gz = struct.unpack('<h', bytes(gyro_data[4:6]))[0] / 16.0 * 0.017453292519943295
                    self.gyro = (gx, gy, gz)

                    # Calculate heading from gyro integration (yaw)
                    # Initialize timestamp on first read
                    if self.last_update_time is None:
                        self.last_update_time = time.time()
                        heading = 0.0
                    else:
                        # Integrate gyro Z (yaw rate) to get heading
                        current_time = time.time()
                        dt = current_time - self.last_update_time
                        self.last_update_time = current_time

                        # Integrate gyro z-axis (yaw) in degrees
                        heading_delta = gz * 57.2957795 * dt  # rad/s to deg/s * dt
                        self.integrated_roll += heading_delta

                        # Normalize to 0-360
                        heading = self.integrated_roll % 360.0

                    self.euler = (heading, roll, pitch)

                    # Quaternion not available in ACCGYRO mode
                    self.quaternion = (1.0, 0.0, 0.0, 0.0)

                    # Magnetometer not used in ACCGYRO mode (would add lag)
                    self.mag = (0.0, 0.0, 0.0)

                    # Read temperature
                    self.temperature = self.bus.read_byte_data(self.address, BNO055_TEMP_ADDR)

                    # Read calibration status
                    calib = self.bus.read_byte_data(self.address, BNO055_CALIB_STAT_ADDR)
                    sys_cal = (calib >> 6) & 0x03
                    gyro_cal = (calib >> 4) & 0x03
                    accel_cal = (calib >> 2) & 0x03
                    mag_cal = calib & 0x03
                    self.calibration = (sys_cal, gyro_cal, accel_cal, mag_cal)

                # Call callback if provided
                if self.callback:
                    try:
                        self.callback(self.get_orientation())
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        import traceback
                        traceback.print_exc()

                # Maintain update rate
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Sensor read error: {e}")
                time.sleep(0.1)  # Brief pause on error

    def get_orientation(self) -> dict:
        """
        Get current orientation data

        Returns:
            dict with euler angles, quaternion, gyro, accel, mag, temp, calibration
        """
        with self.lock:
            return {
                'euler': self.euler,  # (heading, roll, pitch) degrees
                'quaternion': self.quaternion,  # (w, x, y, z)
                'gyro': self.gyro,  # (x, y, z) rad/s
                'accel': self.accel,  # (x, y, z) m/s^2
                'mag': self.mag,  # (x, y, z) uT
                'temperature': self.temperature,
                'calibration': self.calibration  # (sys, gyro, accel, mag) 0-3
            }

    def get_roll_angle(self) -> float:
        """Get current roll angle in degrees"""
        with self.lock:
            return self.euler[1] if self.euler[1] is not None else 0.0

    def get_pitch_angle(self) -> float:
        """Get current pitch angle in degrees"""
        with self.lock:
            return self.euler[2] if self.euler[2] is not None else 0.0

    def get_heading_angle(self) -> float:
        """Get current heading angle in degrees"""
        with self.lock:
            return self.euler[0] if self.euler[0] is not None else 0.0

    def is_calibrated(self) -> bool:
        """Check if sensor is fully calibrated (all values >= 3)"""
        with self.lock:
            return all(c >= 3 for c in self.calibration)
