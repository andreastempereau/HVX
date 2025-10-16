#!/usr/bin/env python3
"""Test all three cameras in the new configuration"""

import cv2
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# Initialize GStreamer
Gst.init(None)

def test_csi_camera(sensor_id, name):
    """Test a CSI camera using GStreamer"""
    print(f"\n{'='*60}")
    print(f"Testing {name} (IMX219 sensor-id {sensor_id})")
    print('='*60)

    try:
        # Build GStreamer pipeline for IMX219
        pipeline_str = (
            f"nvarguscamerasrc sensor-id={sensor_id} ! "
            f"video/x-raw(memory:NVMM), width=1280, height=720, format=NV12, framerate=30/1 ! "
            f"nvvidconv flip-method=2 ! "
            f"video/x-raw, width=640, height=480, format=BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink name=sink emit-signals=true max-buffers=1 drop=true"
        )

        print(f"Pipeline: {pipeline_str}")

        # Create pipeline
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name('sink')

        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print(f"❌ Failed to start pipeline for {name}")
            return False

        # Try to get a sample
        import time
        time.sleep(1)  # Wait for pipeline to initialize

        sample = appsink.emit('pull-sample')
        if sample is None:
            print(f"❌ No sample received from {name}")
            pipeline.set_state(Gst.State.NULL)
            return False

        # Get buffer info
        buf = sample.get_buffer()
        caps = sample.get_caps()

        print(f"✅ {name} is working!")
        print(f"   Caps: {caps.to_string()}")
        print(f"   Buffer size: {buf.get_size()} bytes")

        # Cleanup
        pipeline.set_state(Gst.State.NULL)
        return True

    except Exception as e:
        print(f"❌ Error testing {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_usb_camera(camera_id, name):
    """Test a USB webcam"""
    print(f"\n{'='*60}")
    print(f"Testing {name} (USB camera_id {camera_id})")
    print('='*60)

    try:
        cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

        if not cap.isOpened():
            print(f"❌ Failed to open {name}")
            return False

        # Try to read a frame
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"❌ Failed to read frame from {name}")
            cap.release()
            return False

        print(f"✅ {name} is working!")
        print(f"   Frame shape: {frame.shape}")
        print(f"   Resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
        print(f"   FPS: {cap.get(cv2.CAP_PROP_FPS)}")

        cap.release()
        return True

    except Exception as e:
        print(f"❌ Error testing {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("HELMET CAMERA SYSTEM TEST")
    print("="*60)

    results = {}

    # Test left eye (IMX219 sensor-id 0)
    results['left_eye'] = test_csi_camera(0, "Left Eye Camera")

    # Test right eye (IMX219 sensor-id 1)
    results['right_eye'] = test_csi_camera(1, "Right Eye Camera")

    # Test aerial USB camera
    results['aerial'] = test_usb_camera(0, "Aerial USB Camera")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, status in results.items():
        status_str = "✅ PASS" if status else "❌ FAIL"
        print(f"{name:20s}: {status_str}")

    print("\n")
    all_pass = all(results.values())
    if all_pass:
        print("🎉 All cameras are working!")
    else:
        print("⚠️  Some cameras failed. Check the output above for details.")

    return 0 if all_pass else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
