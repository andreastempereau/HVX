#!/usr/bin/env python3
"""Test all camera indices to find working USB webcam"""

import cv2
import sys

print("Testing all camera indices...")

for i in range(10):
    print(f"\n=== Testing camera index {i} ===")

    # Try default backend
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✓ Camera {i} works with default backend: {frame.shape}")
            cap.release()
            continue
        cap.release()

    # Try V4L2 backend
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✓ Camera {i} works with V4L2 backend: {frame.shape}")
            cap.release()
            continue
        cap.release()

    print(f"✗ Camera {i} not available")

print("\nDone testing cameras")
