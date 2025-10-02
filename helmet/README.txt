================================================================================
                    HELMET OS - AR/VR VISION SYSTEM
                              Version 1.1.1
================================================================================

OVERVIEW
========

Helmet OS is a complete software stack for an AR helmet system featuring
real-time video capture, AI-powered object detection, voice control, and
dual-eye display with augmented reality overlays.

This modular, microservices-based AR/VR platform is designed for the NVIDIA
Jetson Orin Nano and provides a complete solution for building augmented
reality applications with computer vision, voice interaction, and real-time
video processing capabilities.


KEY FEATURES
============

- Dual Camera Support
  Front CSI camera + rear USB camera with GStreamer acceleration

- AI Object Detection
  YOLOv8-based real-time object detection with GPU acceleration

- Voice Control
  Offline ASR (faster-whisper) with 15+ voice commands

- Dual-Eye Display
  Stereoscopic compositor with lens distortion correction

- Real-time Telemetry
  System monitoring, FPS tracking, temperature/battery status

- Video Recording
  Voice-activated recording with timestamp annotations

- AR Overlays
  Dynamic HUD with bounding boxes, status displays, and crosshairs


ARCHITECTURE
============

The system follows a microservices architecture with gRPC for inter-service
communication:

    +-------------------------------------------------------------+
    |                    Visor UI (Qt/QML)                        |
    |  Dual-Eye Compositor • AR Overlays • HUD • User Interface   |
    +-------------------------------------------------------------+
                              |
                    +---------+---------+
                    |   Orchestrator    |
                    | System Coordinator|
                    |  State Management |
                    +---------+---------+
                              |
        +---------------------+---------------------+
        |                     |                     |
    +---+--------+  +---------+-------+  +----------+------+
    | Video      |  | Perception      |  | Voice Service   |
    | Service    |  | YOLOv8/ONNX     |  | Whisper + TTS   |
    | GStreamer  |  | Object Detection|  | Intent Recog.   |
    +------------+  +-----------------+  +-----------------+


CORE SERVICES
=============

1. Video Service (services/video/)
   - Hardware-accelerated video capture via GStreamer
   - Support for CSI cameras (IMX219) and USB webcams
   - Real-time frame streaming over gRPC
   - Automatic format detection (YUYV/MJPEG)

2. Perception Service (services/perception/)
   - YOLOv8n object detection
   - TensorRT/ONNX inference support
   - GPU-accelerated processing on Jetson
   - Configurable confidence thresholds and NMS
   - Region of Interest (ROI) detection

3. Voice Service (services/voice/)
   - Offline speech recognition (faster-whisper)
   - Intent classification with regex patterns
   - Text-to-speech synthesis (Piper)
   - Voice activity detection (WebRTC VAD)
   - 15+ built-in voice commands

4. Orchestrator Service (services/orchestrator/)
   - System state management
   - Command routing and execution
   - Telemetry collection (CPU, memory, temperature)
   - SQLite-based state persistence
   - Service coordination

5. Visor UI (apps/visor-ui/)
   - Qt6/QML dual-eye compositor
   - Real-time video rendering
   - AR overlay engine
   - Detection bounding boxes
   - HUD with system metrics
   - Lens distortion correction
   - Rear camera integration with Claude AI captions


QUICK START
===========

Development Setup (Any Platform)
---------------------------------

1. Clone the repository:
   git clone <repository-url>
   cd helmet

2. Build and start with Docker Compose:
   docker compose up

3. The system will start with:
   - Mock video input
   - CPU-based AI inference
   - Simulated audio/voice


Jetson Orin Nano Setup
----------------------

1. Install system dependencies:
   sudo apt update
   sudo apt install -y python3-pip python3-venv python3-dev \
       portaudio19-dev libsndfile1 ffmpeg

2. Run the installation script:
   ./install_jetson.sh

3. Activate virtual environment:
   source venv/bin/activate

4. Start backend services:
   python start_jetson_dev.py

5. In another terminal, start the UI:
   export HELMET_PROFILE=dev
   export PYTHONPATH=$(pwd):$(pwd)/libs
   python apps/visor-ui/main.py


SYSTEM REQUIREMENTS
===================

Development Environment
-----------------------
- Docker & Docker Compose
- Python 3.10+
- 8GB+ RAM
- Any modern CPU

Production (Jetson Orin Nano)
------------------------------
- NVIDIA Jetson Orin Nano
- JetPack 6.x / Ubuntu 22.04
- 8GB RAM (minimum)
- CSI camera (IMX219 or compatible)
- USB camera for rear view (optional)
- Dual OLED displays
- Bone conduction headset with microphone
- CUDA 12.x, TensorRT 8.x


CONFIGURATION
=============

Configuration profiles are stored in configs/profiles/:

dev.json - Development Mode
----------------------------
{
  "video": {
    "camera_type": "webcam",
    "camera_id": 1,
    "width": 1280,
    "height": 720,
    "fps": 60
  },
  "perception": {
    "model_path": "models/yolov8n.pt",
    "device": "cpu",
    "confidence_threshold": 0.7
  },
  "ui": {
    "fullscreen": false,
    "dual_eye": true
  }
}

field.json - Production Mode
-----------------------------
- CSI camera with GStreamer
- GPU-accelerated inference
- Optimized logging
- Fullscreen dual-eye display

