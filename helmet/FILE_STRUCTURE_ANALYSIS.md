# Helmet Project - Complete File Structure Analysis

## PROJECT OVERVIEW
**Version:** 1.3.0 | **Platform:** Jetson Orin Nano | **Language:** Python 3.10+

Helmet OS is a microservices-based AR/VR system with:
- Dual-camera vision system (CSI + USB cameras)
- AI object detection (YOLOv8)
- Voice control (offline ASR/TTS)
- Dual-eye AR display (Qt/QML)
- Real-time telemetry and recording

---

## DIRECTORY STRUCTURE

### ROOT LEVEL FILES

```
/home/hvx/HVX/helmet/
├── Documentation
│   ├── README.md                    # Main project documentation
│   ├── README.txt                   # Additional notes
│   ├── TECHNICAL_REVIEW.md          # 50KB comprehensive technical review
│   ├── GETTING_STARTED.md           # Setup and getting started guide
│   ├── GPS_SETUP.md                 # GPS configuration guide
│   ├── INDOOR_POSITIONING_SETUP.md  # Indoor positioning setup
│   ├── POSITIONING_SUMMARY.md       # Positioning system summary
│   ├── RECORDING.md                 # Recording features documentation
│   └── leftoff.txt                  # Developer notes (progress tracker)
│
├── Configuration & Profiles
│   └── configs/profiles/            # Configuration files (see below)
│
├── Dependencies & Deployment
│   ├── requirements-jetson.txt      # Jetson-specific requirements
│   ├── deploy/                      # Deployment scripts (see below)
│   └── venv/                        # Virtual environment (SKIP IN CLEANUP)
│
├── Root-level Test & Utility Scripts
│   ├── camera_debug.py              # Camera debugging utility
│   ├── find_dual_cameras.py         # Discover dual camera setup
│   ├── megaphone.py                 # Audio/voice utility (executable)
│   ├── start_jetson_dev.py          # Jetson development startup (executable)
│   ├── test_cameras.py              # Camera testing (executable)
│   ├── test_dual_camera_combined.py # Dual camera testing (executable)
│   ├── test_dual_camera_setup.py    # Dual camera setup test (executable)
│   ├── test_dual_cameras.py         # Alternative dual camera test (executable)
│   ├── test_gps_raw.py              # GPS raw testing (executable)
│   ├── test_imu_connection.py       # IMU connection testing (executable)
│   ├── test_imu_scan.py             # IMU scanning utility
│   ├── test_opencv_cameras.py       # OpenCV camera testing
│   ├── test_recording.py            # Recording testing (executable)
│   └── test_voice_assistant.py      # Voice assistant testing (executable)
│
├── Cached Assets (REMOVE)
│   ├── .map_cache/                  # Map tile cache (~2000+ PNG files)
│   └── models/
│       ├── coco.names               # YOLO class names
│       ├── yolov4.cfg               # YOLOv4 config (keep for reference)
│       └── yolov4.weights           # YOLOv4 weights (45MB, REMOVE)
│
└── Logs & Recordings (CLEAN)
    ├── logs/                        # Runtime logs
    ├── recordings/                  # Video recordings
    └── .map_cache/                  # Temporary map tiles
```

---

### APPS/ - Frontend UI Layer

**Purpose:** User-facing application (Qt/QML based dual-eye display)

