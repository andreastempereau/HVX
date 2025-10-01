# Helmet OS - AR/VR Vision System

A complete software stack for an AR helmet system with video capture, AI perception, voice control, and dual-eye display.

## Architecture

- **visor-ui**: Qt/QML compositor for dual-eye display with overlays
- **video**: GStreamer-based video capture and streaming
- **perception**: AI-powered object detection and image analysis
- **voice**: ASR/TTS voice assistant with intent recognition
- **orchestrator**: System coordination and state management

## Quick Start

### Development (with mocks)
```bash
docker compose up
```

### Production (Jetson)
```bash
sudo systemctl start visor.target
```

## Requirements

### Development
- Docker & Docker Compose
- Python 3.9+
- Qt6/PySide6 for UI development

### Production (Jetson Orin Nano)
- JetPack 6.x / Ubuntu 22.04
- GStreamer with NVMM support
- TensorRT 8.x
- CUDA 12.x

## Configuration

Profiles are stored in `configs/profiles/`:
- `dev.json` - Development with mocks
- `field.json` - Production deployment
- `demo.json` - Demo/testing mode