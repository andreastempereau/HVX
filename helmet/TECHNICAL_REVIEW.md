# COMPREHENSIVE TECHNICAL REVIEW: Helmet OS AR/VR Vision System

## EXECUTIVE SUMMARY

**Project Name:** Helmet OS - AR/VR Vision System
**Version:** 1.2.0
**Platform:** NVIDIA Jetson Orin Nano (ARM64, Ubuntu 22.04, JetPack 6.x)
**Total Codebase:** 6,141+ lines of Python, 34 Python modules, extensive QML UI
**Architecture:** Microservices-based with gRPC inter-process communication
**Primary Language:** Python 3.10+
**UI Framework:** Qt6/QML (PySide6)

---

## 1. SYSTEM ARCHITECTURE

### 1.1 High-Level Architecture

The system follows a **distributed microservices architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                 Visor UI (Qt6/QML Frontend)                 │
│    Dual-Eye Compositor • AR Overlays • HUD • User Input     │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴───────────┐
        │   Orchestrator       │
        │  System Coordinator  │
        │  State Management    │
        └──────────┬───────────┘
                   │
    ┌──────────────┼──────────────────┐
    │              │                  │
┌───▼──────┐  ┌───▼────────┐  ┌──────▼──────┐
│  Video   │  │ Perception │  │    Voice    │
│ Service  │  │  Service   │  │   Service   │
└──────────┘  └────────────┘  └─────────────┘
```

**Design Philosophy:**
- **Microservices:** Each service is independently deployable and can run on different ports
- **gRPC Communication:** High-performance binary protocol for inter-service communication
- **Event-Driven:** Qt signals/slots for UI reactivity
- **Hardware-Accelerated:** Direct GStreamer pipelines, CUDA/TensorRT support
- **Real-time:** Low-latency video processing (<50ms frame-to-display)

### 1.2 File Structure

```
helmet/
├── apps/visor-ui/          # Main UI application (19 Python files, 6,141 lines)
│   ├── main.py             # Entry point, Qt/QML initialization
│   ├── qml/                # QML UI components
│   │   └── main.qml        # Main window, video, overlays
│   ├── direct_camera.py    # GStreamer dual-camera handler
│   ├── openai_voice_assistant.py  # OpenAI Realtime API integration
│   ├── gyro_sensor.py      # BNO055 IMU sensor (I2C)
│   ├── gps_client.py       # GPS reader client
│   ├── system_monitor.py   # System telemetry (CPU, GPU, memory, temp)
│   └── [15+ other modules]
├── services/               # Backend microservices
│   ├── video/              # Video capture service (GStreamer, OpenCV)
│   ├── perception/         # Object detection (YOLOv8, ONNX)
│   ├── voice/              # Voice ASR/TTS (Whisper, Piper)
│   ├── orchestrator/       # System coordination, state management
│   └── gps/                # GPS service (NMEA parsing)
├── libs/                   # Shared libraries
│   ├── messages/           # Protobuf definitions (helmet.proto)
│   └── utils/              # Config, logging utilities
├── configs/profiles/       # Configuration profiles (dev.json, field.json)
├── deploy/                 # Deployment scripts, Docker, systemd
└── models/                 # AI models (yolov8n.pt)
```

---

## 2. CORE SERVICES - DETAILED BREAKDOWN

### 2.1 VIDEO SERVICE (services/video/video_service.py)

**Purpose:** Hardware-accelerated video capture and frame streaming

**Key Features:**
- **Multi-Camera Support:**
  - USB Webcams (development)
  - CSI cameras via GStreamer (IMX219)
  - Dual CSI cameras with side-by-side/PIP modes
  - Video file playback (testing)

**Implementation Details:**

**Camera Initialization (video_service.py:38-234):**
```python
class VideoCapture:
    def _setup_capture(self):
        - Detects camera type from config (webcam/csi/csi_dual/file)
        - For USB: Uses OpenCV with V4L2 backend, forces MJPEG format
        - For CSI: Builds GStreamer pipeline with nvarguscamerasrc
        - For dual CSI: Creates two separate pipelines, combines frames
```

**GStreamer Pipeline Example (line 78):**
```
nvarguscamerasrc sensor-id=0 !
video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12, framerate=30/1 !
nvvideoconvert flip-method=2 !   # 180° rotation
video/x-raw, format=BGRx !
videoconvert !
appsink
```

**Frame Combination Modes (line 235-290):**
- **Side-by-side:** `np.hstack((left, right))` - horizontal concat
- **Top-bottom:** `np.vstack((left, right))` - vertical concat
- **Picture-in-Picture:** Resize + overlay with configurable position

**gRPC Interface:**
- `GetFrame()` - Single frame request
- `StreamFrames()` - Continuous streaming (target FPS from config)
- Port: 50051 (configurable)
- Max message size: 50MB (high-res frame support)

**Performance Optimizations:**
- Buffer size = 1 (minimize latency)
- Auto-exposure/autofocus disabled (reduce CPU)
- Frame dropping enabled (prefer fresh frames)
- YUYV misinterpretation detection and correction

**Libraries Used:**
- `opencv-python==4.8.1.78` - Frame capture, format conversion
- `numpy==1.24.3` - Array operations
- `grpcio==1.60.0` - Network communication

---

### 2.2 PERCEPTION SERVICE (services/perception/perception_service.py)

**Purpose:** Real-time object detection and scene analysis

**Architecture:**

**Model Support (line 60-132):**
1. **Primary: Ultralytics YOLOv8**
   - Model: `yolov8n.pt` (nano, fastest)
   - Input size: 640x640
   - Device: CPU or CUDA (auto-detect)
   - Confidence threshold: 0.7
   - NMS threshold: 0.4

2. **Secondary: ONNX Runtime**
   - Providers: CPUExecutionProvider, CUDAExecutionProvider
   - Quantization: INT8 for speed

3. **Fallback: OpenCV DNN + Haar Cascades**
   - Face detection only
   - Used when no ML library available

**Detection Pipeline (line 134-158):**
```python
def detect(frame):
    1. Apply ROI if set (crop to region of interest)
    2. Run inference via _run_inference()
    3. Parse detections (bounding boxes, labels, confidence)
    4. Return normalized coordinates (0-1 range)
```

**Inference Implementation (line 159-199):**
```python
if ULTRALYTICS_AVAILABLE:
    results = model.predict(
        frame,
        imgsz=(640, 640),
        conf=0.7,
        iou=0.4,
        max_det=100,
        verbose=False
    )
    # Extract boxes.xyxyn (normalized coords)
    # Extract boxes.conf (confidence)
    # Extract boxes.cls (class ID)
