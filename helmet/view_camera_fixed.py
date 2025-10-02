#!/usr/bin/env python3
"""Camera viewer with YUYV conversion fix"""

import cv2
import sys
import numpy as np

print("Opening camera...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("ERROR: Could not open camera")
    sys.exit(1)

# Check what format we're getting
fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"Camera format: {fourcc_str}")

print("Camera opened! Press 'q' to quit")
cv2.namedWindow('Camera Feed', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Camera Feed', 1280, 720)

frame_count = 0
while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    # If the frame is all green (YUYV misinterpretation), extract the Y channel
    # Check if we have the YUYV problem (only green channel has data)
    if frame[:,:,0].max() < 10 and frame[:,:,2].max() < 10 and frame[:,:,1].max() > 10:
        # Extract just the Y (luminance) channel which is in the green channel
        gray = frame[:,:,1]
        # Convert back to BGR for display
        frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.putText(frame, "YUYV->Grayscale conversion", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    frame_count += 1
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow('Camera Feed', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Camera closed")
