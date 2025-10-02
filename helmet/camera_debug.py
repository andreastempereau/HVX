#!/usr/bin/env python3
"""Debug camera pixel formats"""

import cv2
import numpy as np

cap = cv2.VideoCapture(0)

# Print all camera properties
print("=== Camera Properties ===")
print(f"Width: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}")
print(f"Height: {cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
print(f"FPS: {cap.get(cv2.CAP_PROP_FPS)}")
print(f"Format: {cap.get(cv2.CAP_PROP_FORMAT)}")
print(f"Mode: {cap.get(cv2.CAP_PROP_MODE)}")
fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"FOURCC: {fourcc_str} ({fourcc})")
print(f"Backend: {cap.getBackendName()}")

# Capture one frame
ret, frame = cap.read()
print(f"\n=== Frame Info ===")
print(f"Captured: {ret}")
print(f"Shape: {frame.shape}")
print(f"Dtype: {frame.dtype}")
print(f"Min/Max: {frame.min()}/{frame.max()}")
print(f"Channel means: B={frame[:,:,0].mean():.1f}, G={frame[:,:,1].mean():.1f}, R={frame[:,:,2].mean():.1f}")

# Sample a 10x10 patch from center
h, w = frame.shape[:2]
patch = frame[h//2-5:h//2+5, w//2-5:w//2+5]
print(f"\nCenter 10x10 patch sample:")
print(f"  Blue channel: {patch[:,:,0].ravel()[:10]}")
print(f"  Green channel: {patch[:,:,1].ravel()[:10]}")
print(f"  Red channel: {patch[:,:,2].ravel()[:10]}")

# Try different pixel format assumptions
print("\n=== Trying format conversions ===")

# Maybe it's YUYV packed incorrectly?
# YUYV is Y0 U0 Y1 V0 - let's see if reshaping helps
if frame.shape[2] == 3:
    print("Trying to reinterpret as different formats...")

    # Save original
    cv2.imwrite('/tmp/camera_original.jpg', frame)
    print("Saved original to /tmp/camera_original.jpg")

    # Try swapping channels
    bgr_swap = frame[:,:,[2,1,0]]  # RGB order
    cv2.imwrite('/tmp/camera_rgb_swap.jpg', bgr_swap)
    print("Saved RGB swap to /tmp/camera_rgb_swap.jpg")

    # Try each channel individually
    cv2.imwrite('/tmp/camera_channel_b.jpg', frame[:,:,0])
    cv2.imwrite('/tmp/camera_channel_g.jpg', frame[:,:,1])
    cv2.imwrite('/tmp/camera_channel_r.jpg', frame[:,:,2])
    print("Saved individual channels to /tmp/camera_channel_*.jpg")

cap.release()

print("\nCheck the saved images in /tmp/ to see which looks correct")
print("If one of the single channels (B, G, or R) looks correct, it means the camera")
print("is outputting grayscale but OpenCV is treating it as color.")
