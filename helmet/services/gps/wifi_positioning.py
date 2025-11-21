#!/usr/bin/env python3
"""Wi-Fi positioning service for indoor location when GPS is unavailable"""

import logging
import subprocess
import re
import requests
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class WiFiAccessPoint:
    """Wi-Fi access point information"""
    mac_address: str
    signal_strength: int  # RSSI in dBm
    ssid: Optional[str] = None
    channel: Optional[int] = None

class WiFiPositioningService:
    """Wi-Fi-based positioning service using Google Geolocation API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Wi-Fi positioning service

        Args:
            api_key: Google Geolocation API key (required for production use)
                    Get one at: https://console.cloud.google.com/apis/credentials
        """
        # Google Geolocation API
        self.api_key = api_key
        if api_key:
            self.api_url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={api_key}"
        else:
            # Will fall back to IP geolocation if no API key
            self.api_url = None
            logger.warning("No Google API key provided - Wi-Fi positioning disabled")

        # Fallback to IP geolocation
        self.ip_geolocation_url = "https://ipapi.co/json/"

        # Cache for reducing API calls
        self._last_position: Optional[Tuple[float, float, float]] = None
        self._last_wifi_scan: List[WiFiAccessPoint] = []

    def scan_wifi_networks(self) -> List[WiFiAccessPoint]:
        """Scan for nearby Wi-Fi networks and return their information"""
        try:
            # Use nmcli (NetworkManager) to scan Wi-Fi networks
            # Skip rescan - just use cached results for speed
            # subprocess.run(['nmcli', 'dev', 'wifi', 'rescan'], capture_output=True, timeout=2)

            # Now list the networks
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'BSSID,SIGNAL,SSID,CHAN', 'dev', 'wifi', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.warning("Failed to scan Wi-Fi networks with nmcli")
                return []

            access_points = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    # Split by colon, but be careful with MAC addresses which contain colons
                    parts = line.split(':')

                    # MAC address is first 6 parts (AA:BB:CC:DD:EE:FF)
                    if len(parts) < 9:  # Need at least MAC (6) + signal + ssid + channel
                        continue

                    # Join MAC address parts and remove any escape characters
                    mac = ':'.join(parts[0:6]).replace('\\', '')
                    signal_str = parts[6].strip()
                    ssid = parts[7].strip() if len(parts) > 7 else ""
                    channel_str = parts[8].strip() if len(parts) > 8 else "0"

                    # Parse signal strength
                    if not signal_str.isdigit():
                        continue
                    signal = int(signal_str)

                    # Convert signal from 0-100% to approximate dBm (-100 to -30)
                    rssi = -100 + (signal * 0.7)

                    # Parse channel
                    channel = int(channel_str) if channel_str.isdigit() else 0

                    ap = WiFiAccessPoint(
                        mac_address=mac,
                        signal_strength=int(rssi),
                        ssid=ssid if ssid else None,
                        channel=channel if channel > 0 else None
                    )
                    access_points.append(ap)

                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse line: {line} - {e}")
                    continue

            logger.info(f"Found {len(access_points)} Wi-Fi access points")
            self._last_wifi_scan = access_points
            return access_points

        except subprocess.TimeoutExpired:
            logger.warning("Wi-Fi scan timed out")
            return []
        except Exception as e:
            logger.error(f"Wi-Fi scan error: {e}")
            return []

    def get_position_from_wifi(self) -> Optional[Tuple[float, float, float]]:
        """
        Get position using Wi-Fi positioning via Google Geolocation API

        Returns:
            Tuple of (latitude, longitude, accuracy_meters) or None
        """
        try:
            # Check if API key is available
            if not self.api_url:
                logger.warning("No Google API key - Wi-Fi positioning unavailable")
                return None

            # Scan for Wi-Fi networks
            access_points = self.scan_wifi_networks()

            if not access_points:
                logger.warning("No Wi-Fi networks found for positioning")
                return None

            # Build request for Google Geolocation API
            wifi_data = []
            for ap in sorted(access_points, key=lambda x: x.signal_strength, reverse=True)[:10]:
                wifi_data.append({
                    "macAddress": ap.mac_address,
                    "signalStrength": ap.signal_strength,
                    "channel": ap.channel
                })

            if not wifi_data:
                return None

            # Request payload for Google API
            payload = {
                "considerIp": False,  # Don't use IP fallback
                "wifiAccessPoints": wifi_data
            }

            # Make request to Google Geolocation API
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                data = response.json()
                lat = data.get('location', {}).get('lat')
                lon = data.get('location', {}).get('lng')
                accuracy = data.get('accuracy', 1000)

                if lat and lon:
                    position = (lat, lon, accuracy)
                    self._last_position = position
                    logger.info(f"Wi-Fi position: {lat:.6f}, {lon:.6f} (accuracy: ±{accuracy}m)")
                    return position
            elif response.status_code == 404:
                logger.error("Google Geolocation API returned 404 - API may not be enabled")
                logger.error("Enable it at: https://console.cloud.google.com/apis/library/geolocation.googleapis.com")
                return None
            elif response.status_code == 403:
                logger.error("Google Geolocation API returned 403 - Check API key permissions")
                return None
            elif response.status_code == 429:
                logger.warning("Google Geolocation API rate limit exceeded - using cached position")
                return self._last_position
            else:
                logger.warning(f"Wi-Fi positioning API returned status {response.status_code}: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Wi-Fi positioning API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Wi-Fi positioning error: {e}")
            return None

    def get_position_from_ip(self) -> Optional[Tuple[float, float, float]]:
        """
        Get approximate position using IP geolocation (fallback method)

        Returns:
            Tuple of (latitude, longitude, accuracy_meters) or None
        """
        try:
            response = requests.get(self.ip_geolocation_url, timeout=3)

            if response.status_code == 200:
                data = response.json()
                lat = data.get('latitude')
                lon = data.get('longitude')

                if lat and lon:
                    # IP geolocation is very inaccurate (city-level)
                    accuracy = 5000  # ~5km accuracy
                    position = (lat, lon, accuracy)
                    logger.info(f"IP position: {lat:.6f}, {lon:.6f} (city-level)")
                    return position

            return None

        except Exception as e:
            logger.error(f"IP geolocation error: {e}")
            return None

    def get_position(self, prefer_wifi: bool = True) -> Optional[Tuple[float, float, float]]:
        """
        Get position using best available method

        Args:
            prefer_wifi: Try Wi-Fi positioning first, then IP fallback

        Returns:
            Tuple of (latitude, longitude, accuracy_meters) or None
        """
        if prefer_wifi:
            # Try Wi-Fi positioning first
            position = self.get_position_from_wifi()
            if position:
                return position

            # Fall back to IP geolocation
            logger.info("Wi-Fi positioning unavailable, trying IP geolocation")
            return self.get_position_from_ip()
        else:
            # Just use IP geolocation
            return self.get_position_from_ip()

    def get_last_position(self) -> Optional[Tuple[float, float, float]]:
        """Get last known position from cache"""
        return self._last_position


