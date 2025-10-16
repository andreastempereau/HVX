#!/usr/bin/env python3
"""Test script for dual CSI camera combination modes"""

import cv2
import sys
from pathlib import Path

# Add libs to path
sys.path.append(str(Path(__file__).parent / "libs"))
from utils.config import get_config

def test_dual_cameras():
    """Test dual camera capture and combination"""
    config = get_config()

    print("=" * 60)
    print("Dual Camera Combination Test")
    print("=" * 60)

    # Get camera configuration
    camera_type = config.get('video.camera_type', 'webcam')
    combination_mode = config.get('video.dual_camera.combination_mode', 'side-by-side')
    left_sensor_id = config.get('video.dual_camera.left_sensor_id', 0)
    right_sensor_id = config.get('video.dual_camera.right_sensor_id', 1)
    width = config.get('video.width', 1280)
    height = config.get('video.height', 720)
    fps = config.get('video.fps', 30)

    print(f"\nConfiguration:")
    print(f"  Camera Type: {camera_type}")
    print(f"  Combination Mode: {combination_mode}")
    print(f"  Left Sensor ID: {left_sensor_id}")
    print(f"  Right Sensor ID: {right_sensor_id}")
    print(f"  Resolution: {width}x{height}@{fps}fps")

    if camera_type != 'csi_dual':
        print(f"\nError: Camera type is '{camera_type}', expected 'csi_dual'")
        print("Please update configs/profiles/dev.json to use 'csi_dual' camera type")
        return False

    # Create GStreamer pipelines
    gst_pipeline_left = (
        f"nvarguscamerasrc sensor-id={left_sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvideoconvert flip-method=2 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=BGR ! appsink max-buffers=1 drop=true"
    )

    gst_pipeline_right = (
        f"nvarguscamerasrc sensor-id={right_sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvideoconvert flip-method=2 ! "
        f"video/x-raw, width={width}, height={height}, format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=BGR ! appsink max-buffers=1 drop=true"
    )

    print("\nInitializing cameras...")
    print(f"  Left camera: sensor-id={left_sensor_id}")
    print(f"  Right camera: sensor-id={right_sensor_id}")

    # Initialize cameras
    cap_left = cv2.VideoCapture(gst_pipeline_left, cv2.CAP_GSTREAMER)
    cap_right = cv2.VideoCapture(gst_pipeline_right, cv2.CAP_GSTREAMER)

    if not cap_left.isOpened():
        print(f"\n✗ Failed to open left camera (sensor-id={left_sensor_id})")
        return False
    else:
        print(f"  ✓ Left camera opened successfully")

    if not cap_right.isOpened():
        print(f"\n✗ Failed to open right camera (sensor-id={right_sensor_id})")
        cap_left.release()
        return False
    else:
        print(f"  ✓ Right camera opened successfully")

    # Flush initial frames
    print("\nFlushing initial frames...")
    for _ in range(5):
        cap_left.grab()
        cap_right.grab()

    # Capture test frames
    print("\nCapturing test frames...")
    ret_left, frame_left = cap_left.read()
    ret_right, frame_right = cap_right.read()

    if not ret_left or frame_left is None:
        print("✗ Failed to capture from left camera")
        cap_left.release()
        cap_right.release()
        return False

    if not ret_right or frame_right is None:
        print("✗ Failed to capture from right camera")
        cap_left.release()
        cap_right.release()
        return False

    print(f"  ✓ Left frame: {frame_left.shape}")
    print(f"  ✓ Right frame: {frame_right.shape}")

    # Convert to RGB
    frame_left_rgb = cv2.cvtColor(frame_left, cv2.COLOR_BGR2RGB)
    frame_right_rgb = cv2.cvtColor(frame_right, cv2.COLOR_BGR2RGB)

    # Test all combination modes
    print("\nTesting combination modes:")

    # 1. Side-by-side
    combined_sbs = cv2.hconcat([frame_left, frame_right])
    print(f"  ✓ Side-by-side: {combined_sbs.shape}")
    cv2.imwrite('/tmp/test_side_by_side.jpg', combined_sbs)
    print(f"    Saved to: /tmp/test_side_by_side.jpg")

    # 2. Top-bottom
    combined_tb = cv2.vconcat([frame_left, frame_right])
    print(f"  ✓ Top-bottom: {combined_tb.shape}")
    cv2.imwrite('/tmp/test_top_bottom.jpg', combined_tb)
    print(f"    Saved to: /tmp/test_top_bottom.jpg")

    # 3. Picture-in-picture
    pip_scale = 0.25
    combined_pip = frame_left.copy()
    pip_height = int(frame_right.shape[0] * pip_scale)
    pip_width = int(frame_right.shape[1] * pip_scale)
    pip_frame = cv2.resize(frame_right, (pip_width, pip_height))

    # Position in top-right
    h, w = combined_pip.shape[:2]
    ph, pw = pip_frame.shape[:2]
    y, x = 10, w - pw - 10

    # Add white border
    cv2.rectangle(combined_pip, (x-2, y-2), (x+pw+2, y+ph+2), (255, 255, 255), 2)
    combined_pip[y:y+ph, x:x+pw] = pip_frame

    print(f"  ✓ Picture-in-picture: {combined_pip.shape}")
    cv2.imwrite('/tmp/test_pip.jpg', combined_pip)
    print(f"    Saved to: /tmp/test_pip.jpg")

    # Capture a few frames to test performance
    print("\nPerformance test (capturing 30 frames)...")
    import time
    start_time = time.time()
    frame_count = 0

    for i in range(30):
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()

        if ret_left and ret_right:
            frame_count += 1

    elapsed = time.time() - start_time
    actual_fps = frame_count / elapsed

    print(f"  ✓ Captured {frame_count} frames in {elapsed:.2f}s")
    print(f"  ✓ Actual FPS: {actual_fps:.1f} fps")

    # Cleanup
    cap_left.release()
    cap_right.release()

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
    print("\nYou can now:")
    print("  1. Start the video service: python services/video/video_service.py")
    print("  2. View combined feed in the HUD")
    print("\nTest images saved to /tmp/:")
    print("  - test_side_by_side.jpg")
    print("  - test_top_bottom.jpg")
    print("  - test_pip.jpg")

    return True

if __name__ == "__main__":
    try:
        success = test_dual_cameras()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