```
apps/visor-ui/                       # MAIN UI APPLICATION - KEEP
├── main.py                          # Entry point (1064 lines)
│   └── Initializes Qt/QML app, handles dual-eye rendering
│   └── Manages camera feeds, AR overlays, HUD
│   └── Orchestrates all hardware and service communication
│
├── QML Interface (Qt Quick/QML files) - KEEP ALL
│   ├── qml/main.qml                 # Primary QML interface
│   ├── qml/HUDOverlay.qml           # AR HUD overlay system
│   ├── qml/DetectionOverlay.qml     # AI detection visualization
│   ├── qml/ClosedCaptions.qml       # Caption display
│   ├── qml/StartupScreen.qml        # Boot/startup screen
│   ├── qml/MinimalStatus.qml        # Minimal status display
│   ├── qml/Minimap.qml              # Map navigation display
│   ├── qml/SensorInfo.qml           # Sensor information display
│   ├── qml/EyeView.qml              # Individual eye view
│   ├── qml/SnapshotAnalysis.qml     # Snapshot analysis UI
│   ├── qml/RearviewMirror.qml       # Rear camera view
│   ├── qml/VoiceOverlay.qml         # Voice interaction display
│   ├── qml/OrientationCrosshair.qml # IMU orientation display
│   └── qml/HUDPresetWheel.qml       # HUD preset selector
│
├── Direct Hardware Interfaces (NO SERVICE DEPENDENCY) - KEEP
│   ├── direct_camera.py             # Direct camera access (238 lines)
│   ├── rear_camera.py               # Rear camera handler (126 lines)
│   ├── gyro_sensor.py               # Gyroscope/IMU handler (275 lines)
│   ├── gps_client.py                # GPS client (257 lines)
│   ├── wake_word_detector.py        # Wake word detection (398 lines)
│   └── test_wake_word.py            # Wake word test utility (177 lines)
│   └── test_gyro.py                 # Gyro test utility (52 lines)
│
├── Voice Assistants (CORE FUNCTIONALITY) - KEEP
│   ├── openai_voice_assistant.py    # OpenAI-based assistant (1099 lines)
│   ├── voice_assistant.py           # Local voice assistant (280 lines)
│   ├── voice_listener.py            # Voice input listener (155 lines)
│
├── Recording & Capture (CORE FUNCTIONALITY) - KEEP
│   ├── full_recorder.py             # Complete recording system (423 lines)
│   ├── video_recorder.py            # Video recording (313 lines)
│
├── System Management (CORE FUNCTIONALITY) - KEEP
│   ├── system_monitor.py            # System monitoring (294 lines)
│   ├── power_manager.py             # Power management (198 lines)
│   ├── minimap_controller.py        # Map/GPS control (336 lines)
│   ├── hud_controller.py            # HUD control (181 lines)
│
├── Service Clients (gRPC COMMUNICATION - OPTIONAL, COULD BE REMOVED)
│   ├── video_client.py              # Video service client (85 lines)
│   ├── perception_client.py         # Perception service client (79 lines)
│   ├── caption_client.py            # Caption service client (227 lines)
│
├── Dependencies
│   ├── requirements.txt              # UI-specific dependencies
│   │   - PySide6, opencv-python, grpcio
│   │   - anthropic, openai, elevenlabs
│   │   - openwakeword, websockets, etc.
│   │
│   └── logs/                        # Runtime logs directory

SUMMARY: 
- TOTAL: 6257 lines of Python
- KEY FILES: main.py (core), openai_voice_assistant.py, full_recorder.py
- KEEP: ALL (this is the entire UI layer)
- REMOVE: Only service clients if backend services removed
```

---

### SERVICES/ - Backend gRPC Microservices

**Purpose:** Independent services providing specialized functionality via gRPC