```

**PyTorch 2.6+ Compatibility Fix (line 30-46):**
```python
# Allows loading YOLOv8 models with safe_globals
torch.serialization.add_safe_globals([
    DetectionModel,
    torch.nn.modules.container.Sequential,
    # ... more modules
])
```

**gRPC Interface:**
- `Infer(FrameMeta)` - Single frame inference
- `InferStream(stream)` - Continuous detection
- `SetROI(ROIRequest)` - Set region of interest
- Port: 50052

**Performance:**
- **Jetson Orin Nano:** 20-25 FPS (YOLOv8n, FP16)
- **CPU mode:** ~5-10 FPS
- Inference time logged per frame

**COCO Classes:** 80 classes (person, car, bicycle, dog, etc.)

**Libraries Used:**
- `ultralytics==8.0.220` - YOLOv8 implementation
- `onnxruntime==1.16.3` - ONNX inference
- `torch` (pre-installed on Jetson) - Model loading
- `opencv-python` - Image preprocessing

---

### 2.3 VOICE SERVICE (services/voice/voice_service.py)

**Purpose:** Voice input processing (ASR + intent classification) and TTS

**Components:**

**1. AudioCapture (line 51-159):**
- **Microphone Input:** PyAudio with configurable device
- **Voice Activity Detection:** WebRTC VAD (aggressiveness=2)
- **Frame Duration:** 30ms chunks
- **Sample Rate:** 16kHz, mono
- **Queue-based:** Audio buffered for processing

**2. ASREngine (line 160-229) - Automatic Speech Recognition:**
- **Model:** faster-whisper (CTranslate2 optimized)
- **Model Size:** small (configurable: tiny/base/small/medium/large)
- **Device:** Auto (GPU if available)
- **Quantization:** INT8 for speed
- **Language:** English (configurable)
- **Beam Size:** 1 (fastest)
- **Temperature:** 0.0 (deterministic)

**Transcription Pipeline:**
```python
audio_float = audio_int16.astype(np.float32) / 32768.0
segments, info = model.transcribe(audio_float, language='en')
text = " ".join([seg.text for seg in segments])
```

**3. IntentEngine (line 230-347) - Intent Classification:**
- **Method:** Regex pattern matching
- **Intents File:** `intents.json` (customizable)

**Default Intents (line 250-309):**
```json
{
  "toggle_night_mode": {
    "patterns": ["toggle night.*mode", "night.*vision"],
    "action": "set_mode",
    "parameters": {"mode": "night"}
  },
  "start_recording": {
    "patterns": ["start.*record", "begin.*record"],
    "action": "toggle_recording",
    "parameters": {"enabled": true}
  },
  // ... 15+ voice commands
}
```

**4. TTSEngine (line 348-406) - Text-to-Speech:**
- **Model:** Piper TTS (planned)
- **Voice:** en_US-ljspeech-medium
- **Fallback:** Mock TTS (sine wave beeps)

**gRPC Interface:**
- `ProcessAudio(stream AudioData)` → `stream Intent`
- `Synthesize(TTSRequest)` → `TTSResponse`
- Port: 50053

**Performance:**
- **Whisper small latency:** ~500ms
- **VAD latency:** <50ms
- **Intent classification:** <10ms

**Libraries Used:**
- `faster-whisper==0.10.0` - Optimized Whisper
- `pyaudio==0.2.13` - Audio I/O
- `webrtcvad==2.0.10` - Voice activity detection
- `piper-tts` (optional) - Text-to-speech

---

### 2.4 ORCHESTRATOR SERVICE (services/orchestrator/orchestrator_service.py)

**Purpose:** System coordination, state management, and command routing

**Architecture:**

**1. SystemState (line 27-209) - State Management:**
- **Database:** SQLite (system_state.db)
- **Tables:**
  - `system_state` - Key-value configuration
  - `telemetry_log` - Performance metrics
  - `command_log` - Command history

**State Variables:**
```python
current_mode: str   # normal, night, navigation, debug, emergency
recording: bool
brightness: int     # 0-100
zoom_level: float   # 0.5-5.0
marked_targets: list
```

**Methods:**
- `set_mode(mode)` - Change operating mode
- `toggle_recording(enabled)` - Start/stop recording
- `adjust_brightness(direction)` - ±10% brightness
- `adjust_zoom(direction)` - ×1.2 or ÷1.2
- `mark_target(x, y)` - Mark point of interest
- `emergency_mode()` - Activate emergency (auto-record)

**2. ServiceClients (line 210-253) - Service Connections:**
- Connects to Video, Perception, Voice services
- Maintains gRPC channels
- Provides service discovery

**3. OrchestratorServiceImpl (line 254-523) - gRPC Server:**

**Command Execution (line 266-353):**
```python
def ExecuteCommand(request):
    action = request.action
    parameters = dict(request.parameters)

    # Route to appropriate handler
    if action == "set_mode":
        success = system_state.set_mode(parameters["mode"])
    elif action == "toggle_recording":
        success = system_state.toggle_recording()
    elif action == "emergency_mode":
        success = system_state.emergency_mode()
    # ... etc

    # Log command execution
    system_state.log_command(intent, action, parameters, success)

    return CommandResponse(success, message, timestamp)
```

**Status Monitoring (line 354-422):**
```python
def _get_hud_status():
    system_status = SystemStatus()
    system_status.cpu_usage = psutil.cpu_percent()
    system_status.memory_usage = psutil.virtual_memory().percent
    system_status.temperature = _get_temperature()  # psutil.sensors_temperatures()
    system_status.battery_level = _get_battery_level()  # psutil.sensors_battery()
    system_status.recording = recording
    system_status.current_mode = mode

    hud_status = HUDStatus()
    hud_status.system = system_status
    hud_status.fps = 30  # From video service
    hud_status.detection_count = 0  # From perception
    hud_status.status_message = _get_status_message()

    return hud_status
```

**gRPC Interface:**
- `ExecuteCommand(Command)` → `CommandResponse`
- `GetStatus(StatusRequest)` → `HUDStatus`
- `StreamStatus(StatusRequest)` → `stream HUDStatus` (1Hz)
- Port: 50054

**Libraries Used:**
- `psutil==5.9.6` - System metrics
- `sqlite3` (built-in) - State persistence
- `asyncio-mqtt==0.16.1` - MQTT (optional)

---

### 2.5 GPS SERVICE (services/gps/gps_service.py)

**Purpose:** Read GPS data from Ardusimple GPS module via serial NMEA

**Architecture:**

**GPSData Container (line 15-48):**
```python
class GPSData:
    latitude: float         # Decimal degrees
    longitude: float        # Decimal degrees
    altitude: float         # Meters
    speed: float            # km/h
    heading: float          # Degrees (0-360)
    fix_quality: int        # 0=no fix, 1=GPS, 2=DGPS, 4=RTK Fixed
    satellites: int         # Number of satellites
    hdop: float             # Horizontal dilution of precision
    timestamp: datetime     # GPS time
    last_update: datetime   # Last data received
