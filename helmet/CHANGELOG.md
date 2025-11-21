# Changelog

All notable changes to Helmet OS will be documented in this file.

## [2.0.0] - 2025-11-20

### 🎯 Major Architectural Changes

**Complete redesign from microservices to standalone AR interface**

- **Removed microservices architecture** - Deleted 2,934 lines of gRPC backend services
- **Single process application** - No more orchestrator, video, perception, voice, or GPS services
- **32% code reduction** - Simplified from 9,200 to 6,300 lines
- **Direct hardware access** - Camera, GPS, IMU, voice all integrated directly into UI
- **Zero IPC overhead** - Eliminated inter-process communication latency

### 🖥️ New AR Interface

- **Single 16:9 screen** - Changed from dual-eye VR (1440x1440 per eye) to unified 1920x1080 display
- **Simplified UI** - One set of widgets instead of duplicated left/right overlays
- **Black background** - Camera feed commented out for now (thermal overlay replaces it)
- **Auto-fullscreen** - Application starts in fullscreen mode automatically

### 🔥 Thermal Camera Integration

- **FLIR Boson support** - Added thermal imaging overlay (640x512 @ 30fps)
- **T key toggle** - Press T to show/hide thermal camera
- **N key calibration** - Press N to trigger NUC (removes artifacts)
- **Low latency** - Optimized capture with minimal buffering
- **Full-screen overlay** - Thermal replaces background, widgets stay on top

### ⚡ Simplified Startup

- **One command** - `./run_ui.sh` starts everything
- **No service management** - No need to start multiple processes
- **Auto-configuration** - Installs dependencies and configures environment
- **S key to quit** - Added quick exit shortcut

### 📦 Removed Components

- All gRPC services (orchestrator, video, perception, voice, GPS)
- Service client wrappers (video_client, perception_client, caption_client)
- gRPC protocol definitions (libs/messages/)
- Service deployment files (Docker, systemd units)
- Map cache (2000+ PNG tiles)
- Legacy YOLOv4 weights (45MB)

### 🔧 Technical Improvements

- **GPS** - Moved to local directory, direct serial access
- **Camera** - Already using direct GStreamer (no changes needed)
- **Voice** - OpenAI Realtime Assistant working standalone
- **Wake word** - OpenWakeWord integration maintained
- **Gyro/IMU** - BNO055 support retained
- **Recording** - Full video+audio recording functional

### 🎹 Updated Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **T** | Toggle thermal overlay |
| **N** | Trigger thermal NUC calibration |
| **S** / **Esc** | Quit application |
| **F** | Toggle fullscreen |
| **H** | Toggle HUD |
| **D** | Toggle detections |
| **C** | Clear overlays |
| **P** | Snapshot analyze |
| **Space** | Voice mode |

### 🚀 Performance

- **Lower latency** - No IPC overhead
- **Simpler debugging** - Single stack trace
- **Reduced memory** - One process instead of five
- **Faster startup** - No service orchestration

### ⚠️ Temporarily Disabled

- **Object detection** - Was using perception service (can re-add with direct YOLO)
- **Live captions** - Was using caption service (can re-add with direct Deepgram)

### 📝 Migration Notes

- Old `start_jetson_dev.py` no longer starts services (shows standalone mode message)
- Use `./run_ui.sh` for quick startup with auto-configuration
- All hardware interfaces remain functional
- Configuration files unchanged (dev.json, field.json)

---

## [1.3.0] - Previous Version

- GPS with WiFi positioning fallback
- Dual camera setup with VR interface
- Microservices architecture with 5 services
- Voice assistant and wake word detection
