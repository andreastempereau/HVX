#!/bin/bash
# Helmet UI Startup Script
# Simple one-command startup for the visor UI

cd "$(dirname "$0")"

echo "============================================"
echo "Helmet Visor UI - Startup"
echo "============================================"

# Check for libxcb-cursor0
if ! dpkg -l | grep -q libxcb-cursor0; then
    echo "Installing missing X11 library (libxcb-cursor0)..."
    sudo apt-get update -qq
    sudo apt-get install -y libxcb-cursor0
fi

# Set up display environment
if [ -z "$DISPLAY" ]; then
    echo "Setting DISPLAY to :0"
    export DISPLAY=:0
else
    echo "Using existing DISPLAY: $DISPLAY"
fi

# Set Qt platform to X11 (xcb)
export QT_QPA_PLATFORM=xcb

# Set environment variables
export HELMET_PROFILE=dev
export PYTHONPATH=/home/hvx/HVX/helmet:/home/hvx/HVX/helmet/libs

# Setup virtual environment with system site packages (for PyGObject, GStreamer, etc.)
NEEDS_REINSTALL=false

if [ ! -d "venv" ]; then
    NEEDS_REINSTALL=true
elif [ ! -f "venv/pyvenv.cfg" ] || ! grep -q "include-system-site-packages = true" venv/pyvenv.cfg; then
    echo "Upgrading virtual environment to include system packages..."
    rm -rf venv
    NEEDS_REINSTALL=true
fi

if [ "$NEEDS_REINSTALL" = true ]; then
    echo "Creating virtual environment (with system packages access)..."
    python3 -m venv --system-site-packages venv

    echo "Installing dependencies from requirements-jetson.txt..."
    source venv/bin/activate
    pip3 install -q -r requirements-jetson.txt
    echo "✓ Base dependencies installed"
else
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check and install AR dependencies if needed
if ! python3 -c "import pyorbbecsdk" 2>/dev/null; then
    echo "Installing AR dependencies (pyorbbecsdk2)..."
    pip3 install -q pyorbbecsdk2
    echo "✓ AR dependencies installed"
fi

echo "Environment configured:"
echo "  DISPLAY: $DISPLAY"
echo "  QT_QPA_PLATFORM: $QT_QPA_PLATFORM"
echo "  HELMET_PROFILE: $HELMET_PROFILE"
echo "  Python: $(which python3)"
echo ""
echo "Starting Helmet Visor UI..."
echo "============================================"
echo ""

# Run the UI
python3 apps/visor-ui/main.py

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================"
    echo "UI exited with error code: $EXIT_CODE"
    echo "============================================"
fi

exit $EXIT_CODE