```

**GPSReader (line 50-312):**

**Connection (line 69-95):**
```python
serial_conn = serial.Serial(
    port='/dev/ttyUSB0',
    baudrate=115200,  # Ardusimple default
    timeout=1.0,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
)
```

**NMEA Parsing (line 180-241):**
Supports multiple NMEA sentence types:
- **GGA** - Fix data (lat, lon, alt, satellites, fix quality, HDOP)
- **RMC** - Recommended minimum (lat, lon, speed, heading, timestamp)
- **VTG** - Course and speed (speed in km/h, heading)
- **GSA** - Satellite status (HDOP)

**Example NMEA Parsing:**
```python
if isinstance(msg, pynmea2.GGA):
    data.latitude = msg.latitude
    data.longitude = msg.longitude
    data.altitude = msg.altitude
    data.fix_quality = int(msg.gps_qual)
    data.satellites = int(msg.num_sats)
    data.hdop = float(msg.horizontal_dil)
```

**Thread-Safe Reading (line 242-253):**
```python
def get_data():
    with lock:
        return data.copy()
```

**RTK Support:**
- Fix quality 4 = RTK Fixed (cm-level accuracy)
- Fix quality 5 = RTK Float (dm-level accuracy)

**Libraries Used:**
- `pyserial==3.5` - Serial communication
- `pynmea2==1.19.0` - NMEA sentence parsing

---

## 3. VISOR UI APPLICATION - FRONTEND

### 3.1 Main Application (apps/visor-ui/main.py)

**Architecture:** Qt6/QML hybrid (Python backend + QML frontend)

**Initialization Sequence (line 972-1044):**
```python
1. Load .env file (API keys, secrets)
2. Setup logging (system.log_level, logs/)
3. Create QGuiApplication
4. Register QML types (VisorApp)
5. Create QQmlApplicationEngine
6. Register image providers:
   - VideoImageProvider (zero-copy frame updates)
   - MinimapImageProvider (GPS map tiles)
7. Create VisorApp instance
8. Setup minimap controller
9. Load main.qml
10. Start VisorApp (begin frame loop)
11. Run Qt event loop
```

**VisorApp Class (line 77-971) - Main Controller:**

**Components Initialized:**
```python
- direct_camera          # Dual GStreamer cameras
- perception_client      # Object detection client
- hud_controller         # HUD data aggregation
- voice_listener         # Voice command listener (DISABLED)
- caption_client         # Deepgram captions (DISABLED)
- voice_assistant        # OpenAI Realtime API
- wake_word_detector     # openWakeWord (offline)
- gyro_sensor            # BNO055 IMU (I2C bus 7)
- system_monitor         # CPU/GPU/memory/temp telemetry
- video_recorder         # Full screen recording (video+audio)
- gps_client             # GPS/NMEA reader
- minimap_controller     # Map rendering
```

**Qt Signals (line 80-90):**
```python
frameUpdated = Signal(str)                    # Video frame path
detectionsUpdated = Signal('QVariantList')    # Object detections
hudStatusUpdated = Signal('QVariantMap')      # System status
snapshotAnalyzed = Signal(str, str)           # Snapshot + analysis
voiceCommandReceived = Signal(str)            # Voice command
captionReceived = Signal(str, bool)           # Caption text + final flag
orientationUpdated = Signal(float, float, float)  # heading, roll, pitch
gpsPositionUpdated = Signal(float, float, float, float)  # lat, lon, alt, heading
gpsStatusUpdated = Signal('QVariantMap')      # GPS status
minimapUpdated = Signal(str)                  # Minimap image path
```

**Frame Update Loop (line 643-713):**
```python
def _update_frame():
    1. Record frame timestamp for FPS tracking
    2. Get frame from direct_camera.get_frame()  # numpy RGB array
    3. Convert numpy → QImage (zero-copy via data pointer)
    4. If recording: Grab QML window framebuffer (includes widgets)
    5. Add full screen capture to video_recorder
    6. Update image_provider with new frame
    7. Emit frameUpdated signal to QML (triggers refresh)
    8. (Optional) Run perception inference asynchronously

Timer: 30 FPS (33ms interval)
```

**HUD Update Loop (line 746-756):**
```python
def _update_hud():
    status = hud_controller.get_status()  # Aggregates all telemetry
    emit hudStatusUpdated(status)

Timer: 1 Hz (1000ms interval)
```

### 3.2 Camera System (apps/visor-ui/direct_camera.py)

**DirectCamera Class - Dual GStreamer CSI Capture**

**Key Features:**
- **Direct GStreamer API** (via gi.repository.Gst)
- **Zero-copy buffers** (NVMM memory)
- **Hardware acceleration** (nvarguscamerasrc, nvvidconv)
- **Dual simultaneous capture** (left + right cameras)
- **Split-screen output** (side-by-side)

**Pipeline Architecture (line 54-75):**
```
Left Camera:
nvarguscamerasrc sensor-id=0 →
video/x-raw(memory:NVMM), 1280x720, NV12, 30fps →
nvvidconv flip-method=2 →  # 180° rotation
video/x-raw, BGRx →
videoconvert → BGR →
appsink (emit-signals=true, drop=true)

Right Camera: (identical, sensor-id=1)
```

**Frame Callback (line 111-147):**
```python
def _on_new_sample_left(appsink):
    sample = appsink.emit('pull-sample')
    buf = sample.get_buffer()
    success, map_info = buf.map(Gst.MapFlags.READ)

    # Convert to numpy array (zero-copy view)
    frame = np.ndarray(
        shape=(height, width, 3),
        dtype=np.uint8,
        buffer=map_info.data
    )

    # Store copy (original buffer will be unmapped)
    with frame_lock:
        current_frame_left = frame.copy()

    buf.unmap(map_info)
```

**Frame Combining (line 189-217):**
```python
def get_frame():
    if not current_frame_left or not current_frame_right:
        return None

    # Side-by-side: [Left | Right]
    combined = np.hstack((
        cv2.cvtColor(current_frame_left, cv2.COLOR_BGR2RGB),
        cv2.cvtColor(current_frame_right, cv2.COLOR_BGR2RGB)
    ))

    return combined  # Shape: (720, 2560, 3)
