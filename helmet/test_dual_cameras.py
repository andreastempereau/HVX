#!/usr/bin/env python3
"""Test dual camera setup with OpenCV"""

import cv2
import numpy as np

def test_camera(device_id):
    """Test a single camera"""
    print(f"\nTesting /dev/video{device_id}...")
    cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)

    if not cap.isOpened():
        print(f"  ❌ Failed to open /dev/video{device_id}")
        return None

    # Try to read a frame
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f"  ❌ Failed to read frame from /dev/video{device_id}")
        cap.release()
        return None

    print(f"  ✅ /dev/video{device_id} is working!")
    print(f"     Resolution: {frame.shape[1]}x{frame.shape[0]}")
    print(f"     Format: {frame.shape}")

    return cap

def main():
    print("="*60)
    print("DUAL CAMERA TEST")
    print("="*60)

    # Test both cameras
    cam0 = test_camera(0)
    cam1 = test_camera(1)

    if cam0 is None and cam1 is None:
        print("\n❌ No cameras working!")
        return 1

    # Create a merged view if both work
    if cam0 and cam1:
        print("\n✅ Both cameras working! Creating side-by-side view...")

        # Read frames from both
        ret0, frame0 = cam0.read()
        ret1, frame1 = cam1.read()

        if ret0 and ret1:
            # Resize to same height if needed
            h0, w0 = frame0.shape[:2]
            h1, w1 = frame1.shape[:2]

            target_height = min(h0, h1)
            frame0_resized = cv2.resize(frame0, (int(w0 * target_height / h0), target_height))
            frame1_resized = cv2.resize(frame1, (int(w1 * target_height / h1), target_height))

            # Concatenate side-by-side
            merged = np.hstack([frame0_resized, frame1_resized])

            print(f"   Merged view resolution: {merged.shape[1]}x{merged.shape[0]}")
            print(f"   Left camera: {frame0_resized.shape[1]}x{frame0_resized.shape[0]}")
            print(f"   Right camera: {frame1_resized.shape[1]}x{frame1_resized.shape[0]}")

            # Save sample
            cv2.imwrite('/tmp/dual_camera_test.jpg', merged)
            print(f"   Saved sample to /tmp/dual_camera_test.jpg")

    # Cleanup
    if cam0:
        cam0.release()
    if cam1:
        cam1.release()

    print("\n✅ Test complete!")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
