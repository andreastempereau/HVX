#!/usr/bin/env python3
"""
Windows development startup script
Runs services directly on Windows for easier webcam access
"""

import subprocess
import sys
import time
import threading
import signal
import os
from pathlib import Path

# Service processes
processes = []
running = True

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\nShutting down services...")
    running = False

    for process in processes:
        if process.poll() is None:  # Still running
            print(f"Stopping {process.args[0]}...")
            process.terminate()

    # Wait for processes to terminate
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"Force killing {process.args[0]}...")
            process.kill()

    print("All services stopped")
    sys.exit(0)

def start_service(name, script_path, delay=0):
    """Start a Python service"""
    if delay > 0:
        time.sleep(delay)

    print(f"Starting {name}...")
    try:
        env = os.environ.copy()
        process = subprocess.Popen([
            sys.executable, script_path
        ], cwd=Path(__file__).parent, env=env)
        processes.append(process)
        print(f"{name} started (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"Failed to start {name}: {e}")
        return None

def main():
    """Main startup function"""
    print("Starting Helmet OS (Windows Development Mode)")
    print("=" * 50)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set environment
    os.environ['HELMET_PROFILE'] = 'dev'
    current_dir = str(Path(__file__).parent)
    libs_dir = str(Path(__file__).parent / "libs")

    # Set PYTHONPATH to include both helmet root and libs directory
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] = f"{current_dir};{libs_dir};{os.environ['PYTHONPATH']}"
    else:
        os.environ['PYTHONPATH'] = f"{current_dir};{libs_dir}"

    # Check Python dependencies
    print("Checking dependencies...")
    try:
        import cv2
        import grpc
        import numpy
        print("Core dependencies available")
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install: pip install opencv-python grpcio numpy")
        return

    # Test webcam access
    print("Testing webcam access...")
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"Webcam working: {frame.shape}")
            else:
                print("Webcam detected but no frames")
            cap.release()
        else:
            print("No webcam detected")
    except Exception as e:
        print(f"Webcam test failed: {e}")

    # Start services in order
    services = [
        ("Orchestrator", "services/orchestrator/orchestrator_service.py", 0),
        ("Video Service", "services/video/video_service.py", 2),
        ("Perception Service", "services/perception/perception_service.py", 4),
        ("Voice Service", "services/voice/voice_service.py", 6),
    ]

    # Start services in threads to handle delays
    threads = []
    for name, script, delay in services:
        thread = threading.Thread(
            target=start_service,
            args=(name, script, delay),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    # Wait for initial startup
    time.sleep(8)

    print("\nService Status:")
    for i, (name, _, _) in enumerate(services):
        if i < len(processes) and processes[i].poll() is None:
            print(f"  {name}: Running (PID: {processes[i].pid})")
        else:
            print(f"  {name}: Not running")

    print("\nService Endpoints:")
    print("  Orchestrator:  localhost:50054")
    print("  Video:         localhost:50051")
    print("  Perception:    localhost:50052")
    print("  Voice:         localhost:50053")

    print("\nControls:")
    print("  Ctrl+C: Stop all services")

    # UI startup instructions
    print("\nTo start the UI:")
    print("  python apps/visor-ui/main.py")

    # Keep running and monitor services
    try:
        while running:
            time.sleep(1)

            # Check if any service died
            for i, (name, script, _) in enumerate(services):
                if i < len(processes) and processes[i].poll() is not None:
                    print(f"{name} stopped unexpectedly")

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()