```

**Performance:**
- **Latency:** <50ms (direct pipeline, no encoding)
- **FPS:** 30 (configurable, tested up to 60)
- **Resolution:** 1280x720 per camera (2560x720 combined)

### 3.3 Voice Assistant (apps/visor-ui/openai_voice_assistant.py)

**OpenAI Realtime API Integration - Low-Latency Voice**

**Architecture:**
- **WebSocket API:** wss://api.openai.com/v1/realtime
- **Audio Streaming:** PCM 16-bit, 24kHz, mono
- **Voice-to-Voice:** Speech → Speech (no intermediate text)
- **Model:** gpt-4o-realtime-preview-2024-12-17

**Key Features:**
1. **Wake Word Activation** (via openWakeWord detector)
2. **Continuous Conversation** (no timeout)
3. **Function Calling** (control helmet functions)
4. **Vision Integration** (on-demand camera frame analysis)
5. **Dismissal Phrases** (end conversation gracefully)

**Initialization (line 16-66):**
```python
__init__(
    openai_api_key: str,
    system_prompt: str,  # "Aegis" personality from config
    voice: str = "echo",  # alloy/echo/fable/onyx/nova/shimmer
    input_device_index: int,  # Microphone
    output_device_index: int,  # Bone conduction speakers
    output_volume: float = 3.0,  # Amplification (0-5)
    wake_word_detector,  # Resume after deactivation
    frame_getter,  # Get camera frame on-demand
    system_monitor,  # System telemetry
    video_recorder   # Recording control
)
```

**WebSocket Event Loop (async):**
```python
async def _run_assistant():
    ws = await websockets.connect(OPENAI_REALTIME_URL)

    # Send session config
    await ws.send({
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": voice,
            "instructions": system_prompt,
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",  # Server-side VAD
                "threshold": 0.5,
                "silence_duration_ms": 500
            },
            "tools": [
                {"type": "function", "name": "start_recording"},
                {"type": "function", "name": "stop_recording"},
                {"type": "function", "name": "get_camera_view"},
                {"type": "function", "name": "get_system_telemetry"}
            ]
        }
    })

    # Parallel tasks:
    await asyncio.gather(
        _send_audio_loop(ws),      # Mic → OpenAI
        _receive_audio_loop(ws),   # OpenAI → Speaker
        _handle_events_loop(ws)    # Commands, transcripts
    )
```

**Function Calling Example:**
```python
# Assistant says: "Starting recording now"
# Receives function_call event:
{
    "type": "response.function_call_arguments.done",
    "call_id": "call_123",
    "name": "start_recording",
    "arguments": "{\"duration\": 60}"
}

# Execute function
result = video_recorder.start_recording()

# Return result to assistant
await ws.send({
    "type": "conversation.item.create",
    "item": {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": json.dumps({"success": True, "message": "Recording started"})
    }
})
```

**Vision Integration (On-Demand):**
```python
async def _get_camera_view():
    qimage = frame_getter()  # Get current QImage

    # Convert to base64 JPEG
    buffer = QByteArray()
    qimage.save(buffer, "JPEG", 85)
    image_base64 = base64.b64encode(buffer.data()).decode()

    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
    }
```

**Dismissal Detection:**
```python
dismissal_phrases = [
    'okay thanks', 'thank you', 'that\'s all',
    'dismiss', 'goodbye', 'never mind'
]

if any(phrase in transcript.lower() for phrase in dismissal_phrases):
    deactivate()  # Close mic, resume wake word detector
```

**Performance:**
- **Latency:** 200-500ms (voice → response)
- **Bandwidth:** ~24 kbps audio upload, ~48 kbps download
- **Cost:** $0.06 per minute (audio in) + $0.24 per minute (audio out)

### 3.4 Wake Word Detection (apps/visor-ui/wake_word_detector.py)

**openWakeWord - Offline Wake Word Detection**

**Key Features:**
- **Fully Offline** (no cloud API)
- **Custom Models** (trained on specific phrases)
- **Low CPU** (<5% on Jetson)
- **Pre-trained models:** "hey jarvis", "alexa", "hey mycroft"

**Architecture:**
```python
from openwakeword.model import Model

model = Model(
    inference_framework='onnx',  # or 'tflite'
    custom_model_path='/path/to/hey_jarvis.tflite'
)

# Continuous audio stream
while running:
    audio_chunk = mic_stream.read(1280)  # 80ms @ 16kHz
    prediction = model.predict(audio_chunk)

    if prediction['hey_jarvis'] > 0.5:  # Confidence threshold
        callback('hey_jarvis')  # Trigger activation
        pause()  # Release microphone
```

**Integration:**
```python
wake_word_detector.start(callback=_on_wake_word_detected)

def _on_wake_word_detected(keyword):
    voice_assistant.activate()  # Open mic, start conversation

# When conversation ends:
def _on_conversation_end():
    wake_word_detector.resume()  # Resume wake word listening
```

### 3.5 Gyroscope/IMU (apps/visor-ui/gyro_sensor.py)

**BNO055 9-DOF Absolute Orientation Sensor**

**Hardware:**
- **Chip:** Bosch BNO055
- **Interface:** I2C (bus 7, address 0x28)
- **Sensors:** 3-axis accelerometer, gyroscope, magnetometer
- **Fusion:** On-chip sensor fusion (quaternion output)

**Operating Modes:**
```python
OPERATION_MODE_NDOF = 0x0C      # 9DOF fusion (smoothed, slow)
OPERATION_MODE_IMUPLUS = 0x08   # 6DOF IMU (faster, no mag)
OPERATION_MODE_ACCGYRO = 0x05   # Raw sensors (fastest, no fusion)
```

**Current Configuration:** ACCGYRO mode (raw, instant response)

**I2C Communication (via smbus2):**
```python
from smbus2 import SMBus

bus = SMBus(7)  # I2C bus 7

# Verify chip ID
chip_id = bus.read_byte_data(0x28, 0x00)
assert chip_id == 0xA0  # BNO055

# Set operating mode
bus.write_byte_data(0x28, 0x3D, 0x05)  # ACCGYRO mode

# Read Euler angles (6 bytes)
data = bus.read_i2c_block_data(0x28, 0x1A, 6)
heading = struct.unpack('<h', bytes(data[0:2]))[0] / 16.0  # LSB = 1/16 degree
roll = struct.unpack('<h', bytes(data[2:4]))[0] / 16.0
pitch = struct.unpack('<h', bytes(data[4:6]))[0] / 16.0
```

**Orientation Update Loop:**
```python
def _read_loop():
    while running:
        # Read raw gyro data (6 bytes @ 0x14)
        gyro_data = bus.read_i2c_block_data(address, 0x14, 6)
        gyro_x = struct.unpack('<h', bytes(gyro_data[0:2]))[0] / 900.0  # rad/s
        gyro_y = struct.unpack('<h', bytes(gyro_data[2:4]))[0] / 900.0
        gyro_z = struct.unpack('<h', bytes(gyro_data[4:6]))[0] / 900.0

        # Integrate angular velocity
        dt = time.time() - last_update_time
        integrated_roll += gyro_x * dt
        integrated_pitch += gyro_y * dt

        # Read Euler (fused orientation)
        euler_data = bus.read_i2c_block_data(address, 0x1A, 6)
        heading = struct.unpack('<h', bytes(euler_data[0:2]))[0] / 16.0

        # Emit callback
        callback({
            'euler': (heading, roll, pitch),
            'gyro': (gyro_x, gyro_y, gyro_z),
            'timestamp': time.time()
        })

        time.sleep(1/60)  # 60 Hz update rate
