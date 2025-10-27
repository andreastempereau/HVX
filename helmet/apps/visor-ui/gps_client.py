#!/usr/bin/env python3
"""GPS client wrapper for visor UI"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QObject, Signal, QTimer

# Add services to path
sys.path.append(str(Path(__file__).parent.parent.parent / "services"))
from gps.gps_service import GPSReader, GPSData
from gps.wifi_positioning import WiFiPositioningService

logger = logging.getLogger(__name__)

class GPSClient(QObject):
    """GPS client with Qt signals for UI integration and Wi-Fi fallback"""

    # Signals for QML
    positionUpdated = Signal(float, float, float, float)  # lat, lon, altitude, heading
    statusUpdated = Signal('QVariantMap')  # GPS status info

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        super().__init__()
        self.gps_reader = GPSReader(port=port, baudrate=baudrate)
        self.running = False

        # Wi-Fi positioning fallback
        google_api_key = os.environ.get('GOOGLE_GEOLOCATION_API_KEY')
        self.wifi_positioning = WiFiPositioningService(api_key=google_api_key)
        self.use_wifi_fallback = bool(google_api_key)

        if self.use_wifi_fallback:
            logger.info("Wi-Fi positioning enabled (Google API)")
        else:
            logger.info("Wi-Fi positioning disabled (no API key)")

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update)

        # Last known position
        self.last_latitude: Optional[float] = None
        self.last_longitude: Optional[float] = None
        self.last_altitude: Optional[float] = None
        self.last_heading: Optional[float] = None

        # Positioning method tracking
        self.last_positioning_method = "none"  # "gps", "wifi", "ip", "none"
        self.gps_fix_lost_count = 0  # Count updates without GPS fix

    def start(self) -> bool:
        """Start GPS reader and updates"""
        try:
            if self.gps_reader.start():
                logger.info("GPS client started")
                self.running = True

                # Start update timer (2 Hz for GPS updates)
                self.update_timer.start(500)  # 500ms = 2 Hz
                return True
            else:
                logger.error("Failed to start GPS reader")
                return False

        except Exception as e:
            logger.error(f"GPS client start error: {e}")
            return False

    def stop(self):
        """Stop GPS reader and updates"""
        self.running = False
        self.update_timer.stop()
        self.gps_reader.stop()
        logger.info("GPS client stopped")

    def _update(self):
        """Update GPS data and emit signals, with Wi-Fi fallback"""
        try:
            data = self.gps_reader.get_data()

            # Check if GPS has valid fix
            if data.is_valid():
                # GPS is working!
                self.gps_fix_lost_count = 0
                positioning_method = "gps"

                # Check if position changed (to avoid unnecessary updates)
                position_changed = (
                    self.last_latitude != data.latitude or
                    self.last_longitude != data.longitude or
                    self.last_altitude != data.altitude or
                    self.last_heading != data.heading
                )

                if position_changed:
                    self.last_latitude = data.latitude
                    self.last_longitude = data.longitude
                    self.last_altitude = data.altitude if data.altitude else 0.0
                    self.last_heading = data.heading if data.heading else 0.0

                    # Emit position update
                    self.positionUpdated.emit(
                        data.latitude,
                        data.longitude,
                        self.last_altitude,
                        self.last_heading
                    )

                # Emit status update
                status = {
                    'valid': True,
                    'latitude': data.latitude,
                    'longitude': data.longitude,
                    'altitude': data.altitude,
                    'speed': data.speed,
                    'heading': data.heading,
                    'fix_quality': data.fix_quality,
                    'satellites': data.satellites,
                    'hdop': data.hdop,
                    'positioning_method': positioning_method,
                    'accuracy': data.hdop * 5 if data.hdop else 10  # Rough accuracy estimate
                }
                self.statusUpdated.emit(status)
                self.last_positioning_method = positioning_method

            else:
                # No GPS fix - try Wi-Fi positioning
                self.gps_fix_lost_count += 1

                # Wait 5 updates (10 seconds) before switching to Wi-Fi
                # This avoids unnecessary Wi-Fi lookups during brief GPS dropouts
                if self.gps_fix_lost_count >= 5 and self.use_wifi_fallback:
                    # Try Wi-Fi positioning (no IP fallback)
                    wifi_position = self.wifi_positioning.get_position_from_wifi()

                    if wifi_position:
                        lat, lon, accuracy = wifi_position
                        positioning_method = "wifi"

                        # Only update if position changed
                        position_changed = (
                            self.last_latitude != lat or
                            self.last_longitude != lon
                        )

                        if position_changed or self.last_positioning_method != positioning_method:
                            self.last_latitude = lat
                            self.last_longitude = lon
                            # Don't update altitude/heading from Wi-Fi

                            # Emit position update
                            self.positionUpdated.emit(
                                lat,
                                lon,
                                self.last_altitude or 0.0,
                                self.last_heading or 0.0
                            )

                            logger.info(f"Using {positioning_method} positioning: {lat:.6f}, {lon:.6f} (±{accuracy}m)")

                        # Emit status update
                        status = {
                            'valid': True,  # We have *a* position, even if not GPS
                            'latitude': lat,
                            'longitude': lon,
                            'altitude': None,
                            'speed': None,
                            'heading': None,
                            'fix_quality': 0,
                            'satellites': 0,
                            'hdop': None,
                            'positioning_method': positioning_method,
                            'accuracy': accuracy
                        }
                        self.statusUpdated.emit(status)
                        self.last_positioning_method = positioning_method
                        return

                # No position available (GPS or Wi-Fi)
                status = {
                    'valid': False,
                    'latitude': None,
                    'longitude': None,
                    'altitude': None,
                    'speed': None,
                    'heading': None,
                    'fix_quality': 0,
                    'satellites': data.satellites,
                    'hdop': None,
                    'positioning_method': 'none',
                    'accuracy': None
                }
                self.statusUpdated.emit(status)
                self.last_positioning_method = 'none'

        except Exception as e:
            logger.error(f"GPS update error: {e}")

    def get_position(self) -> Optional[tuple]:
        """Get current position as (lat, lon) tuple"""
        data = self.gps_reader.get_data()
        if data.is_valid():
            return (data.latitude, data.longitude)
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get GPS status information"""
        data = self.gps_reader.get_data()
        return data.to_dict()
