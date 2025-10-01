# Helmet OS - Getting Started Guide

This guide will help you get the Helmet OS software stack running on your development machine and later deploy it to your Jetson Orin Nano.

## Quick Start (Development)

### Prerequisites
- Docker and Docker Compose
- Python 3.9+
- Git

### 1. Clone and Build
```bash
cd helmet/
./deploy/scripts/build.sh
```

### 2. Start Development Environment
```bash
./deploy/scripts/start.sh
```

This starts all services with mock video input and CPU-based AI inference.

### 3. Test the System
- **Video Service**: `curl localhost:50051` (should respond with gRPC)
- **Perception**: Mock detections will appear in logs
- **Voice**: Say "Computer, toggle night mode" (if mic available)
- **UI**: Should display dual-eye view with overlays

### 4. Stop the System
```bash
./deploy/scripts/stop.sh
```

## Production Deployment (Jetson Orin Nano)

### Prerequisites
- Jetson Orin Nano with JetPack 6.x
- CSI camera module or USB camera
- Bone conduction headset with microphone
- Dual OLED displays (configured as extended desktop)

### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install -y \
    python3-venv python3-dev \
    gstreamer1.0-tools gstreamer1.0-plugins-* \
    libgstreamer1.0-dev \
    qt6-base-dev qt6-declarative-dev \
    pulseaudio alsa-utils \
    nvidia-jetpack
```

### 2. Install Helmet OS
```bash
sudo ./deploy/scripts/install.sh
```

### 3. Configure for Your Hardware
Edit the production configuration:
```bash
sudo nano /opt/helmet/configs/profiles/field.json
```

Key settings to adjust:
- `video.camera_id` - Your camera device
- `voice.mic_device` - Your microphone device
- `ui.lens_correction` - Calibrate for your displays
- `perception.device` - Set to "cuda" for GPU inference

### 4. Start the System
```bash
sudo helmet-start
```

### 5. Check Status
```bash
helmet-status
```

## Key Features

### Video Pipeline
- **Development**: Uses MP4 file or webcam mock
- **Production**: CSI camera with hardware acceleration
- **Output**: Dual-eye compositor with lens distortion correction

### AI Perception
- **Model**: YOLOv8 object detection
- **Performance**: 20-30 FPS on Jetson Orin
- **Objects**: People, vehicles, traffic signs, etc.
- **Overlays**: Real-time bounding boxes and labels

### Voice Assistant
- **Wake Word**: "Computer" (configurable)
- **ASR**: faster-whisper (offline)
- **Commands**: 15+ built-in intents
- **TTS**: Piper voices (offline)

### System Control
- **Modes**: Normal, Night Vision, Navigation, Emergency
- **Recording**: Voice-activated video capture
- **Telemetry**: CPU, memory, temperature monitoring
- **Logging**: Structured JSON logs with rotation

## Voice Commands

| Command | Action |
|---------|--------|
| "Computer, toggle night mode" | Switch to night vision |
| "Computer, start recording" | Begin video recording |
| "Computer, take screenshot" | Capture current frame |
| "Computer, what do you see" | Describe current scene |
| "Computer, mark target" | Mark object of interest |
| "Computer, emergency" | Activate emergency mode |
| "Computer, system status" | Get system health report |

## Configuration Profiles

### Development (`dev.json`)
- Mock video input
- CPU inference
- Debug logging
- Windowed UI

### Production (`field.json`)
- Real camera input
- GPU inference
- Optimized logging
- Fullscreen UI

### Demo (`demo.json`)
- Lower resolution
- High detection sensitivity
- Show all overlays

## Troubleshooting

### Video Service Issues
```bash
# Check camera access
v4l2-ctl --list-devices

# Test GStreamer pipeline
gst-launch-1.0 nvarguscamerasrc ! nvvideoconvert ! autovideosink
```

### AI Inference Issues
```bash
# Check GPU utilization
nvidia-smi

# Test CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Audio Issues
```bash
# List audio devices
arecord -l
pactl list sources

# Test microphone
arecord -D hw:1,0 -f cd test.wav
```

### Display Issues
```bash
# Check displays
xrandr

# Test Qt
export DISPLAY=:0
python3 -c "from PySide6.QtWidgets import QApplication; app = QApplication([])"
```

## Performance Optimization

### Jetson Power Mode
```bash
# Maximum performance
sudo nvpmodel -m 0
sudo jetson_clocks
```

### Model Optimization
```bash
# Convert ONNX to TensorRT for faster inference
trtexec --onnx=models/yolov8n.onnx --saveEngine=models/yolov8n.engine --fp16
```

### Memory Management
- Services are limited by systemd resource controls
- Adjust limits in `/etc/systemd/system/helmet-*.service`
- Monitor with `helmet-status`

## Development Workflow

### Adding New Voice Commands
1. Edit `services/voice/intents.json`
2. Add pattern matching rules
3. Implement action in `orchestrator_service.py`
4. Test with voice or gRPC client

### Modifying UI
1. Edit QML files in `apps/visor-ui/qml/`
2. Restart UI service: `sudo systemctl restart helmet-ui`
3. Check logs: `journalctl -fu helmet-ui`

### Custom AI Models
1. Place model in `models/` directory
2. Update `perception.model_path` in config
3. Modify `perception_service.py` if needed
4. Restart perception service

## Next Steps

Once you have the basic system running:

1. **Calibrate displays** - Adjust lens correction parameters
2. **Train custom models** - For your specific use case
3. **Add sensors** - GPS, IMU, environmental sensors
4. **Integrate mapping** - Add SLAM capabilities
5. **Custom applications** - Build domain-specific features

## Support

- Check logs: `journalctl -fu helmet-*`
- Debug mode: Set `HELMET_PROFILE=dev`
- Development tools: `docker-compose --profile dev up`
- File issues on GitHub

Happy building! 🚁