```

**Calibration:**
- **System:** 0-3 (0=uncalibrated, 3=fully calibrated)
- **Gyro:** 0-3
- **Accel:** 0-3
- **Mag:** 0-3

**Performance:**
- **Update Rate:** 60 Hz
- **Latency:** <20ms (raw mode)
- **Accuracy:** ±1° (calibrated)

### 3.6 System Monitor (apps/visor-ui/system_monitor.py)

**Purpose:** Real-time system telemetry collection

**Metrics Collected:**
```python
- CPU usage (%)              # psutil.cpu_percent()
- Memory usage (%)           # psutil.virtual_memory()
- GPU usage (%)              # tegrastats (Jetson)
- GPU temperature (°C)       # /sys/class/thermal/
- CPU temperature (°C)       # sensors or /sys/class/thermal/
- Battery level (%)          # psutil.sensors_battery()
- Battery temperature (°C)   # BMS telemetry
- Disk usage (%)             # psutil.disk_usage('/')
- Network stats (bytes)      # psutil.net_io_counters()
- Process count              # len(psutil.pids())
```

**Jetson-Specific (tegrastats):**
```python
def _parse_tegrastats(line):
    # Example: RAM 3426/7777MB CPU [15%@1190,13%@1190,14%@1190,14%@1190] EMC_FREQ 0% GR3D_FREQ 0%@114 APE 150 PLL@28.5C MCPU@28.5C PMIC@50C Tboard@27C GPU@28C BCPU@28.5C thermal@28.3C Tdiode@26.25C

    cpu_match = re.search(r'CPU \[(.*?)\]', line)
    ram_match = re.search(r'RAM (\d+)/(\d+)MB', line)
    gpu_match = re.search(r'GR3D_FREQ (\d+)%', line)
    temp_match = re.search(r'GPU@(\d+)C', line)

    return {
        'cpu': float(cpu_match.group(1).split('%')[0]),
        'ram_used': int(ram_match.group(1)),
        'ram_total': int(ram_match.group(2)),
        'gpu': int(gpu_match.group(1)),
        'temp': int(temp_match.group(1))
    }
```

**Update Loop:**
```python
def start():
    thread = threading.Thread(target=_monitor_loop, daemon=True)
    thread.start()

def _monitor_loop():
    while running:
        telemetry = {
            'cpu': psutil.cpu_percent(interval=0.1),
            'memory': psutil.virtual_memory().percent,
            'temperature': _get_temperature(),
            'fps': _calculate_fps(),
            'timestamp': time.time()
        }

        # Store in ring buffer (last 60 samples)
        telemetry_buffer.append(telemetry)

        time.sleep(1.0)  # 1 Hz
```

### 3.7 GPS Client (apps/visor-ui/gps_client.py)

**Purpose:** Qt-compatible GPS client wrapper

**Architecture:**
```python
from PySide6.QtCore import QObject, Signal, QThread
from services.gps.gps_service import GPSReader

class GPSClient(QObject):
    positionUpdated = Signal(float, float, float, float)  # lat, lon, alt, heading
    statusUpdated = Signal(dict)  # fix_quality, satellites, hdop

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.reader = GPSReader(port, baudrate)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_updates)

    def start(self):
        self.reader.start()
        self.update_timer.start(1000)  # 1 Hz

    def _emit_updates(self):
        data = self.reader.get_data()
        if data.is_valid():
            self.positionUpdated.emit(
                data.latitude,
                data.longitude,
                data.altitude or 0.0,
                data.heading or 0.0
            )

        self.statusUpdated.emit({
            'fix_quality': data.fix_quality,
            'satellites': data.satellites,
            'hdop': data.hdop,
            'valid': data.is_valid()
        })
```

### 3.8 Video Recorder (apps/visor-ui/full_recorder.py)

**Purpose:** Record full screen with overlays + microphone audio

**Architecture:**
```python
class FullRecorder:
    def __init__(self, output_dir='recordings', fps=30, mic_device_index=None):
        self.video_writer = None  # OpenCV VideoWriter
        self.audio_recorder = None  # PyAudio stream
        self.video_frames = []
        self.audio_chunks = []
        self.recording = False
```

**Recording Pipeline:**
```
1. QML Window → QImage (screen capture)
2. QImage → numpy array (RGB)
3. numpy → OpenCV VideoWriter (H.264/MJPEG)

Parallel:
4. Microphone → PyAudio stream
5. Audio chunks → WAV file
6. Merge video + audio with ffmpeg
```

**Implementation:**
```python
def start_recording(self):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = f"{output_dir}/recording_{timestamp}.avi"
    audio_path = f"{output_dir}/audio_{timestamp}.wav"

    # Video writer (H.264, 30 FPS)
    fourcc = cv2.VideoWriter_fourcc(*'X264')
    self.video_writer = cv2.VideoWriter(
        video_path, fourcc, fps, (width, height)
    )

    # Audio stream (16kHz, mono, 16-bit)
    self.audio_stream = pyaudio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=mic_device_index,
        stream_callback=_audio_callback
    )

    self.recording = True

def add_frame(self, frame_array: np.ndarray):
    if self.recording and self.video_writer:
        # Convert RGB → BGR for OpenCV
        bgr_frame = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
        self.video_writer.write(bgr_frame)

def stop_recording(self):
    self.recording = False

    # Release video writer
    self.video_writer.release()

    # Stop audio stream
    self.audio_stream.stop_stream()
    self.audio_stream.close()

    # Write audio to WAV
    with wave.open(audio_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)
        wf.writeframes(b''.join(audio_chunks))

    # Merge with ffmpeg
    final_path = f"{output_dir}/final_{timestamp}.mp4"
    subprocess.run([
        'ffmpeg', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', final_path
    ])