```
services/                           # BACKEND SERVICES - REMOVE ENTIRE SECTION

├── orchestrator/
│   ├── orchestrator_service.py     # Master coordinator (570 lines)
│   │   └── Implements OrchestratorServiceImpl (gRPC Servicer)
│   │   └── Manages system state, command routing, telemetry
│   │   └── SQLite-based state persistence
│   │   └── CPU/GPU/temp monitoring
│   │   └── PORT: 50054
│   │
│   └── requirements.txt
│
├── video/
│   ├── video_service.py            # Video capture service (527 lines)
│   │   └── Implements VideoServiceImpl (gRPC Servicer)
│   │   └── Hardware-accelerated capture (GStreamer)
│   │   └── Supports: webcam, file, CSI, dual-CSI
│   │   └── Real-time frame streaming
│   │   └── PORT: 50051
│   │
│   └── requirements.txt
│
├── perception/
│   ├── perception_service.py       # AI detection service (656 lines)
│   │   └── Implements PerceptionServiceImpl (gRPC Servicer)
│   │   └── YOLOv8 object detection
│   │   └── ONNX Runtime support
│   │   └── GPU-accelerated on Jetson
│   │   └── ROI (Region of Interest) detection
│   │   └── PORT: 50052
│   │
│   └── requirements.txt
│
├── voice/
│   ├── voice_service.py            # Voice assistant service (555 lines)
│   │   └── Implements VoiceServiceImpl (gRPC Servicer)
│   │   └── Offline ASR (faster-whisper)
│   │   └── TTS synthesis (Piper)
│   │   └── Voice activity detection (WebRTC VAD)
│   │   └── Intent classification
│   │   └── PORT: 50053
│   │
│   ├── intents.json                # Voice command intents
│   └── requirements.txt
│
└── gps/
    ├── gps_service.py              # GPS service (311 lines)
    │   └── NOT a gRPC service - standalone utility
    │   └── Reads Ardusimple GPS via serial
    │   └── NMEA2 sentence parsing
    │   └── GPS data container and reader
    │
    ├── wifi_positioning.py         # WiFi geolocation (310 lines)
    │   └── WiFi-based positioning fallback
    │   └── Google Geolocation API integration
    │   └── Access point scanning
    │
    └── __init__.py

SUMMARY:
- TOTAL: 2934 lines of Python
- ARCHITECTURE: Pure gRPC microservices (except GPS which is standalone)
- DEPENDENCY: All require grpcio and service clients
- PORTS: 50051-50054
- FUNCTION: Orchestrate and delegate work to specialized services
- REMOVAL IMPACT: UI must be refactored to call hardware directly instead of via gRPC
```

---

### LIBS/ - Shared Libraries & Protocol Definitions

**Purpose:** Common code, gRPC definitions, utilities

```
libs/

├── messages/                        # gRPC Protocol Definitions
│   ├── helmet.proto                 # Protobuf service definitions (136 lines)
│   │   ├── FrameMeta - video frame data
│   │   ├── Detection - AI detection results
│   │   ├── Intent - voice command intents
│   │   ├── SystemStatus - telemetry
│   │   ├── HUDStatus - display status
│   │   ├── Services defined: VideoService, PerceptionService, VoiceService, OrchestratorService
│   │
│   ├── helmet_pb2.py               # Generated protobuf code (auto-generated)
│   ├── helmet_pb2_grpc.py          # Generated gRPC code (auto-generated)
│   ├── generate_pb.py              # Protobuf compiler script
│   ├── __init__.py
│   └── requirements.txt
│
└── utils/
    ├── config.py                    # Configuration manager (50+ lines)
    │   └── Config class that loads profiles from configs/profiles/*.json
    │   └── Nested configuration access via dots (e.g., "video.camera_type")
    │   └── Default configuration fallback
    │
    ├── logging_utils.py             # Logging utilities
    │   └── Centralized logging setup
    │   └── Performance logging decorators
    │
    └── __init__.py

SUMMARY:
- KEEP: libs/utils/ (needed by visor-ui)
- REMOVE OR REFACTOR: libs/messages/ (gRPC definitions)
  - helmet.proto can be deleted (services gone)
  - helmet_pb2.py and helmet_pb2_grpc.py only needed if UI retains service clients
```

---

### CONFIGS/ - Configuration Profiles

**Purpose:** System configuration for different environments

