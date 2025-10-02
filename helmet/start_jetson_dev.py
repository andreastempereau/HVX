#!/usr/bin/env python3
"""
Jetson development startup script
Runs all backend services directly on Jetson for development
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
            print(f"Stopping {process.args[1]}...")
            process.terminate()

    # Wait for processes to terminate
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"Force killing {process.args[1]}...")
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

def check_gpu():
    """Check if GPU is available"""
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ NVIDIA GPU detected")
            return True
        else:
            print("✗ NVIDIA GPU not detected")
            return False
    except FileNotFoundError:
        print("✗ nvidia-smi not found")
        return False

def check_camera():
    """Check if camera is available"""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✓ Camera working: {frame.shape}")
                cap.release()
                return True
            else:
                print("✗ Camera detected but no frames")
                cap.release()
                return False
        else:
            print("✗ No camera detected")
            return False
    except Exception as e:
        print(f"✗ Camera test failed: {e}")
        return False

def main():
    """Main startup function"""
    print("=" * 60)
    print("Starting Helmet OS (Jetson Development Mode)")
    print("=" * 60)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set environment FIRST before any imports
    os.environ['HELMET_PROFILE'] = 'dev'
    os.environ['TORCH_WEIGHTS_ONLY'] = 'False'  # Allow ultralytics model loading with PyTorch 2.6+
    current_dir = str(Path(__file__).parent)
    libs_dir = str(Path(__file__).parent / "libs")

    # Set PYTHONPATH to include both helmet root and libs directory
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] = f"{current_dir}:{libs_dir}:{os.environ['PYTHONPATH']}"
    else:
        os.environ['PYTHONPATH'] = f"{current_dir}:{libs_dir}"

    # Also add to sys.path so imports work in this script
    sys.path.insert(0, libs_dir)
    sys.path.insert(0, current_dir)

    print(f"\nEnvironment:")
    print(f"  Profile: {os.environ['HELMET_PROFILE']}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Working Dir: {current_dir}")

    # System checks
    print("\nSystem Checks:")
    check_gpu()
    check_camera()

    # Check Python dependencies
    print("\nChecking dependencies...")
    missing_deps = []
    try:
        import cv2
        print("✓ opencv-python")
    except ImportError:
        print("✗ opencv-python")
        missing_deps.append("opencv-python")

    try:
        import grpc
        print("✓ grpcio")
    except ImportError:
        print("✗ grpcio")
        missing_deps.append("grpcio")

    try:
        import numpy
        print("✓ numpy")
    except ImportError:
        print("✗ numpy")
        missing_deps.append("numpy")

    try:
        from messages import helmet_pb2
        print("✓ protobuf messages")
    except ImportError:
        print("✗ protobuf messages (run: cd libs/messages && python generate_pb.py)")
        missing_deps.append("protobuf-messages")

    if missing_deps:
        print("\n⚠ Missing dependencies detected")
        print("Install with:")
        print("  sudo apt-get install python3-pip python3-venv")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r libs/messages/requirements.txt")
        print("  pip install -r services/video/requirements.txt")
        print("  pip install -r services/perception/requirements.txt")
        print("  pip install -r services/voice/requirements.txt")
        print("  pip install -r services/orchestrator/requirements.txt")
        print("\nContinuing anyway (services may fail)...")
        time.sleep(2)

    # Start services in order
    services = [
        ("Orchestrator", "services/orchestrator/orchestrator_service.py", 0),
        ("Video Service", "services/video/video_service.py", 2),
        ("Perception Service", "services/perception/perception_service.py", 4),
        ("Voice Service", "services/voice/voice_service.py", 6),
    ]

    print("\n" + "=" * 60)
    print("Starting Services...")
    print("=" * 60)

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

    print("\n" + "=" * 60)
    print("Service Status:")
    print("=" * 60)
    for i, (name, _, _) in enumerate(services):
        if i < len(processes) and processes[i].poll() is None:
            print(f"  ✓ {name}: Running (PID: {processes[i].pid})")
        else:
            print(f"  ✗ {name}: Not running")

    print("\n" + "=" * 60)
    print("Service Endpoints:")
    print("=" * 60)
    print("  Orchestrator:  localhost:50054")
    print("  Video:         localhost:50051")
    print("  Perception:    localhost:52052")
    print("  Voice:         localhost:50053")

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("To start the UI in another terminal:")
    print("  export HELMET_PROFILE=dev")
    print("  export PYTHONPATH=/home/hvx/HVX/helmet:/home/hvx/HVX/helmet/libs")
    print("  python apps/visor-ui/main.py")

    print("\nControls:")
    print("  Ctrl+C: Stop all services")
    print("=" * 60)

    # Keep running and monitor services
    try:
        while running:
            time.sleep(1)

            # Check if any service died
            for i, (name, script, _) in enumerate(services):
                if i < len(processes) and processes[i].poll() is not None:
                    print(f"\n⚠ {name} stopped unexpectedly (exit code: {processes[i].returncode})")

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()
