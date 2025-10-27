# Indoor Positioning Setup (Wi-Fi Based)

Your helmet can now determine location indoors using Wi-Fi positioning, just like your iPhone!

## How It Works

When GPS signal is weak or unavailable (indoors), the system:
1. Scans nearby Wi-Fi access points (MAC addresses and signal strength)
2. Sends this data to Google Geolocation API
3. Google returns your location with ~20-50m accuracy
4. Falls back to IP geolocation if Wi-Fi positioning fails

## Setup Google Geolocation API

### 1. Get a Google Cloud Account
- Go to https://console.cloud.google.com/
- Sign in with your Google account (or create one)
- You get **$300 free credit** for new accounts

### 2. Create a Project
- Click "Select a project" at the top
- Click "NEW PROJECT"
- Name it something like "Helmet-GPS"
- Click "CREATE"

### 3. Enable Geolocation API
- Go to https://console.cloud.google.com/apis/library
- Search for "Geolocation API"
- Click on it
- Click "ENABLE"

### 4. Create API Key
- Go to https://console.cloud.google.com/apis/credentials
- Click "CREATE CREDENTIALS"
- Select "API key"
- Copy the API key (looks like: `AIzaSyD...`)

### 5. Restrict API Key (Recommended)
- Click on your new API key to edit it
- Under "API restrictions":
  - Select "Restrict key"
  - Check "Geolocation API"
- Click "SAVE"

### 6. Add API Key to Your Helmet

Edit your `.env` file:
```bash
nano /home/hvx/HVX/helmet/.env
```

Add this line:
```bash
GOOGLE_GEOLOCATION_API_KEY=AIzaSyD...your-key-here...
```

Save and exit (Ctrl+X, Y, Enter)

## Pricing

**Free Tier:**
- 40,000 requests per month (free forever)
- That's ~1,333 requests per day
- At 1 request per minute = 22 hours/day of usage

**After Free Tier:**
- $5 per 1,000 requests
- But you can set spending limits to prevent charges

## Testing

Test Wi-Fi positioning:
```bash
source venv/bin/activate
python3 services/gps/wifi_positioning.py
```

This will:
1. Scan Wi-Fi networks
2. Get your location from Wi-Fi
3. Show a Google Maps link
4. Fall back to IP geolocation

## Integration with GPS

The system automatically:
- Uses GPS when outdoors (satellite fix available)
- Switches to Wi-Fi positioning when indoors (no GPS fix)
- Shows accuracy on minimap (GPS: ±5m, Wi-Fi: ±20-50m, IP: ±5000m)

## Minimap Indicators

- **Green border** + "X SATS" = GPS active
- **Yellow border** + "Wi-Fi" = Wi-Fi positioning active
- **Red border** + "NO GPS" = No positioning available

## Troubleshooting

### No Wi-Fi Networks Found
```bash
# Check NetworkManager is running
systemctl status NetworkManager

# Manual scan
nmcli dev wifi rescan
nmcli dev wifi list
```

### API Key Not Working
- Check the key is correct in `.env`
- Verify Geolocation API is enabled in Google Cloud Console
- Check for API restrictions (should allow Geolocation API)
- Restart the application after adding the key

### "API key not valid" Error
- Make sure you copied the entire key
- Check there are no extra spaces in `.env` file
- API key might take a few minutes to activate

## Privacy Note

- Wi-Fi MAC addresses are sent to Google for positioning
- No personal data or network passwords are transmitted
- Only MAC addresses and signal strengths are used
- Consider this when in sensitive environments

## Alternative: IP Geolocation Only

If you don't want to use Google API:
- Don't set `GOOGLE_GEOLOCATION_API_KEY`
- System will use free IP geolocation
- Accuracy: city-level (~5km)
- No API key or setup needed
