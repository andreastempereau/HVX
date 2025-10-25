#!/usr/bin/env python3
"""Test cameras with OpenCV to verify they work"""

import cv2
import sys

def test_camera(device_path):
    """Test a single camera with OpenCV"""
    # Extract device number from path
    device_num = int(device_path.split('video')[-1])

    print(f"\nTesting {device_path} (device {device_num})...")

    cap = cv2.VideoCapture(device_num, cv2.CAP_V4L2)

    if not cap.isOpened():
        print(f"  ❌ Failed to open {device_path}")
        return False

    # Try to read a frame
    ret, frame = cap.read()

    if not ret or frame is None:
        print(f"  ❌ Failed to read frame from {device_path}")
        cap.release()
        return False

    print(f"  ✅ {device_path} working!")
    print(f"     Resolution: {frame.shape[1]}x{frame.shape[0]}")
    print(f"     Format: {frame.shape}")

    # Try to set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Read another frame
    ret, frame = cap.read()
    if ret:
        print(f"     After setting 1280x720: {frame.shape[1]}x{frame.shape[0]}")

    cap.release()
    return True

def main():
    print("="*60)
    print("OPENCV CAMERA TEST")
    print("="*60)

    left_ok = test_camera('/dev/video2')
    right_ok = test_camera('/dev/video3')

    if left_ok and right_ok:
        print("\n✅ Both cameras working with OpenCV!")
        return 0
    else:
        print("\n❌ One or both cameras failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
