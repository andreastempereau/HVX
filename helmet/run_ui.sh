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

echo "Environment configured:"
echo "  DISPLAY: $DISPLAY"
echo "  QT_QPA_PLATFORM: $QT_QPA_PLATFORM"
echo "  HELMET_PROFILE: $HELMET_PROFILE"
echo ""
echo "Starting Helmet Visor UI..."
echo "============================================"
echo ""

# Run the UI
python apps/visor-ui/main.py

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "============================================"
    echo "UI exited with error code: $EXIT_CODE"
    echo "============================================"
fi

exit $EXIT_CODE
