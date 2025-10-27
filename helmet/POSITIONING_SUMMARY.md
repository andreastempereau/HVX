# Helmet GPS & Indoor Positioning - Complete Summary

## ✅ What's Been Implemented

### 1. **GPS Tracking** (Outdoor)
- Ardusimple GPS module connected via USB (`/dev/ttyUSB0`)
- NMEA sentence parsing (GGA, RMC, VTG, GSA)
- Real-time position, altitude, speed, and heading
- Typical accuracy: ±5 meters

### 2. **Wi-Fi Positioning** (Indoor Fallback)
- Uses Google Geolocation API
- Scans nearby Wi-Fi networks (MAC addresses + signal strength)
- Provides location when GPS signal is unavailable
- Typical accuracy: ±20-50 meters indoors
- Automatic fallback after 10 seconds without GPS

### 3. **IP Geolocation** (Last Resort)
- Free fallback when Wi-Fi positioning unavailable
- City-level accuracy (~5km)
- No configuration needed

### 4. **Video Game-Style Minimap**
- Circular widget in bottom-left corner
- Shows your position with blue dot and yellow direction arrow
- North compass indicator (red triangle)
- Map tiles from OpenStreetMap
- Rotates with IMU heading
- Zoom controls (levels 10-19)

## 🎨 Visual Indicators

### Minimap Border Colors:
- **Green** = GPS active (satellite positioning)
- **Yellow/Amber** = Wi-Fi positioning active
- **Orange** = IP positioning active
- **Red** = No positioning available

### Status Display:
- **GPS**: "X SATS" (satellite count)
- **Wi-Fi**: "Wi-Fi ±XXm" (accuracy in meters)
- **IP**: "IP (~5km)" (city-level)
- **None**: "NO GPS"

## 📁 Files Created/Modified

### New Files:
```
services/gps/
├── gps_service.py              # GPS NMEA reader
├── wifi_positioning.py         # Wi-Fi & IP positioning
└── __init__.py

apps/visor-ui/
├── gps_client.py               # Qt GPS client with fallback
├── minimap_controller.py       # Minimap rendering & tiles
└── qml/Minimap.qml             # Minimap UI component

test_gps_raw.py                 # Raw NMEA testing tool

# Documentation
GPS_SETUP.md                    # GPS setup guide
INDOOR_POSITIONING_SETUP.md     # Google API setup guide
POSITIONING_SUMMARY.md          # This file
```

### Modified Files:
```
apps/visor-ui/main.py           # Integrated GPS & minimap
apps/visor-ui/qml/main.qml      # Added minimap widget
requirements-jetson.txt         # Added GPS dependencies
```

## 🚀 Quick Start

### 1. Get Google API Key (for indoor positioning)

1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable "Geolocation API"
4. Create an API key
5. Add to `.env`:
   ```bash
   GOOGLE_GEOLOCATION_API_KEY=AIzaSyD...your-key-here...
   ```

### 2. Set Permissions

```bash
# Add user to dialout group for GPS access
sudo usermod -a -G dialout $USER

# Log out and log back in for changes to take effect
```

### 3. Run the Application

```bash
cd /home/hvx/HVX/helmet
./start_ui.sh
```

## 🎯 How It Works

### Automatic Positioning Selection:

```
┌─────────────────────────────────────────────┐
│                                             │
│  GPS Signal Available?                      │
│         │                                   │
│         ├─ YES ──> Use GPS                  │
│         │          (Green border)           │
│         │                                   │
│         └─ NO ──> Wait 10 seconds           │
│                   │                         │
│                   ├─ Try Wi-Fi Positioning  │
│                   │  (Google API)           │
│                   │  (Yellow border)        │
│                   │                         │
│                   └─ Try IP Geolocation     │
│                      (Orange border)        │
│                                             │
└─────────────────────────────────────────────┘
```

### Positioning Methods:

| Method | Accuracy | Environment | Requirements |
|--------|----------|-------------|--------------|
| **GPS** | ±5m | Outdoors, clear sky | GPS antenna |
| **Wi-Fi** | ±20-50m | Indoors/Outdoors | Google API key + Internet |
| **IP** | ~5km | Anywhere | Internet only |

## 📊 Minimap Features

1. **Real-time Position**
   - Blue dot at center = your location
   - Yellow arrow = your heading direction

2. **North Compass**
   - Red triangle always points north
   - Rotates opposite to map for consistency

3. **Map Tiles**
   - OpenStreetMap tiles
   - Cached locally in `.map_cache/`
   - Auto-downloads on first use

4. **Zoom Controls**
   - `+` button = Zoom in
   - `-` button = Zoom out
   - Range: 10 (city) to 19 (building)
   - Default: 17 (street-level)

5. **Speed Display**
   - Shows current speed when moving
   - Only available with GPS

## 🧪 Testing

### Test GPS Only:
```bash
source venv/bin/activate
python3 services/gps/gps_service.py
```

### Test Wi-Fi Positioning:
```bash
source venv/bin/activate
export GOOGLE_GEOLOCATION_API_KEY=your-key-here
python3 services/gps/wifi_positioning.py
```

### Test Raw NMEA Data:
```bash
sudo python3 test_gps_raw.py
```

## ⚙️ Configuration

Add to your `.env` file:

```bash
# GPS Configuration
GPS_PORT=/dev/ttyUSB0
GPS_BAUDRATE=115200

# Google Geolocation API (for indoor positioning)
GOOGLE_GEOLOCATION_API_KEY=AIzaSyD...your-key-here...
```

## 💰 Cost

### Google Geolocation API:
- **Free Tier**: 40,000 requests/month
- Updates every 2 seconds indoors = ~1,800 requests/hour
- **~22 hours/month of indoor use is FREE**
- After free tier: $5 per 1,000 requests

### Recommendation:
Set billing alerts in Google Cloud Console to prevent unexpected charges.

## 🔧 Troubleshooting

### No GPS Fix
- Take GPS outside for clear sky view
- Wait 1-2 minutes for cold start
- Check antenna connection

### Permission Denied (/dev/ttyUSB0)
```bash
sudo usermod -a -G dialout $USER
# Log out and log back in
```

### Wi-Fi Positioning Not Working
- Check `GOOGLE_GEOLOCATION_API_KEY` in `.env`
- Verify API is enabled in Google Cloud Console
- Check internet connection
- Look for API errors in logs

### Minimap Not Showing
- Check QML loaded successfully (no errors in log)
- Verify minimap image provider is registered
- Check for OpenGL/graphics driver issues

## 🔐 Privacy Considerations

### Data Sent to Google:
- Wi-Fi MAC addresses (not SSIDs or passwords)
- Signal strengths only
- No personal information

### Data NOT Sent:
- Network passwords
- SSIDs (network names)
- Any user data
- Photos or recordings

### Recommendation:
- Consider disabling Wi-Fi positioning in sensitive locations
- Use GPS-only mode when privacy is critical
- IP geolocation works without Wi-Fi scanning

## 📱 Just Like Your iPhone!

Your helmet now uses the same multi-source positioning as smartphones:

1. **Primary**: GPS satellites (outdoor)
2. **Fallback**: Wi-Fi networks (indoor)
3. **Last Resort**: IP address (anywhere)

The system automatically switches between methods for seamless indoor/outdoor transitions!

## 🎮 Gaming-Style HUD

The minimap provides a familiar gaming experience:
- Always centered on your position
- Rotates with your heading (IMU)
- Real-time map updates
- Visual indicators for positioning method
- Zoom in/out for tactical or strategic view

Perfect for navigation, location tracking, and situational awareness!
