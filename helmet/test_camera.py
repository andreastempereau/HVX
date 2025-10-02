#!/usr/bin/env python3
"""Simple camera test script"""

import cv2
import sys

print("Testing camera...")

# Try to open camera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open camera")
    sys.exit(1)

# Get camera properties
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

print(f"Camera opened successfully!")
print(f"Resolution: {width}x{height}")
print(f"FPS: {fps}")

# Capture a few frames
for i in range(5):
    ret, frame = cap.read()
    if ret:
        print(f"Frame {i+1}: {frame.shape}, dtype={frame.dtype}, size={frame.nbytes} bytes")
    else:
        print(f"Frame {i+1}: Failed to capture")

cap.release()
print("\nCamera test completed!")
print(f"Frame size in MB: {frame.nbytes / (1024*1024):.2f} MB")