```
configs/profiles/

├── dev.json                         # Development config (MAIN ACTIVE CONFIG)
│   ├── video: dual_usb cameras, CSI disabled, mocking disabled
│   ├── perception: YOLOv8n, CPU mode, confidence 0.7
│   ├── voice: ASR "small", offline, 16kHz sampling
│   ├── ui: fullscreen=false, dual_eye=true, lens correction enabled
│   ├── assistant: OpenAI voice assistant config (lengthy system prompt)
│   ├── services: gRPC ports 50051-50054
│   ├── caption: Mic device #5
│   └── assistant: Mic/output device indices (5, 6)
│
├── field.json                       # Field/production config
│   └── Likely: CSI cameras enabled, GPU acceleration, optimized settings
│
└── demo.json                        # Demo configuration
    └── Mock data, lightweight settings for testing

SUMMARY:
- KEEP: configs/profiles/
- ACTION: May need to update if services removed (comment out service ports)
```

---

### DEPLOY/ - Deployment & Orchestration

**Purpose:** Docker, systemd, and deployment automation

```
deploy/

├── docker/                          # Docker containers
│   ├── Dockerfile.base              # Base image with dependencies
│   ├── Dockerfile.dev               # Development environment
│   ├── Dockerfile.ui                # UI container (visor-ui)
│   ├── Dockerfile.video             # Video service container
│   ├── Dockerfile.perception        # Perception service container
│   ├── Dockerfile.voice             # Voice service container
│   └── Dockerfile.orchestrator      # Orchestrator service container
│   └── (probably docker-compose.yml too, check if exists)
│
├── systemd/                         # Linux systemd unit files
│   ├── helmet.target                # Master target (all services)
│   ├── helmet-ui.service            # UI service unit
│   ├── helmet-video.service         # Video service unit
│   ├── helmet-perception.service    # Perception service unit
│   ├── helmet-voice.service         # Voice service unit
│   └── helmet-orchestrator.service  # Orchestrator service unit
│
└── scripts/                         # Deployment automation
    ├── build.sh                     # Build all containers
    ├── start.sh                     # Start all services
    ├── stop.sh                      # Stop all services
    └── install.sh                   # Installation script

SUMMARY:
- KEEP: deploy/docker/Dockerfile.ui, deploy/docker/Dockerfile.base
- REMOVE: Deploy files for orchestrator, video, perception, voice services
- UPDATE: docker-compose.yml if exists (remove service containers)
- UPDATE: systemd units for removed services
```

---

## CATEGORIZATION FOR CLEANUP

### KEEP - Core UI & Hardware Integration (6000+ lines)
```
KEEP ALL OF apps/visor-ui/:
  - main.py (orchestrates everything)
  - All QML files in qml/
  - Direct camera/IMU/GPS handlers
  - Voice assistants (OpenAI + local)
  - Recording and system monitoring
  - Service clients (can refactor to direct hardware access)

KEEP FROM libs/:
  - libs/utils/ (config.py, logging_utils.py)
  - Keep for: configuration and logging infrastructure

KEEP FROM configs/:
  - configs/profiles/ (dev.json, field.json, demo.json)
  - Update as needed after removing services
```

### REMOVE - Backend Services (2900+ lines)
```
REMOVE ENTIRE services/ DIRECTORY:
  services/orchestrator/           (570 lines, gRPC master coordinator)
  services/video/                  (527 lines, gRPC video capture)
  services/perception/             (656 lines, gRPC AI detection)
  services/voice/                  (555 lines, gRPC voice assistant)
  services/gps/                    (620 lines, GPS + WiFi positioning)
    - Except: GPS hardware interface can be kept as library if needed

RATIONALE:
  - All are gRPC server implementations
  - Serve same functions as visor-ui handlers
  - Redundant architecture for single-application system
  - Visor-ui already has direct hardware access
```

### REMOVE - Deployment Infrastructure
```
REMOVE deploy/systemd/:
  - All .service files for removed services
  - Keep: helmet-ui.service (update to run without services)

REMOVE FROM deploy/docker/:
  - Dockerfile.orchestrator
  - Dockerfile.video
  - Dockerfile.perception
  - Dockerfile.voice
  
KEEP:
  - Dockerfile.base (if UI still uses it)
  - Dockerfile.ui
  - Dockerfile.dev
  - docker-compose.yml (if simplified to UI only)
```

