#!/usr/bin/env python3
"""Find which two cameras can be opened simultaneously"""

import cv2
import sys

def test_dual(dev1, dev2):
    """Test if two cameras can be opened at the same time"""
    print(f"\nTesting /dev/video{dev1} + /dev/video{dev2}...")

    cap1 = cv2.VideoCapture(dev1, cv2.CAP_V4L2)
    if not cap1.isOpened():
        print(f"  ❌ /dev/video{dev1} failed to open")
        return False

    cap2 = cv2.VideoCapture(dev2, cv2.CAP_V4L2)
    if not cap2.isOpened():
        print(f"  ❌ /dev/video{dev2} failed to open")
        cap1.release()
        return False

    # Try to read from both
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if ret1 and ret2 and frame1 is not None and frame2 is not None:
        print(f"  ✅ Both working! {frame1.shape[1]}x{frame1.shape[0]} + {frame2.shape[1]}x{frame2.shape[0]}")
        cap1.release()
        cap2.release()
        return True
    else:
        print(f"  ❌ Failed to read frames (ret1={ret1}, ret2={ret2})")
        cap1.release()
        cap2.release()
        return False

def main():
    print("="*60)
    print("FINDING DUAL CAMERA PAIRS")
    print("="*60)

    working_pairs = []

    # Test all combinations
    for i in range(4):
        for j in range(i+1, 4):
            if test_dual(i, j):
                working_pairs.append((i, j))

    print("\n" + "="*60)
    if working_pairs:
        print("✅ Working camera pairs:")
        for pair in working_pairs:
            print(f"   /dev/video{pair[0]} + /dev/video{pair[1]}")
    else:
        print("❌ No working dual camera pairs found!")
    print("="*60)

if __name__ == "__main__":
    main()