Environment Variables
---------------------
Create a .env file:

ANTHROPIC_API_KEY=sk-ant-...  # For Claude AI captions
DEEPGRAM_API_KEY=...          # For advanced ASR (optional)


VOICE COMMANDS
==============

Wake word: "Computer" (configurable)

Command                                 Action
-------                                 ------
"Computer, toggle night mode"           Activate night vision
"Computer, start recording"             Begin video recording
"Computer, stop recording"              End recording
"Computer, take screenshot"             Capture current frame
"Computer, what do you see"             Describe current scene
"Computer, mark target"                 Mark object of interest
"Computer, show navigation"             Navigation mode
"Computer, zoom in/out"                 Adjust zoom level
"Computer, increase/decrease brightness" Adjust display
"Computer, emergency"                   Activate emergency mode
"Computer, system status"               Health check report
"Computer, show/hide HUD"               Toggle overlays


API REFERENCE
=============

gRPC Services
-------------

VideoService (Port 50051)
  rpc GetFrame(FrameRequest) returns (FrameMeta);
  rpc StreamFrames(FrameRequest) returns (stream FrameMeta);

PerceptionService (Port 50052)
  rpc Infer(FrameMeta) returns (DetectionResult);
  rpc InferStream(stream FrameMeta) returns (stream DetectionResult);
  rpc SetROI(ROIRequest) returns (CommandResponse);

VoiceService (Port 50053)
  rpc ProcessAudio(stream AudioData) returns (stream Intent);
  rpc Synthesize(TTSRequest) returns (TTSResponse);

OrchestratorService (Port 50054)
  rpc ExecuteCommand(Command) returns (CommandResponse);
  rpc GetStatus(StatusRequest) returns (HUDStatus);
  rpc StreamStatus(StatusRequest) returns (stream HUDStatus);


PROJECT STRUCTURE
=================

helmet/
├── apps/
│   └── visor-ui/              # Qt/QML UI application
│       ├── main.py            # Main UI entry point
│       ├── video_client.py    # Video stream client
│       ├── perception_client.py
│       ├── caption_client.py  # Claude AI integration
│       ├── rear_camera.py     # Rear camera support
│       └── qml/               # QML UI components
├── services/
│   ├── video/                 # Video capture service
│   ├── perception/            # Object detection service
│   ├── voice/                 # Voice assistant service
│   └── orchestrator/          # System coordinator
├── libs/
│   ├── messages/              # Protobuf definitions
│   └── utils/                 # Shared utilities
├── configs/
│   └── profiles/              # Configuration profiles
├── deploy/
│   ├── docker/                # Docker containers
│   ├── systemd/               # Systemd services
│   └── scripts/               # Deployment scripts
├── models/                    # AI models (yolov8n.pt)
├── logs/                      # Application logs
├── recordings/                # Video recordings
└── docker-compose.yml         # Docker orchestration


DEVELOPMENT
===========

Adding Custom Voice Commands
-----------------------------

1. Edit services/voice/intents.json:

{
  "custom_command": {
    "patterns": ["pattern.*regex", "another.*pattern"],
    "action": "custom_action",
    "parameters": {"param": "value"},
    "response": "Action confirmed"
  }
}

2. Implement action in services/orchestrator/orchestrator_service.py:

elif action == "custom_action":
    # Your implementation
    success = True
    message = "Custom action executed"


Custom AI Models
----------------

1. Place model in models/ directory

2. Update config:

{
  "perception": {
    "model_path": "models/your_model.pt",
    "device": "cuda"
  }
}


Building for Production
------------------------

# Build Docker images
./deploy/scripts/build.sh

# Install as systemd services (Jetson)
sudo ./deploy/scripts/install.sh

# Start/stop services
sudo systemctl start helmet.target
sudo systemctl stop helmet.target


TROUBLESHOOTING
===============

Camera Issues
-------------
# Check available cameras
v4l2-ctl --list-devices

# Test GStreamer pipeline
gst-launch-1.0 nvarguscamerasrc ! nvvideoconvert ! autovideosink


GPU/CUDA Issues
---------------
# Check CUDA availability
python3 -c "import torch; print(torch.cuda.is_available())"

# Monitor GPU usage
nvidia-smi


Audio Issues
------------
# List audio devices
arecord -l
pactl list sources

# Test microphone
arecord -D hw:1,0 -f cd test.wav


PERFORMANCE BENCHMARKS
======================

Jetson Orin Nano (15W mode)
----------------------------
- Video Capture: 30 FPS @ 1920x1080
- Object Detection: 20-25 FPS (YOLOv8n, FP16)
- Voice Recognition: ~500ms latency (Whisper small)
- System Load: 40-60% CPU, 3-4GB RAM


ROADMAP
=======

- [ ] TensorRT model optimization
- [ ] SLAM/Visual odometry integration
- [ ] GPS/IMU sensor fusion
- [ ] Gesture recognition
- [ ] Multi-user collaboration
- [ ] Cloud telemetry dashboard
- [ ] Custom training pipeline


LICENSE
=======

[Your License Here]


CONTRIBUTING
============

Contributions are welcome! Please read our contributing guidelines before
submitting PRs.


CONTACT
=======

[Your Contact Information]


================================================================================
Built with care for the AR/VR community
================================================================================
