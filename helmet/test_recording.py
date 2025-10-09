#!/usr/bin/env python3
"""Test video recording functionality"""

import sys
import time
from pathlib import Path

# Add libs to path
sys.path.append(str(Path(__file__).parent / "libs"))
sys.path.append(str(Path(__file__).parent / "apps" / "visor-ui"))

from video_recorder import VideoRecorder
import numpy as np
import cv2

print("="*60)
print("VIDEO RECORDER TEST")
print("="*60)

# Initialize recorder
output_dir = Path(__file__).parent / "recordings"
print(f"\nOutput directory: {output_dir}")
print(f"Directory exists: {output_dir.exists()}")

recorder = VideoRecorder(output_dir=str(output_dir), fps=30)

# Callbacks
def on_started(filename, duration):
    print(f"\n✓ Recording started: {filename}")
    if duration:
        print(f"  Duration limit: {duration}s")

def on_stopped(filename, frames, duration):
    print(f"\n✓ Recording stopped: {filename}")
    print(f"  Frames written: {frames}")
    print(f"  Duration: {duration:.1f}s")
    print(f"  File size: {Path(filename).stat().st_size / 1024 / 1024:.2f} MB")

recorder.on_recording_started = on_started
recorder.on_recording_stopped = on_stopped

# Test 1: 3-second recording
print("\n" + "-"*60)
print("TEST 1: 3-second recording with synthetic frames")
print("-"*60)

filename = recorder.start_recording(duration_seconds=3, filename="test_3sec")

# Generate 90 frames (3 seconds at 30fps)
for i in range(90):
    # Create 1280x720 test frame (matching helmet camera resolution)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Create a gradient pattern
    frame[:, :, 0] = (i * 3) % 256  # Red varies
    frame[:, :, 1] = 128  # Green constant
    frame[:, :, 2] = 255 - (i * 3) % 256  # Blue inverse

    # Add text overlay
    cv2.putText(
        frame,
        f"Frame {i+1}/90 - Time: {i/30:.2f}s",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        2,
        (255, 255, 255),
        3
    )

    # Add timestamp
    cv2.putText(
        frame,
        time.strftime("%H:%M:%S"),
        (50, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 255, 0),
        2
    )

    recorder.add_frame(frame)
    time.sleep(1/30)  # 30fps timing

# Wait for auto-stop
time.sleep(0.5)

# Test 2: Manual stop
print("\n" + "-"*60)
print("TEST 2: 1-second recording with manual stop")
print("-"*60)

filename = recorder.start_recording(filename="test_manual_stop")

# Generate 30 frames (1 second)
for i in range(30):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :, 1] = 255  # All green

    cv2.putText(
        frame,
        f"Manual Stop Test - Frame {i+1}",
        (50, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        2,
        (255, 255, 255),
        3
    )

    recorder.add_frame(frame)
    time.sleep(1/30)

saved_file = recorder.stop_recording()

# Test 3: Check recording status
print("\n" + "-"*60)
print("TEST 3: Recording status check")
print("-"*60)

print("\nBefore starting:")
info = recorder.get_recording_info()
print(f"  Recording: {info['recording']}")

recorder.start_recording(filename="test_status")
print("\nDuring recording:")
info = recorder.get_recording_info()
print(f"  Recording: {info['recording']}")
print(f"  Filename: {Path(info['filename']).name}")
print(f"  Duration: {info['duration']:.2f}s")
print(f"  Frames: {info['frames']}")

# Add a few frames
for i in range(30):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :, 2] = 255  # Blue
    recorder.add_frame(frame)
    time.sleep(1/30)

recorder.stop_recording()
print("\nAfter stopping:")
info = recorder.get_recording_info()
print(f"  Recording: {info['recording']}")

# Summary
print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
print(f"\nRecordings saved to: {output_dir}")
print("\nFiles created:")
for video_file in sorted(output_dir.glob("test_*.mp4")):
    size_mb = video_file.stat().st_size / 1024 / 1024
    print(f"  - {video_file.name} ({size_mb:.2f} MB)")

print("\nYou can play these videos with:")
print(f"  mpv {output_dir}/test_3sec.mp4")
print(f"  vlc {output_dir}/test_manual_stop.mp4")
