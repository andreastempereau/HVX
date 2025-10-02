#!/usr/bin/env python3
"""Simple camera viewer with OpenCV"""

import cv2
import sys

print("Opening camera...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open camera")
    sys.exit(1)

# Force MJPEG format to avoid YUYV conversion issues
print("Setting camera to MJPEG format...")
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))

print("Camera opened! Press 'q' to quit")
print("Creating window...")

cv2.namedWindow('Camera Feed', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Camera Feed', 1280, 720)

frame_count = 0
while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    # Add frame counter
    frame_count += 1
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Show frame
    cv2.imshow('Camera Feed', frame)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Camera closed")
