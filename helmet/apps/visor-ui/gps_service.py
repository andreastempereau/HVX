#!/usr/bin/env python3
"""GPS service for reading Ardusimple GPS data via serial port"""

import serial
import pynmea2
import logging
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class GPSData:
    """Container for GPS data"""

    def __init__(self):
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.altitude: Optional[float] = None
        self.speed: Optional[float] = None  # Speed in km/h
        self.heading: Optional[float] = None  # Course over ground
        self.fix_quality: int = 0  # 0 = no fix, 1 = GPS fix, 2 = DGPS fix, etc.
        self.satellites: int = 0
        self.hdop: Optional[float] = None  # Horizontal dilution of precision
        self.timestamp: Optional[datetime] = None
        self.last_update: Optional[datetime] = None

    def is_valid(self) -> bool:
        """Check if we have a valid GPS fix"""
        return self.latitude is not None and self.longitude is not None and self.fix_quality > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert GPS data to dictionary"""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'heading': self.heading,
            'fix_quality': self.fix_quality,
            'satellites': self.satellites,
            'hdop': self.hdop,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'valid': self.is_valid()
        }

class GPSReader:
    """GPS reader for Ardusimple GPS"""

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        """
        Initialize GPS reader

        Args:
            port: Serial port for GPS (default: /dev/ttyUSB0)
            baudrate: Baud rate (Ardusimple default is 115200, but could be 9600 or 38400)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.reader_thread: Optional[threading.Thread] = None
        self.data = GPSData()
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Connect to GPS device"""
        try:
            logger.info(f"Connecting to GPS on {self.port} at {self.baudrate} baud")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            # Wait a moment for connection to stabilize
            time.sleep(0.5)

            if self.serial_conn.is_open:
                logger.info("GPS connection established")
                return True
            else:
                logger.error("Failed to open GPS serial port")
                return False

        except serial.SerialException as e:
            logger.error(f"GPS connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from GPS device"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("GPS disconnected")

    def start(self) -> bool:
        """Start reading GPS data in background thread"""
        if self.running:
            logger.warning("GPS reader already running")
            return True

        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                return False

        self.running = True
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        logger.info("GPS reader started")
        return True

    def stop(self):
        """Stop reading GPS data"""
        self.running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=2.0)
        self.disconnect()
        logger.info("GPS reader stopped")

    def _read_loop(self):
        """Main reading loop (runs in background thread)"""
        logger.info("GPS reading loop started")
        consecutive_errors = 0
        max_errors = 10

        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    logger.warning("GPS connection lost, attempting to reconnect...")
                    if not self.connect():
                        time.sleep(2.0)
                        continue

                # Read a line from serial port
                line = self.serial_conn.readline()

                if not line:
                    continue

                # Decode bytes to string
                try:
                    line_str = line.decode('ascii', errors='ignore').strip()
                except UnicodeDecodeError:
                    continue

                # Skip empty lines
                if not line_str:
                    continue

                # Parse NMEA sentence
                self._parse_nmea(line_str)
                consecutive_errors = 0

            except serial.SerialException as e:
                consecutive_errors += 1
                logger.error(f"Serial error ({consecutive_errors}/{max_errors}): {e}")
                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, stopping GPS reader")
                    self.running = False
                    break
                time.sleep(1.0)

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"GPS read error ({consecutive_errors}/{max_errors}): {e}")
                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, stopping GPS reader")
                    self.running = False
                    break
                time.sleep(0.1)

        logger.info("GPS reading loop stopped")

    def _parse_nmea(self, sentence: str):
        """Parse NMEA sentence and update GPS data"""
        try:
            # Skip if not a valid NMEA sentence
            if not sentence.startswith('$'):
                return

            # Parse with pynmea2
            msg = pynmea2.parse(sentence)

            with self._lock:
                # GGA - Fix data
                if isinstance(msg, pynmea2.GGA):
                    if msg.latitude and msg.longitude:
                        self.data.latitude = msg.latitude
                        self.data.longitude = msg.longitude
                    if msg.altitude:
                        self.data.altitude = msg.altitude
                    self.data.fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
                    self.data.satellites = int(msg.num_sats) if msg.num_sats else 0
                    if msg.horizontal_dil:
                        self.data.hdop = float(msg.horizontal_dil)
                    self.data.last_update = datetime.now()

                    if self.data.is_valid():
                        logger.debug(f"GPS Fix: {self.data.latitude:.6f}, {self.data.longitude:.6f}, "
                                   f"Alt: {self.data.altitude}m, Sats: {self.data.satellites}")

                # RMC - Recommended minimum data
                elif isinstance(msg, pynmea2.RMC):
                    if msg.latitude and msg.longitude:
                        self.data.latitude = msg.latitude
                        self.data.longitude = msg.longitude
                    if msg.spd_over_grnd:
                        # Convert knots to km/h
                        self.data.speed = float(msg.spd_over_grnd) * 1.852
                    if msg.true_course:
                        self.data.heading = float(msg.true_course)
                    if msg.timestamp:
                        self.data.timestamp = msg.timestamp
                    self.data.last_update = datetime.now()

                # VTG - Course and speed
                elif isinstance(msg, pynmea2.VTG):
                    if msg.spd_over_grnd_kmph:
                        self.data.speed = float(msg.spd_over_grnd_kmph)
                    if msg.true_track:
                        self.data.heading = float(msg.true_track)
                    self.data.last_update = datetime.now()

                # GSA - Satellite status
                elif isinstance(msg, pynmea2.GSA):
                    if msg.hdop:
                        self.data.hdop = float(msg.hdop)
                    self.data.last_update = datetime.now()

        except pynmea2.ParseError:
            # Ignore parse errors for unsupported sentences
            pass
        except Exception as e:
            logger.debug(f"NMEA parse error: {e} for sentence: {sentence}")

    def get_data(self) -> GPSData:
        """Get current GPS data (thread-safe)"""
        with self._lock:
            return self.data

    def get_position(self) -> Optional[tuple]:
        """Get current position as (lat, lon) tuple"""
        with self._lock:
            if self.data.is_valid():
                return (self.data.latitude, self.data.longitude)
            return None

def main():
    """Test GPS reader"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting GPS reader test...")

    # Try different common baud rates
    baud_rates = [115200, 38400, 9600]
    gps = None

    for baudrate in baud_rates:
        logger.info(f"Trying baud rate: {baudrate}")
        gps = GPSReader(port='/dev/ttyUSB0', baudrate=baudrate)
        if gps.start():
            logger.info(f"GPS reader started successfully at {baudrate} baud")
            break
        else:
            logger.warning(f"Failed to start at {baudrate} baud")
            gps = None

    if not gps:
        logger.error("Failed to connect to GPS at any baud rate")
        return

    try:
        logger.info("Reading GPS data for 30 seconds...")
        logger.info("Waiting for GPS fix (this may take a minute if outdoors)...")

        for i in range(30):
            time.sleep(1)
            data = gps.get_data()

            if data.is_valid():
                logger.info(f"\n{'='*60}")
                logger.info(f"GPS DATA UPDATE:")
                logger.info(f"  Position: {data.latitude:.6f}, {data.longitude:.6f}")
                logger.info(f"  Altitude: {data.altitude:.1f}m" if data.altitude else "  Altitude: N/A")
                logger.info(f"  Speed: {data.speed:.1f} km/h" if data.speed else "  Speed: N/A")
                logger.info(f"  Heading: {data.heading:.1f}°" if data.heading else "  Heading: N/A")
                logger.info(f"  Fix Quality: {data.fix_quality}")
                logger.info(f"  Satellites: {data.satellites}")
                logger.info(f"  HDOP: {data.hdop:.2f}" if data.hdop else "  HDOP: N/A")
                logger.info(f"{'='*60}\n")
            else:
                logger.info(f"[{i+1}/30] No GPS fix yet... (Sats: {data.satellites}, Fix: {data.fix_quality})")

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        logger.info("Stopping GPS reader...")
        gps.stop()
        logger.info("GPS test complete")

if __name__ == "__main__":
    main()
