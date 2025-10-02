#!/usr/bin/env python3
"""Test different camera color formats"""

import cv2
import sys

print("Opening camera...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open camera")
    sys.exit(1)

# Try to get camera format info
fourcc = cap.get(cv2.CAP_PROP_FOURCC)
fourcc_str = "".join([chr((int(fourcc) >> 8 * i) & 0xFF) for i in range(4)])
print(f"Camera FOURCC format: {fourcc_str}")

# Try setting to MJPEG (common format)
print("\nTrying MJPEG format...")
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))

# Capture a frame
ret, frame = cap.read()
if not ret:
    print("Failed to capture frame")
    sys.exit(1)

print(f"Frame shape: {frame.shape}")
print(f"Frame dtype: {frame.dtype}")
print(f"Frame min/max: {frame.min()}/{frame.max()}")
print(f"Mean values per channel: R={frame[:,:,2].mean():.1f}, G={frame[:,:,1].mean():.1f}, B={frame[:,:,0].mean():.1f}")

cv2.namedWindow('Original (BGR)', cv2.WINDOW_NORMAL)
cv2.namedWindow('RGB Converted', cv2.WINDOW_NORMAL)
cv2.namedWindow('YUV Converted', cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Original BGR
    cv2.imshow('Original (BGR)', frame)

    # Try BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cv2.imshow('RGB Converted', frame_rgb)

    # Try assuming it's YUV
    try:
        # Try different YUV conversions
        frame_yuv = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR)
        cv2.imshow('YUV Converted', frame_yuv)
    except:
        pass

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
