#!/bin/bash
# Quick install script for Jetson development environment

set -e

echo "============================================================"
echo "Helmet OS - Jetson Development Setup"
echo "============================================================"

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Warning: This doesn't appear to be a Jetson device"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install system dependencies
echo ""
echo "Step 1: Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    libportaudio2 \
    libsndfile1 \
    ffmpeg \
    meson \
    ninja-build

# Create virtual environment
echo ""
echo "Step 2: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages  # Use system packages for PyGObject
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo ""
echo "Step 3: Upgrading pip..."
pip install --upgrade pip

# Install core dependencies
echo ""
echo "Step 4: Installing core dependencies..."
pip install -r libs/messages/requirements.txt

# Generate protobuf files
echo ""
echo "Step 5: Generating protobuf files..."
cd libs/messages
python generate_pb.py
cd ../..

# Install service dependencies (with Jetson fixes)
echo ""
echo "Step 6: Installing service dependencies..."
pip install -r services/video/requirements.txt
pip install -r services/orchestrator/requirements.txt

# Install perception dependencies
echo ""
echo "Step 7: Installing perception dependencies..."
pip install -r services/perception/requirements.txt

# Install PyTorch for Jetson (if not already installed)
echo ""
echo "Step 8: Checking PyTorch..."
if python -c "import torch" 2>/dev/null; then
    echo "PyTorch already installed"
    python -c "import torch; print(f'PyTorch version: {torch.__version__}')"
else
    echo "Installing PyTorch for Jetson..."
    echo "This may take a while..."
    pip install --no-cache https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/torch-2.4.0-cp310-cp310-linux_aarch64.whl
fi

# Install voice dependencies
echo ""
echo "Step 9: Installing voice dependencies..."
# Install pyaudio with system portaudio
pip install pyaudio
pip install -r services/voice/requirements.txt || echo "Some voice dependencies failed (optional)"

# Install UI dependencies
echo ""
echo "Step 10: Installing UI dependencies..."
pip install -r apps/visor-ui/requirements.txt

# Test imports
echo ""
echo "Step 11: Testing imports..."
python3 << 'EOF'
import sys
errors = []

try:
    import grpc
    print("✓ grpcio")
except ImportError as e:
    errors.append(f"✗ grpcio: {e}")

try:
    import cv2
    print("✓ opencv-python")
except ImportError as e:
    errors.append(f"✗ opencv-python: {e}")

try:
    import numpy
    print("✓ numpy")
except ImportError as e:
    errors.append(f"✗ numpy: {e}")

try:
    from messages import helmet_pb2
    print("✓ protobuf messages")
except ImportError as e:
    errors.append(f"✗ protobuf messages: {e}")

try:
    from ultralytics import YOLO
    print("✓ ultralytics")
except ImportError as e:
    errors.append(f"✗ ultralytics: {e}")

try:
    from PySide6 import QtCore
    print("✓ PySide6")
except ImportError as e:
    errors.append(f"✗ PySide6: {e}")

try:
    import gi
    print("✓ PyGObject (system)")
except ImportError as e:
    errors.append(f"✗ PyGObject: {e}")

if errors:
    print("\nErrors found:")
    for err in errors:
        print(f"  {err}")
    sys.exit(1)
else:
    print("\n✓ All core dependencies installed successfully!")
EOF

echo ""
echo "============================================================"
echo "Installation Complete!"
echo "============================================================"
echo ""
echo "To start the backend services:"
echo "  python start_jetson_dev.py"
echo ""
echo "To start the UI (in another terminal):"
echo "  source venv/bin/activate"
echo "  export HELMET_PROFILE=dev"
echo "  export PYTHONPATH=$(pwd):$(pwd)/libs"
echo "  python apps/visor-ui/main.py"
echo ""
echo "============================================================"