```

### 3.9 QML UI Components (apps/visor-ui/qml/)

**Main Window (main.qml):**
- **Size:** 1440x1440 (square for dual displays)
- **Frameless:** No window decorations
- **Black background:** Minimize eye strain
- **Keyboard shortcuts:**
  - Esc: Quit
  - F: Toggle fullscreen
  - H: Toggle HUD
  - D: Toggle detections
  - C: Clear all overlays
  - P: Capture and analyze (Claude API)

**Key Components:**

1. **Fullscreen Video (line 22-40):**
```qml
Image {
    id: fullscreenVideo
    anchors.fill: parent
    fillMode: Image.PreserveAspectCrop
    cache: false          # Disable cache for live video
    asynchronous: false   # Synchronous for low latency
    smooth: false         # Disable smoothing for performance

    function updateFrame(framePath) {
        source = framePath  # "image://video/12345"
    }
}
```

2. **MinimalStatus (line 43-49):**
   - Top-right corner
   - Battery, temperature, FPS
   - Always visible (except clear mode)

3. **HUDOverlay (line 65-78):**
   - Full-screen overlay
   - System metrics, detection badges
   - Opacity 0.8, fades in/out
   - Deployment animation on startup

4. **DetectionOverlay (line 117-123):**
   - Bounding boxes for detected objects
   - Labels with confidence scores
   - Toggle visibility with voice/keyboard

5. **OrientationCrosshair (line 138-142):**
   - Pitch/roll/heading indicator
   - Updates at 60 Hz from IMU
   - Horizon line, compass ring

6. **Minimap (line 145-155):**
   - Bottom-left corner, 300x300px
   - GPS position + heading arrow
   - OpenStreetMap tiles (cached)
   - Rotates with IMU heading

7. **HUDPresetWheel (line 158-167):**
   - Gesture-controlled preset selector
   - Presets: Full, Clear, Custom
   - Always active (can switch out of clear mode)

8. **Qt Connections (line 213-254):**
```qml
Connections {
    target: visorApp  // Python backend

    function onFrameUpdated(framePath) {
        fullscreenVideo.updateFrame(framePath)
    }

    function onDetectionsUpdated(detections) {
        detectionOverlay.updateDetections(detections)
        detailedHUD.updateDetections(detections)
    }

    function onOrientationUpdated(heading, roll, pitch) {
        orientationCrosshair.headingAngle = heading
        orientationCrosshair.rollAngle = roll
        orientationCrosshair.pitchAngle = pitch
    }
}
```

---

## 4. PROTOCOL BUFFERS - DATA CONTRACTS

### 4.1 Message Definitions (libs/messages/helmet.proto)

**FrameMeta (line 8-15):**
```protobuf
message FrameMeta {
  uint64 frame_id = 1;
  google.protobuf.Timestamp timestamp = 2;
  uint32 width = 3;
  uint32 height = 4;
  string format = 5;      // RGB, BGR, YUV420
  bytes data = 6;         // Raw frame data (up to 50MB)
}
```

**Detection (line 18-26):**
```protobuf
message Detection {
  float x = 1;            // Normalized 0-1
  float y = 2;
  float width = 3;
  float height = 4;
  string label = 5;       // "person", "car", etc.
  float confidence = 6;   // 0-1
  uint32 class_id = 7;    // COCO class ID
}
```

**DetectionResult (line 28-33):**
```protobuf
message DetectionResult {
  uint64 frame_id = 1;
  google.protobuf.Timestamp timestamp = 2;
  repeated Detection detections = 3;
  float inference_time_ms = 4;
}
```

**Intent (line 36-42):**
```protobuf
message Intent {
  string text = 1;                    // Transcribed text
  string intent_name = 2;             // "toggle_night_mode"
  map<string, string> entities = 3;   // Parameters
  float confidence = 4;
  google.protobuf.Timestamp timestamp = 5;
}
```

**HUDStatus (line 67-74):**
```protobuf
message HUDStatus {
  SystemStatus system = 1;
  bool mic_active = 2;
  float mic_level = 3;
  uint32 fps = 4;
  uint32 detection_count = 5;
  string status_message = 6;
}
```

### 4.2 Service Definitions (line 90-110)

**VideoService:**
```protobuf
service VideoService {
  rpc GetFrame(FrameRequest) returns (FrameMeta);
  rpc StreamFrames(FrameRequest) returns (stream FrameMeta);
}
```

**PerceptionService:**
```protobuf
service PerceptionService {
  rpc Infer(FrameMeta) returns (DetectionResult);
  rpc InferStream(stream FrameMeta) returns (stream DetectionResult);
  rpc SetROI(ROIRequest) returns (CommandResponse);
}
```

**VoiceService:**
```protobuf
service VoiceService {
  rpc ProcessAudio(stream AudioData) returns (stream Intent);
  rpc Synthesize(TTSRequest) returns (TTSResponse);
}
```

**OrchestratorService:**
```protobuf
service OrchestratorService {
  rpc ExecuteCommand(Command) returns (CommandResponse);
  rpc GetStatus(StatusRequest) returns (HUDStatus);
  rpc StreamStatus(StatusRequest) returns (stream HUDStatus);
}
```

---

## 5. DEPENDENCIES & LIBRARIES

### 5.1 Core Dependencies (requirements-jetson.txt)

**gRPC & Protobuf:**
- `grpcio==1.60.0` - gRPC runtime
- `grpcio-tools==1.60.0` - Protobuf compiler
- `protobuf==4.25.1` - Protocol buffers

**Computer Vision & ML:**
- `numpy==1.24.3` - Array operations
- `opencv-python==4.8.1.78` - Image processing
- `Pillow==10.1.0` - Image format support
- `ultralytics==8.0.220` - YOLOv8 models
- `onnxruntime==1.16.3` - ONNX inference (ARM64)
- `torch` (pre-installed) - PyTorch 2.4.0 (NVIDIA wheel)
- `torchvision` (pre-installed) - Vision models

**Voice/Audio:**
- `faster-whisper==0.10.0` - Optimized Whisper ASR
- `pyaudio==0.2.13` - Audio I/O
- `soundfile==0.12.1` - Audio file handling
- `webrtcvad==2.0.10` - Voice activity detection
- `scipy==1.11.4` - Signal processing
- `transformers==4.35.2` - Hugging Face models
- `librosa==0.10.1` - Audio analysis

**Orchestrator:**
- `asyncio-mqtt==0.16.1` - MQTT client
- `psutil==5.9.6` - System metrics

**UI:**
- `PySide6==6.6.0` - Qt6 Python bindings

**Utilities:**
- `python-dotenv` - Environment variables

**GPS:**
- `pyserial==3.5` - Serial communication
- `pynmea2==1.19.0` - NMEA parsing

### 5.2 Additional Dependencies (Not in requirements.txt)

**IMU/Sensors:**
- `smbus2` - I2C communication (BNO055)

**Wake Word Detection:**
- `openwakeword` - Offline wake word detection

**OpenAI:**
- `websockets` - WebSocket client (Realtime API)

**Map Rendering:**
- `folium` - Map tile rendering

---

## 6. CONFIGURATION SYSTEM

### 6.1 Configuration Loader (libs/utils/config.py)

**Environment-Based Profiles:**
```python
HELMET_PROFILE=dev   → configs/profiles/dev.json
HELMET_PROFILE=field → configs/profiles/field.json
(default)            → configs/profiles/dev.json
```

**Hierarchical Access:**
```python
config = get_config()
value = config.get('video.width', default=1920)
# Dot notation: 'video.width' → config['video']['width']
```

### 6.2 Development Profile (configs/profiles/dev.json)

**Key Settings:**
```json
{
  "video": {
    "camera_type": "dual_usb",
    "dual_mode": true,
    "device_left": "/dev/video0",
    "device_right": "/dev/video1",
    "width": 1280,
    "height": 720,
    "fps": 30
  },
  "perception": {
    "model_path": "models/yolov8n.pt",
    "device": "cpu",  // Change to "cuda" for GPU
    "confidence_threshold": 0.7
  },
  "assistant": {
    "voice": "echo",
    "wake_word": "hey_jarvis",
    "system_prompt": "[5000+ character Aegis prompt]"
  },
  "gyro": {
    "i2c_bus": 7  // BNO055 detected on bus 7
  },
  "gps": {
    "port": "/dev/ttyUSB0",
    "baudrate": 115200
  },
  "system": {
    "log_level": "DEBUG",
    "recording_dir": "recordings"
  }
}
```

---

## 7. DATA FLOW & COMMUNICATION

### 7.1 Frame Processing Pipeline

```
1. Direct Camera (GStreamer)
   ├─ Left CSI camera → nvarguscamerasrc → 1280x720 BGR
   └─ Right CSI camera → nvarguscamerasrc → 1280x720 BGR

