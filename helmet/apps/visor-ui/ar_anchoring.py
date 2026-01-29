"""
AR Anchoring System for Xreal Birdbath Optics
Manages 3D spatial pins that appear fixed in real-world space
"""
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
import time
import math


@dataclass
class ARPin:
    """Represents a spatial pin anchored in 3D space"""
    id: int
    position_3d: np.ndarray  # [x, y, z] in meters, world coordinates
    created_at: float  # Timestamp
    label: str = ""  # Optional text label
    color: Tuple[int, int, int] = (0, 255, 0)  # BGR color


class ARAnchoringSystem:
    """
    Manages AR pins for Xreal birdbath optics display

    Key constraints:
    - Xreal displays a virtual screen at ~2m distance
    - Screen is fixed relative to head (not true AR passthrough)
    - Need to project 3D pins onto 2D screen based on head orientation
    """

    def __init__(self,
                 screen_width=1920,
                 screen_height=1080,
                 fov_horizontal=90.0,  # Wider FOV for smoother pin movement
                 virtual_screen_distance=2.0):  # Virtual screen distance in meters
        """
        Initialize AR anchoring system

        Args:
            screen_width: Display width in pixels
            screen_height: Display height in pixels
            fov_horizontal: Horizontal field of view in degrees
            virtual_screen_distance: Distance to virtual screen in meters
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fov_h = math.radians(fov_horizontal)
        self.fov_v = math.radians(fov_horizontal * screen_height / screen_width)  # Approximate vertical FOV
        self.virtual_distance = virtual_screen_distance

        # Pin storage
        self.pins: List[ARPin] = []
        self.next_pin_id = 1

        # Head tracking state
        self.head_yaw = 0.0  # Rotation around Y axis (left/right)
        self.head_pitch = 0.0  # Rotation around X axis (up/down)
        self.head_roll = 0.0  # Rotation around Z axis (tilt)

        # Reference frame (where head was when system started)
        self.reference_yaw = 0.0
        self.reference_pitch = 0.0
        self.reference_roll = 0.0
        self.reference_set = False

    def set_head_orientation(self, yaw: float, pitch: float, roll: float):
        """
        Update head orientation from gyro/IMU data

        Args:
            yaw: Yaw angle in degrees (left/right rotation)
            pitch: Pitch angle in degrees (up/down rotation)
            roll: Roll angle in degrees (tilt rotation)
        """
        # Validate inputs - reject NaN/Inf values
        if not (math.isfinite(yaw) and math.isfinite(pitch) and math.isfinite(roll)):
            print(f"[ARAnchoring] WARNING: Invalid orientation values (NaN/Inf), ignoring: yaw={yaw} pitch={pitch} roll={roll}")
            return

        # Set reference frame on first call
        if not self.reference_set:
            self.reference_yaw = yaw
            self.reference_pitch = pitch
            self.reference_roll = roll
            self.reference_set = True
            print(f"[AR] Head tracking active (ref: yaw={yaw:.1f}°)")

        # Store current orientation relative to reference
        self.head_yaw = yaw - self.reference_yaw
        self.head_pitch = pitch - self.reference_pitch
        self.head_roll = roll - self.reference_roll

        # Track orientation updates
        if not hasattr(self, '_orientation_update_count'):
            self._orientation_update_count = 0
        self._orientation_update_count += 1

    def add_pin(self,
                world_position: np.ndarray,
                label: str = "",
                color: Tuple[int, int, int] = (0, 255, 0)) -> ARPin:
        """
        Add a new AR pin at 3D world position

        Args:
            world_position: [x, y, z] position in meters (world coordinates)
            label: Optional text label
            color: Pin color (BGR)

        Returns:
            Created ARPin object
        """
        pin = ARPin(
            id=self.next_pin_id,
            position_3d=world_position.copy(),
            created_at=time.time(),
            label=label,
            color=color
        )
        self.pins.append(pin)
        self.next_pin_id += 1
        return pin

    def remove_pin(self, pin_id: int) -> bool:
        """
        Remove pin by ID

        Args:
            pin_id: Pin ID to remove

        Returns:
            True if removed, False if not found
        """
        for i, pin in enumerate(self.pins):
            if pin.id == pin_id:
                self.pins.pop(i)
                return True
        return False

    def get_pin_at_screen_position(self,
                                     screen_x: int,
                                     screen_y: int,
                                     tolerance: int = 50) -> Optional[ARPin]:
        """
        Find pin near screen coordinates (for deletion with open palm)

        Args:
            screen_x: X coordinate on screen
            screen_y: Y coordinate on screen
            tolerance: Distance tolerance in pixels

        Returns:
            Nearest pin within tolerance, or None
        """
        nearest_pin = None
        nearest_dist = tolerance

        for pin in self.pins:
            screen_pos = self.project_to_screen(pin.position_3d)
            if screen_pos is None:
                continue

            px, py = screen_pos
            dist = math.sqrt((px - screen_x)**2 + (py - screen_y)**2)

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_pin = pin

        return nearest_pin

    def project_to_screen(self, world_position: np.ndarray, debug: bool = False) -> Optional[Tuple[int, int]]:
        """
        Project 3D world position to 2D screen coordinates

        Args:
            world_position: [x, y, z] in world coordinates (meters)
            debug: If True, print debug info about projection

        Returns:
            (screen_x, screen_y) in pixels, or None if behind camera/outside FOV
        """
        try:
            # Ensure world_position is a proper numpy array with float values
            if not isinstance(world_position, np.ndarray):
                world_position = np.array(world_position, dtype=np.float64)
            else:
                world_position = world_position.astype(np.float64)

            # 1. Rotate point based on head orientation
            # Apply inverse rotation to simulate fixed world with moving head
            rotated = self._rotate_point_inverse(
                world_position,
                self.head_yaw,
                self.head_pitch,
                self.head_roll
            )

            # Extract scalar values from numpy array
            x = float(rotated[0])
            y = float(rotated[1])
            z = float(rotated[2])

            # 2. Check if point is in front of camera
            if z <= 0.01:  # Small epsilon to avoid edge cases
                return None  # Behind camera

            # 3. Project onto virtual screen using perspective projection
            angle_h = math.atan2(x, z)  # Horizontal angle
            angle_v = math.atan2(y, z)  # Vertical angle

            # Check if within FOV (with small margin for edge cases)
            fov_h_limit = self.fov_h / 2 * 1.1  # 10% margin
            fov_v_limit = self.fov_v / 2 * 1.1
            if abs(angle_h) > fov_h_limit or abs(angle_v) > fov_v_limit:
                return None  # Outside field of view

            # Map angle to screen coordinates
            screen_x = int((angle_h / self.fov_h + 0.5) * self.screen_width)
            screen_y = int((0.5 - angle_v / self.fov_v) * self.screen_height)

            # Clamp to screen bounds
            screen_x = max(0, min(self.screen_width - 1, screen_x))
            screen_y = max(0, min(self.screen_height - 1, screen_y))

            return (screen_x, screen_y)

        except Exception as e:
            print(f"[ARAnchoring] Projection error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _rotate_point_inverse(self,
                               point: np.ndarray,
                               yaw: float,
                               pitch: float,
                               roll: float) -> np.ndarray:
        """
        Apply inverse rotation to point (world stays fixed, head rotates)

        Args:
            point: [x, y, z] point to rotate
            yaw: Yaw in degrees
            pitch: Pitch in degrees
            roll: Roll in degrees

        Returns:
            Rotated point
        """
        # Convert to radians (negative for inverse)
        yaw_rad = math.radians(-yaw)
        pitch_rad = math.radians(-pitch)
        roll_rad = math.radians(-roll)

        # Rotation matrices
        # Yaw (around Y axis)
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        R_yaw = np.array([
            [cos_yaw, 0, sin_yaw],
            [0, 1, 0],
            [-sin_yaw, 0, cos_yaw]
        ])

        # Pitch (around X axis)
        cos_pitch = math.cos(pitch_rad)
        sin_pitch = math.sin(pitch_rad)
        R_pitch = np.array([
            [1, 0, 0],
            [0, cos_pitch, -sin_pitch],
            [0, sin_pitch, cos_pitch]
        ])

        # Roll (around Z axis)
        cos_roll = math.cos(roll_rad)
        sin_roll = math.sin(roll_rad)
        R_roll = np.array([
            [cos_roll, -sin_roll, 0],
            [sin_roll, cos_roll, 0],
            [0, 0, 1]
        ])

        # Apply rotations in REVERSE order for proper inverse
        # If forward is: R_yaw @ R_pitch @ R_roll @ point
        # Then inverse is: R_roll(-) @ R_pitch(-) @ R_yaw(-) @ point
        rotated = R_roll @ R_pitch @ R_yaw @ point
        return rotated

    def get_all_pins_screen_positions(self) -> List[Tuple[ARPin, Tuple[int, int]]]:
        """
        Get all pins with their current screen positions

        Returns:
            List of (pin, (screen_x, screen_y)) tuples
            Only includes pins currently visible on screen
        """
        results = []
        for pin in self.pins:
            screen_pos = self.project_to_screen(pin.position_3d)
            if screen_pos is not None:
                results.append((pin, screen_pos))
        return results

    def reset_reference_frame(self):
        """Reset the reference frame to current head orientation"""
        self.reference_set = False

    def clear_all_pins(self):
        """Remove all pins"""
        self.pins.clear()

    def get_stats(self) -> dict:
        """Get system statistics"""
        return {
            'pin_count': len(self.pins),
            'head_yaw': self.head_yaw,
            'head_pitch': self.head_pitch,
            'head_roll': self.head_roll,
            'reference_set': self.reference_set
        }
