# GPS Setup Guide

## Hardware
- **GPS Module**: Ardusimple GPS
- **Antenna**: Ublox antenna
- **Connection**: USB (FTDI Bridge)
- **Device**: `/dev/ttyUSB0`
- **Baud Rate**: 115200

## Installation

### 1. Add User to dialout Group
```bash
sudo usermod -a -G dialout $USER
```

Then **log out and log back in** for the group changes to take effect.

### 2. Install Dependencies
```bash
source venv/bin/activate
pip install pyserial pynmea2
```

## Testing GPS Connection

### Test Raw NMEA Data
```bash
sudo python3 test_gps_raw.py
```

This will display raw NMEA sentences from the GPS for 10 seconds.

### Test GPS Service
```bash
newgrp dialout  # Activate dialout group in current session
source venv/bin/activate
python3 services/gps/gps_service.py
```

This will run for 30 seconds and display GPS fix information when available.

## Configuration

GPS settings can be configured in your `.env` or config file:

```bash
# GPS Configuration
GPS_PORT=/dev/ttyUSB0
GPS_BAUDRATE=115200
```

## Minimap Features

The minimap is a circular widget in the bottom-left corner of the HUD that displays:

- **Current Position**: Blue dot at the center
- **Heading Indicator**: Yellow arrow showing direction
- **North Compass**: Red triangle that always points north
- **GPS Status**: Green "X SATS" when active, red "NO GPS" when searching
- **Speed**: Displays current speed in km/h when moving
- **Map Tiles**: OpenStreetMap tiles showing surrounding area
- **Zoom Controls**: +/- buttons on the right side (zoom levels 10-19)

### Minimap Controls
- Map automatically rotates based on IMU heading
- Zoom in/out using the +/- buttons
- Default zoom level: 17 (street-level detail)

## File Structure

```
services/gps/
├── gps_service.py          # Core GPS reader service
└── __init__.py             # Package init

apps/visor-ui/
├── gps_client.py           # GPS client with Qt signals
├── minimap_controller.py   # Minimap rendering and map tiles
└── qml/
    └── Minimap.qml         # Minimap UI component

test_gps_raw.py             # Raw NMEA data testing tool
```

## Troubleshooting

### No GPS Fix
- Ensure GPS antenna has clear view of the sky
- GPS may take 1-2 minutes for cold start (first fix)
- Check satellite count - need at least 4 for 3D fix

### Permission Denied
```bash
# Check if user is in dialout group
groups

# If not, add user:
sudo usermod -a -G dialout $USER

# Then log out and log back in
```

### No Data from GPS
```bash
# Check device connection
ls -l /dev/ttyUSB*

# Test with different baud rates (try 9600 or 38400)
python3 services/gps/gps_service.py
```

### Map Tiles Not Loading
- Check internet connection (tiles downloaded from OpenStreetMap)
- Map tiles are cached in `.map_cache/` directory
- First load may be slow while downloading tiles

## GPS Data Fields

- **Latitude/Longitude**: Position in decimal degrees
- **Altitude**: Height above sea level in meters
- **Speed**: Ground speed in km/h
- **Heading**: Course over ground (0-360°)
- **Fix Quality**: 0=no fix, 1=GPS, 2=DGPS, etc.
- **Satellites**: Number of satellites in view
- **HDOP**: Horizontal dilution of precision (lower is better)

## Integration with Voice Assistant

The GPS data is available to the voice assistant for location-based queries:
- "Where am I?"
- "What's my current speed?"
- "How many satellites do I have?"

The assistant has access to GPS status through the system monitor.