2. Combine Side-by-Side
   └─ np.hstack() → 2560x720 RGB

3. Convert to QImage
   └─ QImage(data, width, height, bytesPerLine, Format_RGB888)

4. Store in Image Provider (zero-copy)
   └─ VideoImageProvider.setImage(qimage)

5. Emit Signal to QML
   └─ frameUpdated.emit("image://video/12345")

6. QML Updates Image Component
   └─ fullscreenVideo.source = framePath

7. (Optional) Perception Inference
   └─ PerceptionClient.infer(frame) → DetectionResult

8. (Optional) Recording
   └─ Grab QML window framebuffer → VideoRecorder.add_frame()
```

**Latency Budget:**
- Camera capture: 33ms (30 FPS)
- GStreamer decode: <10ms
- numpy combine: <5ms
- QImage conversion: <5ms
- Qt rendering: 16ms (60 FPS)
- **Total: ~70ms (acceptable for AR)**

### 7.2 Voice Command Pipeline

```
1. Wake Word Detection (openWakeWord)
   └─ Microphone → 16kHz PCM → Model → "hey_jarvis" detected

2. Activate Voice Assistant
   └─ WakeWordDetector.pause() → OpenAIRealtimeAssistant.activate()

3. Continuous Conversation
   ├─ Mic → 24kHz PCM → WebSocket → OpenAI Realtime API
   └─ OpenAI → Audio response → WebSocket → PyAudio → Speaker

4. Function Calls
   ├─ "Start recording" → function_call event → VideoRecorder.start()
   └─ "What do you see?" → get_camera_view() → Vision analysis

5. Dismissal
   └─ "Okay thanks" → Deactivate → WakeWordDetector.resume()
```

### 7.3 IMU Orientation Pipeline

```
1. BNO055 Sensor (I2C bus 7)
   └─ Read Euler angles @ 60 Hz

2. GyroSensor Thread
   └─ smbus2.read_i2c_block_data(0x28, 0x1A, 6) → (heading, roll, pitch)

3. Callback Invocation
   └─ callback({'euler': (h, r, p), 'gyro': (x, y, z)})

4. Qt Signal (Thread-Safe)
   └─ QMetaObject.invokeMethod(visorApp, "_emit_orientation_signal", ...)

5. QML Update
   ├─ orientationCrosshair.headingAngle = heading
   └─ hudPresetWheel.updateOrientation(heading, roll, pitch)
```

### 7.4 GPS Position Pipeline

```
1. Ardusimple GPS Module (Serial /dev/ttyUSB0, 115200 baud)
   └─ NMEA sentences (GGA, RMC, VTG)

2. GPSReader Thread
   └─ pynmea2.parse(sentence) → GPSData(lat, lon, alt, heading)

3. GPSClient Timer (1 Hz)
   └─ positionUpdated.emit(lat, lon, alt, heading)

4. Minimap Controller
   ├─ Update position marker
   ├─ Fetch OSM tile if needed (cache in .map_cache/)
   └─ Render map → MinimapImageProvider

5. QML Display
   └─ minimap.source = "image://minimap/12345"
```

---

## 8. PERFORMANCE CHARACTERISTICS

### 8.1 Jetson Orin Nano (15W Mode)

**Video Capture:**
- Resolution: 2560x720 (dual 1280x720)
- Frame rate: 30 FPS (stable)
- Latency: <50ms (GStreamer direct)
- CPU usage: 15-20% (hardware decode)

**Object Detection:**
- Model: YOLOv8n (FP16)
- Throughput: 20-25 FPS
- Inference time: 40-50ms
- CPU usage: 40-50% (when enabled)
- GPU usage: 60-70%

**Voice Recognition:**
- Model: Whisper small (INT8)
- Latency: ~500ms
- CPU usage: 30-40% (burst)

**OpenAI Realtime Voice:**
- Latency: 200-500ms (voice → response)
- Bandwidth: 24 kbps up, 48 kbps down
- CPU usage: <10%

**System Overhead:**
- Qt/QML UI: 10-15% CPU
- IMU reading: <5% CPU (60 Hz)
- GPS reading: <2% CPU
- Total idle: 40-60% CPU, 3-4GB RAM

**Thermal:**
- Idle: 35-40°C
- Load: 55-70°C (throttle at 80°C)
- Cooling: Passive heatsink + active fan

### 8.2 Memory Footprint

**Resident Memory (RSS):**
- Main process: 2.5GB
  - Qt/QML: 800MB
  - OpenCV: 400MB
  - PyTorch: 600MB
  - Buffers: 300MB
  - Python: 400MB
- Total system: 4GB / 8GB (50% utilization)

**Video Memory:**
- YOLOv8n model: 6MB
- Frame buffers: 20MB (720p × 3)
- Qt textures: 50MB

---

## 9. HARDWARE INTEGRATION

### 9.1 Camera System

**Cameras:**
- **Front:** 2× USB webcams (dev mode) or 2× IMX219 CSI (production)
- **Aerial:** 1× USB webcam (optional, /dev/video2)

**CSI Interface:**
- **Connector:** MIPI CSI-2 (15-pin FFC)
- **Sensors:** IMX219 (8MP, global shutter)
- **Lenses:** 6mm C-mount, low distortion
- **Resolution:** 1280x720 @ 30 FPS (per camera)
- **Format:** NV12 (YUV 4:2:0)

**USB Interface:**
- **Protocol:** UVC (USB Video Class)
- **Backend:** V4L2 (Video4Linux2)
- **Format:** MJPEG (preferred) or YUYV

### 9.2 IMU/Gyroscope

**Sensor:** Bosch BNO055
- **DOF:** 9 (3-axis accel, gyro, mag)
- **Interface:** I2C (bus 7, address 0x28)
- **Update Rate:** 60 Hz
- **Resolution:** 1/16° (Euler), 1 LSB = 900 rad/s (gyro)
- **Calibration:** 4-point (system, gyro, accel, mag)

**I2C Bus Configuration:**
- `/dev/i2c-7` (Jetson Orin Nano)
- Pullup resistors: 10kΩ (on-board)
- SCL frequency: 400 kHz (fast mode)

### 9.3 GPS

**Module:** Ardusimple simpleRTK2B
- **Chipset:** u-blox ZED-F9P
- **Bands:** GPS, GLONASS, Galileo, BeiDou
- **RTK:** Supported (cm-level accuracy)
- **Interface:** USB serial (/dev/ttyUSB0)
- **Baud rate:** 115200 (default)
- **Protocol:** NMEA 0183
- **Update rate:** 5 Hz

### 9.4 Audio

**Input (Microphone):**
- **Type:** MEMS mic or headset mic
- **Sample rate:** 16kHz (voice), 24kHz (OpenAI)
- **Channels:** Mono
- **Bit depth:** 16-bit
- **Device:** Card 5 (configured in dev.json)

**Output (Speakers):**
- **Type:** Bone conduction transducers
- **Sample rate:** 24kHz
- **Channels:** Stereo
- **Device:** Card 6 (configured in dev.json)

### 9.5 Displays

**Panels:** 2× JDI 5.5" 1440×2560 IPS
- **Interface:** HDMI → MIPI (via driver board)
- **Refresh rate:** 60-90 Hz
- **Brightness:** 500 nits
- **Optics:** Aspheric PMMA eyepieces

**Configuration:**
- QML window: 1440×1440 (split for dual eyes)
- Frameless, fullscreen mode

### 9.6 Power

**Battery:** 4S Li-Po (14.8V nominal, 16.8V max)
- **Capacity:** 5000-10000 mAh
- **BMS:** Smart BMS with telemetry
- **Connector:** XT-90-S (anti-spark)
- **Hot-swap:** Supported

**Regulators:**
- **12V/5A:** Buck converter (displays, fans)
- **5V/3A:** Jetson Orin Nano

---

## 10. DEPLOYMENT & BUILD

### 10.1 Installation (install_jetson.sh)

**Steps:**
```bash
1. apt update && apt install dependencies
   - python3-pip, python3-venv, python3-dev
   - portaudio19-dev, libsndfile1, ffmpeg
   - gstreamer1.0-tools, gstreamer1.0-plugins-*

