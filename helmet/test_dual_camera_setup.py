#!/usr/bin/env python3
"""Test the new dual camera DirectCamera implementation"""

import sys
import time
from pathlib import Path

# Add apps to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "visor-ui"))

from direct_camera import DirectCamera
import cv2

def main():
    print("="*60)
    print("DUAL CAMERA DIRECTCAMERA TEST")
    print("="*60)

    # Initialize dual camera
    print("\nInitializing dual camera...")
    camera = DirectCamera(
        sensor_id=0,  # Not used in dual mode
        width=1280,
        height=720,
        fps=30,
        dual_mode=True,
        device_left='/dev/video2',
        device_right='/dev/video3'
    )

    # Start camera
    if not camera.start():
        print("❌ Failed to start dual camera!")
        return 1

    print("\n✅ Dual camera started successfully!")
    print("Waiting for frames...")
    time.sleep(2)  # Wait for camera to stabilize

    # Capture a few frames
    print("\nCapturing frames...")
    for i in range(5):
        frame = camera.get_frame()
        if frame is not None:
            print(f"  Frame {i+1}: {frame.shape}, dtype={frame.dtype}")

            # Save first frame
            if i == 0:
                output_path = '/tmp/dual_camera_merged.jpg'
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imwrite(output_path, frame_bgr)
                print(f"  Saved merged frame to: {output_path}")
        else:
            print(f"  Frame {i+1}: None")

        time.sleep(0.5)

    # Stop camera
    print("\nStopping camera...")
    camera.stop()

    print("\n✅ Test complete!")
    print(f"   Check the merged output at: /tmp/dual_camera_merged.jpg")
    return 0

if __name__ == "__main__":
    sys.exit(main())
