#!/usr/bin/env python3
"""Test webcam functionality on Windows"""

import cv2
import platform
import sys
from pathlib import Path

# Add libs to path
sys.path.append(str(Path(__file__).parent / "libs"))
from utils.config import get_config

def test_webcam():
    """Test webcam connection and display feed"""
    print(f"Testing webcam on {platform.system()}...")

    # Load configuration
    config = get_config()
    camera_id = config.get('video.camera_id', 0)

    print(f"Attempting to connect to camera ID: {camera_id}")

    # Try DirectShow on Windows for better compatibility
    if platform.system() == 'Windows':
        cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        print("❌ Failed to open webcam")

        # Try other camera IDs
        for test_id in [1, 2, 3]:
            print(f"Trying camera ID {test_id}...")
            if platform.system() == 'Windows':
                test_cap = cv2.VideoCapture(test_id, cv2.CAP_DSHOW)
            else:
                test_cap = cv2.VideoCapture(test_id)

            if test_cap.isOpened():
                print(f"✅ Found camera at ID {test_id}")
                cap = test_cap
                break
            test_cap.release()
        else:
            print("❌ No cameras found")
            return False

    # Get camera properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"✅ Webcam connected successfully!")
    print(f"   Resolution: {int(width)}x{int(height)}")
    print(f"   FPS: {fps}")

    # Try to set properties
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
        print("✅ Camera properties set")
    except Exception as e:
        print(f"⚠️  Could not set camera properties: {e}")

    # Test frame capture
    print("\nTesting frame capture...")
    for i in range(5):
        ret, frame = cap.read()
        if ret:
            print(f"✅ Frame {i+1}: {frame.shape}")
        else:
            print(f"❌ Failed to capture frame {i+1}")
            break

    # Show live feed
    print("\nPress 'q' to quit, 's' to save a test frame")
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to read frame")
                break

            frame_count += 1

            # Add frame info overlay
            cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'q' to quit, 's' to save", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

            cv2.imshow('Helmet Webcam Test', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"test_frame_{frame_count}.jpg"
                cv2.imwrite(filename, frame)
                print(f"✅ Saved frame to {filename}")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Webcam test completed")

    return True

def list_cameras():
    """List available cameras"""
    print("Available cameras:")

    for i in range(10):  # Check first 10 camera indices
        if platform.system() == 'Windows':
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(i)

        if cap.isOpened():
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"  Camera {i}: {int(width)}x{int(height)}")
            cap.release()

if __name__ == "__main__":
    print("🎥 Helmet OS Webcam Test")
    print("=" * 40)

    list_cameras()
    print()
    test_webcam()