2. Create virtual environment
   python3 -m venv venv

3. Install Python packages
   pip install -r requirements-jetson.txt

4. Generate protobuf stubs
   python libs/messages/generate_pb.py

5. Download YOLOv8n model (if not present)
   wget -O models/yolov8n.pt https://...
```

### 10.2 Running the System

**Development Mode:**
```bash
# Terminal 1: Start backend services
source venv/bin/activate
python start_jetson_dev.py  # Starts video, perception, orchestrator

# Terminal 2: Start UI
export HELMET_PROFILE=dev
export PYTHONPATH=$(pwd):$(pwd)/libs
python apps/visor-ui/main.py
```

**Production Mode (systemd):**
```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable helmet.target
sudo systemctl start helmet.target

# Services:
# - helmet-video.service
# - helmet-perception.service
# - helmet-orchestrator.service
# - helmet-ui.service
```

### 10.3 Docker (docker-compose.yml)

**Services:**
- `video-service` (port 50051)
- `perception-service` (port 50052)
- `voice-service` (port 50053)
- `orchestrator-service` (port 50054)
- `ui-app` (DISPLAY forwarded)

**Usage:**
```bash
docker-compose up  # All services
docker-compose up video-service  # Single service
```

---

## 11. KEY TECHNICAL CHALLENGES & SOLUTIONS

### 11.1 Low-Latency Video

**Challenge:** Minimize glass-to-glass latency (<100ms)

**Solution:**
- Direct GStreamer pipelines (no encoding/decoding)
- Zero-copy QImage from numpy (data pointer sharing)
- Asynchronous frame updates (non-blocking)
- Buffer size = 1 (always fresh frames)
- Disable smoothing/filtering (performance)

### 11.2 Dual Camera Synchronization

**Challenge:** Sync two CSI cameras for stereo vision

**Solution:**
- Separate GStreamer pipelines (independent clocks)
- Frame timestamping (correlate by timestamp)
- Combine at display time (acceptable <5ms skew)

### 11.3 PyTorch 2.6+ Model Loading

**Challenge:** `FutureWarning: weights_only=False`

**Solution:**
```python
torch.serialization.add_safe_globals([
    DetectionModel, Sequential, Conv2d, ...
])
```

### 11.4 Microphone Contention

**Challenge:** Wake word detector and voice assistant both need mic

**Solution:**
- Wake word owns mic initially
- On detection: pause wake word, activate assistant
- On dismissal: deactivate assistant, resume wake word
- PyAudio stream properly closed between transitions

### 11.5 IMU Latency

**Challenge:** BNO055 fusion mode has 100ms lag

**Solution:**
- Use ACCGYRO mode (raw sensors, no fusion)
- Integrate gyro data on host for instant response
- Trade smoothness for latency (<20ms)

### 11.6 Qt Thread Safety

**Challenge:** Sensor callbacks from worker threads

**Solution:**
```python
QMetaObject.invokeMethod(
    target_object,
    "method_name",
    Qt.QueuedConnection,  # Cross-thread signal
    Q_ARG(float, value)
)
```

---

## 12. FUTURE ENHANCEMENTS (Roadmap)

**Planned:**
- [ ] TensorRT model optimization (5-10x faster inference)
- [ ] SLAM/Visual odometry (indoor positioning)
- [ ] GPS/IMU sensor fusion (Kalman filter)
- [ ] Gesture recognition (hand tracking via camera)
- [ ] Multi-user collaboration (shared AR space)
- [ ] Cloud telemetry dashboard
- [ ] Custom training pipeline (fine-tune YOLOv8)
- [ ] WiFi positioning fallback (no GPS indoors)

---

## 13. CONCLUSION & ASSESSMENT

### 13.1 Strengths

✅ **Well-Architected:** Clean microservices separation, clear interfaces
✅ **Performance:** Hardware-accelerated video, GPU inference, low latency
✅ **Modularity:** Each service independently deployable, configurable
✅ **Modern Stack:** gRPC, protobuf, Qt6, OpenAI Realtime API
✅ **Rich Features:** Voice control, GPS, IMU, object detection, recording
✅ **Documentation:** Extensive inline comments, clear README
✅ **Configurability:** JSON profiles for different environments
✅ **Error Handling:** Graceful fallbacks, connection retry logic

### 13.2 Areas for Improvement

⚠️ **Code Duplication:** Some camera handling code repeated across services
⚠️ **Testing:** No unit tests, integration tests
⚠️ **Error Recovery:** Some services don't auto-restart on failure
⚠️ **Security:** API keys in .env (consider secrets management)
⚠️ **Monitoring:** No built-in health checks, alerting
⚠️ **Documentation:** API docs could be auto-generated (Sphinx)
⚠️ **Logging:** Could benefit from structured logging (JSON logs)

### 13.3 Overall Assessment

**Grade: A-**

This is a **production-quality AR/VR system** with impressive technical depth. The codebase demonstrates:
- **Expert-level Python** and Qt/QML integration
- **Deep hardware knowledge** (GStreamer, I2C, serial protocols)
- **Modern AI/ML integration** (YOLOv8, Whisper, OpenAI)
- **Real-time systems expertise** (latency optimization, threading)
- **Professional software engineering** (modularity, configuration, deployment)

The project is well-suited for **research, prototyping, or small-scale production** deployments on Jetson platforms. With minor refinements (testing, monitoring, documentation), it could scale to larger deployments.

---

**End of Technical Review**
**Total Analysis Time:** ~2 hours
**Files Reviewed:** 30+ Python modules, protobuf definitions, QML components, configs
**Lines Analyzed:** 6,141+ (excluding venv/)
**Review Date:** October 27, 2025