### CLEAN - Cache & Temporary Files
```
REMOVE .map_cache/:
  - 2000+ PNG map tiles (generated, not source)
  
REMOVE models/:
  - yolov4.weights (45MB, legacy)
  - Keep: coco.names, yolov4.cfg (small, reference only)

REMOVE logs/ and recordings/:
  - Runtime artifacts (regeneratable)
```

### KEEP - Root-level Files & Tests
```
KEEP ALL:
  - Documentation (README.md, TECHNICAL_REVIEW.md, etc.)
  - Configuration files (requirements-jetson.txt)
  - Test scripts (camera, GPS, IMU, voice, recording tests)
  - Utility scripts (start_jetson_dev.py, megaphone.py)

RATIONALE:
  - Documentation essential for understanding system
  - Test scripts useful for hardware validation
  - Utility scripts aid development and troubleshooting
```

---

## REFACTORING REQUIREMENTS

After removing services, the visor-ui will need updates:

1. **Video Capture**
   - Currently: video_client.py calls VideoService via gRPC
   - After: Use direct_camera.py and rear_camera.py directly
   - Files: apps/visor-ui/main.py, direct_camera.py

2. **AI Detection**
   - Currently: perception_client.py calls PerceptionService
   - After: Integrate YOLOv8 detection directly into main.py
   - Dependencies: Already in requirements.txt (ultralytics, onnxruntime)

3. **Voice Processing**
   - Currently: Has local openai_voice_assistant.py (good!)
   - Currently: Also has voice_listener.py for direct input
   - Keep as-is, remove dependency on voice_service.py calls

4. **GPS/Positioning**
   - Currently: gps_client.py gets data from service
   - After: Integrate gps_service.py as library or direct serial reader
   - Files: Could move gps_service.py logic into gps_client.py

5. **Orchestration & State**
   - Currently: Calls orchestrator_service.py
   - After: Move state management into main.py or new local module
   - Focus on: Recording state, mode switching, telemetry

---

## KEY METRICS

| Component | Files | Lines | Status |
|-----------|-------|-------|--------|
| visor-ui | 30 Python + 14 QML | 6257 | KEEP |
| services | 5 Python | 2934 | REMOVE |
| libs | 5 Python | ~200 | KEEP utils, refactor messages |
| configs | 3 JSON | ~1000 | KEEP |
| deploy | 15 files | varies | Partial keep |
| tests | 12 scripts | varies | KEEP |
| **TOTAL (Keep)** | ~60 | ~8000+ | **Core System** |
| **TOTAL (Remove)** | ~20 | ~3000 | **Backend Services** |

---

## CLEANUP PLAN SUMMARY

### Phase 1: Remove Services (2900 lines deleted)
- Delete entire `services/` directory
- Delete obsolete gRPC definitions (keep config.proto pattern if needed)
- Delete service Docker files and systemd units

### Phase 2: Refactor UI (6257 lines modified slightly)
- Update main.py to call hardware directly instead of gRPC clients
- Consolidate configuration (direct_camera.py, gyro_sensor.py, gps_client.py)
- Integrate AI detection directly
- Integrate voice processing logic

### Phase 3: Clean Build Artifacts
- Remove `.map_cache/` (2000+ generated PNG files)
- Remove `models/yolov4.weights` (45MB)
- Clean `logs/` and `recordings/` directories
- Update `docker-compose.yml` if it references old services

### Phase 4: Update Documentation
- Update README.md to reflect new architecture (single-process instead of microservices)
- Update deployment guides
- Keep technical review as historical reference

**Result:** Single cohesive Qt/QML application with direct hardware access, no inter-process communication overhead, simpler deployment.