def main():
    """Test Wi-Fi positioning"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing Wi-Fi Positioning Service")
    print("="*60)

    # Load API key from environment
    import os
    api_key = os.environ.get('GOOGLE_GEOLOCATION_API_KEY')

    if api_key:
        print(f"✓ Google API key loaded: {api_key[:20]}...")
    else:
        print("⚠ No Google API key found in environment")
        print("  Set GOOGLE_GEOLOCATION_API_KEY in .env file")

    service = WiFiPositioningService(api_key=api_key)

    # Test Wi-Fi scan
    print("\n1. Scanning Wi-Fi networks...")
    aps = service.scan_wifi_networks()
    print(f"Found {len(aps)} access points:")
    for ap in aps[:5]:  # Show first 5
        print(f"  - {ap.mac_address}: {ap.signal_strength} dBm ({ap.ssid})")

    # Test Wi-Fi positioning
    print("\n2. Getting position from Wi-Fi...")
    position = service.get_position_from_wifi()
    if position:
        lat, lon, accuracy = position
        print(f"Wi-Fi Position: {lat:.6f}, {lon:.6f}")
        print(f"Accuracy: ±{accuracy:.0f} meters")
        print(f"Google Maps: https://www.google.com/maps?q={lat},{lon}")
    else:
        print("Wi-Fi positioning failed")

    # Test IP geolocation
    print("\n3. Getting position from IP address...")
    ip_position = service.get_position_from_ip()
    if ip_position:
        lat, lon, accuracy = ip_position
        print(f"IP Position: {lat:.6f}, {lon:.6f}")
        print(f"Accuracy: ±{accuracy:.0f} meters (city-level)")
    else:
        print("IP geolocation failed")

    print("\n" + "="*60)
    print("Test complete!")


if __name__ == "__main__":
    main()
