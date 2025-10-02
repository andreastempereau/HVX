#!/usr/bin/env python3
"""Quick test to identify which camera device is the rear CSI camera"""

import cv2
import numpy as np

def test_camera(cam_id):
    """Test a camera device and show what it captures"""
    print(f"\n{'='*60}")
    print(f"Testing /dev/video{cam_id}")
    print(f"{'='*60}")

    try:
        cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)

        if not cap.isOpened():
            print(f"  ❌ Failed to open camera {cam_id}")
            return

        # Get camera properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

        print(f"  Resolution: {int(width)}x{int(height)} @ {int(fps)} FPS")
        print(f"  Format: {fourcc_str}")

        # Try to read a few frames
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                if i == 0:
                    print(f"  ✓ Frame captured: {frame.shape}, dtype: {frame.dtype}")
                    print(f"    Channel stats:")
                    print(f"      B: min={frame[:,:,0].min():3d}, max={frame[:,:,0].max():3d}, mean={frame[:,:,0].mean():6.1f}")
                    print(f"      G: min={frame[:,:,1].min():3d}, max={frame[:,:,1].max():3d}, mean={frame[:,:,1].mean():6.1f}")
                    print(f"      R: min={frame[:,:,2].min():3d}, max={frame[:,:,2].max():3d}, mean={frame[:,:,2].mean():6.1f}")

                    # Save frame for inspection
                    cv2.imwrite(f'/tmp/camera_{cam_id}_test.png', frame)
                    print(f"    Saved test frame to /tmp/camera_{cam_id}_test.png")
            else:
                print(f"  ❌ Failed to read frame {i}")
                break

        cap.release()

    except Exception as e:
        print(f"  ❌ Error testing camera {cam_id}: {e}")

if __name__ == "__main__":
    print("Testing available camera devices...")
    print("The rear CSI camera in CAM0 slot should show actual video data")
    print("(not uniform/flat color values)")

    # Test cameras 0, 1, 2
    for cam_id in [0, 1, 2]:
        test_camera(cam_id)

    print(f"\n{'='*60}")
    print("Test complete. Check the saved images in /tmp/")
    print("The rear camera should show actual video, not a flat color")
    print(f"{'='*60}\n")
