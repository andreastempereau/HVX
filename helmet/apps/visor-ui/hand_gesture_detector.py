"""
Hand gesture detection using depth camera
Detects fist (closed hand) and open palm gestures for AR pin control
"""
import cv2
import numpy as np
from typing import Optional, Tuple, Literal


class HandGestureDetector:
    """Detects hand gestures using depth + color data"""

    def __init__(self,
                 min_hand_depth=0.3,  # 30cm minimum
                 max_hand_depth=1.0,  # 1m maximum
                 min_hand_area=2000,  # Minimum contour area in pixels
                 fist_circularity_threshold=0.7,  # How round is a fist
                 palm_finger_count_min=3):  # Minimum fingers for open palm
        """
        Initialize gesture detector

        Args:
            min_hand_depth: Minimum depth for hand detection (meters)
            max_hand_depth: Maximum depth for hand detection (meters)
            min_hand_area: Minimum contour area (pixels)
            fist_circularity_threshold: Circularity ratio for fist detection
            palm_finger_count_min: Minimum convexity defects for open palm
        """
        self.min_hand_depth = min_hand_depth
        self.max_hand_depth = max_hand_depth
        self.min_hand_area = min_hand_area
        self.fist_circularity = fist_circularity_threshold
        self.palm_finger_count = palm_finger_count_min

        # Gesture state tracking
        self.last_gesture = None
        self.gesture_stable_frames = 0
        self.stability_threshold = 5  # Frames needed to confirm gesture

    def detect(self,
               color_frame: np.ndarray,
               depth_frame: np.ndarray) -> Optional[Tuple[str, Tuple[int, int], float]]:
        """
        Detect hand gesture in current frame

        Args:
            color_frame: BGR color image
            depth_frame: Depth image (uint16, values in mm)

        Returns:
            Tuple of (gesture_type, (x, y), depth_m) or None
            gesture_type: 'fist' or 'palm'
            (x, y): Center of hand in image coordinates
            depth_m: Depth of hand center in meters
        """
        if color_frame is None or depth_frame is None:
            return None

        try:
            # 1. Create depth mask for hand distance range
            depth_m = depth_frame / 1000.0  # Convert to meters
            hand_mask = np.logical_and(
                depth_m > self.min_hand_depth,
                depth_m < self.max_hand_depth
            ).astype(np.uint8) * 255

            # 2. Find contours in the depth mask
            contours, _ = cv2.findContours(hand_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                self._reset_tracking()
                return None

            # 3. Find largest contour (likely the hand)
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)

            if area < self.min_hand_area:
                self._reset_tracking()
                return None

            # 4. Get hand properties
            M = cv2.moments(largest_contour)
            if M["m00"] == 0:
                return None

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Get depth at center
            hand_depth = depth_m[cy, cx]

            # 5. Detect gesture type
            gesture_type = self._classify_gesture(largest_contour, area)

            if gesture_type is None:
                self._reset_tracking()
                return None

            # 6. Check gesture stability (avoid false positives)
            if gesture_type == self.last_gesture:
                self.gesture_stable_frames += 1
            else:
                self.last_gesture = gesture_type
                self.gesture_stable_frames = 1

            # Only return gesture if it's been stable for enough frames
            if self.gesture_stable_frames >= self.stability_threshold:
                return (gesture_type, (cx, cy), hand_depth)

            return None

        except Exception as e:
            print(f"[HandGesture] Detection error: {e}")
            return None

    def _classify_gesture(self, contour: np.ndarray, area: float) -> Optional[Literal['fist', 'palm']]:
        """
        Classify gesture based on contour shape

        Args:
            contour: Hand contour
            area: Contour area

        Returns:
            'fist', 'palm', or None
        """
        try:
            # Calculate contour perimeter
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                return None

            # Circularity: 4π * area / perimeter²
            # Perfect circle = 1.0, more complex shapes < 1.0
            circularity = 4 * np.pi * area / (perimeter * perimeter)

            # FIST detection: High circularity (compact, round shape)
            if circularity > self.fist_circularity:
                return 'fist'

            # PALM detection: Low circularity + convexity defects (fingers)
            # Find convex hull and defects
            hull = cv2.convexHull(contour, returnPoints=False)

            if len(hull) > 3 and len(contour) > 3:
                try:
                    defects = cv2.convexityDefects(contour, hull)

                    if defects is not None:
                        # Count significant defects (gaps between fingers)
                        finger_count = 0
                        for i in range(defects.shape[0]):
                            s, e, f, d = defects[i, 0]
                            # d is the distance from contour point to hull
                            # Larger distance = more significant defect (finger gap)
                            if d > 5000:  # Threshold for significant defect
                                finger_count += 1

                        # Open palm has multiple finger gaps
                        if finger_count >= self.palm_finger_count:
                            return 'palm'
                except Exception:
                    pass  # convexityDefects can fail on some contours

            return None

        except Exception as e:
            print(f"[HandGesture] Classification error: {e}")
            return None

    def _reset_tracking(self):
        """Reset gesture tracking state"""
        self.last_gesture = None
        self.gesture_stable_frames = 0

    def draw_debug(self,
                   frame: np.ndarray,
                   gesture_result: Optional[Tuple[str, Tuple[int, int], float]]) -> np.ndarray:
        """
        Draw debug visualization on frame

        Args:
            frame: Image to draw on
            gesture_result: Result from detect()

        Returns:
            Frame with debug overlay
        """
        if gesture_result is None:
            return frame

        gesture_type, (cx, cy), depth = gesture_result

        # Draw circle at hand center
        color = (0, 255, 0) if gesture_type == 'fist' else (255, 0, 255)
        cv2.circle(frame, (cx, cy), 20, color, 3)

        # Draw gesture label
        label = f"{gesture_type.upper()} {depth:.2f}m"
        cv2.putText(frame, label, (cx - 50, cy - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return frame
