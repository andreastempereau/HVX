#!/usr/bin/env python3
"""
FLIR Boson thermal camera interface
Low-latency thermal imaging for helmet HUD
"""

import cv2
import numpy as np
import threading
import logging
import os

logger = logging.getLogger(__name__)


def find_flir_device():
    """
    Auto-detect FLIR thermal camera device path.
    Scans /sys/class/video4linux/ for FLIR devices.

    Returns:
        str: Device path (e.g., '/dev/video0') or None if not found
    """
    v4l_path = '/sys/class/video4linux'

    if not os.path.exists(v4l_path):
        return None

    for device in sorted(os.listdir(v4l_path)):
        name_path = os.path.join(v4l_path, device, 'name')
        try:
            with open(name_path, 'r') as f:
                name = f.read().strip()
                # Match FLIR/Boson devices
                if 'FLIR' in name or 'Boson' in name:
                    dev_path = f'/dev/{device}'
                    logger.info(f"Found FLIR device: {name} at {dev_path}")
                    return dev_path
        except (IOError, OSError):
            continue

    return None

class ThermalCamera:
    """FLIR Boson thermal camera handler - optimized for low latency"""

    def __init__(self, device=None, width=640, height=512):
        """
        Initialize thermal camera

        Args:
            device: Video device path, or None to auto-detect FLIR camera
            width: Frame width (640 for Boson)
            height: Frame height (512 for Boson)
        """
        if device is None:
            device = find_flir_device()
            if device is None:
                logger.warning("No FLIR device found, falling back to /dev/video0")
                device = '/dev/video0'
        self.device = device
        self.width = width
        self.height = height
        self.cap = None
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.capture_thread = None

    def start(self):
        """Start thermal camera capture"""
        try:
            # Open camera with minimal buffering for low latency
            self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                logger.error(f"Failed to open thermal camera at {self.device}")
                return False

            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            # Minimize buffering for lowest latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Use camera's native format (YU12/I420 for FLIR Boson)
            # Don't force FOURCC - let driver use native format

            # Start capture thread
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

            logger.info(f"Thermal camera started: {self.width}x{self.height} at {self.device}")
            print(f"[ThermalCamera] Started: {self.width}x{self.height}")
            return True

        except Exception as e:
            logger.error(f"Failed to start thermal camera: {e}")
            return False

    def _capture_loop(self):
        """Capture loop running in separate thread"""
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret:
                    # Store frame with lock
                    with self.frame_lock:
                        self.current_frame = frame
                else:
                    logger.warning("Failed to read thermal frame")

            except Exception as e:
                logger.error(f"Thermal capture error: {e}")
                break

    def get_frame(self):
        """
        Get latest thermal frame

        Returns:
            numpy array: BGR frame from thermal camera, or None if no frame
        """
        with self.frame_lock:
            if self.current_frame is not None:
                # Return copy to avoid threading issues
                return self.current_frame.copy()
        return None

    def trigger_nuc(self):
        """
        Trigger Non-Uniformity Correction (NUC) for FLIR Boson
        This recalibrates the thermal sensor to remove artifacts
        """
        try:
            import subprocess

            logger.info("Triggering FLIR Boson NUC (flat field correction)")
            print("[ThermalCamera] Triggering NUC calibration...")

            # Try method 1: V4L2 user control (if available)
            # The FLIR Boson may expose a user control for NUC
            result = subprocess.run(
                ['v4l2-ctl', '--device=' + self.device, '--set-ctrl=ffc_mode=1'],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                print("[ThermalCamera] NUC triggered via v4l2-ctl")
                logger.info("NUC triggered successfully via v4l2-ctl")
                return True

            # Method 2: Try different control names that FLIR uses
            for ctrl_name in ['flat_field_correction', 'do_ffc', 'ffc']:
                result = subprocess.run(
                    ['v4l2-ctl', '--device=' + self.device, f'--set-ctrl={ctrl_name}=1'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    print(f"[ThermalCamera] NUC triggered via {ctrl_name}")
                    logger.info(f"NUC triggered via {ctrl_name}")
                    return True

            # If v4l2 controls don't work, try USB method
            # Note: This requires pyusb and may need sudo
            try:
                import usb.core
                # Find FLIR Boson (vendor ID: 0x09cb, product ID: 0x4007)
                dev = usb.core.find(idVendor=0x09cb, idProduct=0x4007)
                if dev is not None:
                    # Send FFC command (this is camera-specific)
                    # The actual command may vary - this is a common pattern
                    try:
                        dev.ctrl_transfer(0x40, 0x00, 0x0002, 0x0000, [])
                        print("[ThermalCamera] NUC triggered via USB")
                        logger.info("NUC triggered via USB control transfer")
                        return True
                    except:
                        pass
            except ImportError:
                pass

            print("[ThermalCamera] NUC trigger not supported or requires additional setup")
            logger.warning("NUC trigger failed - control not found")
            return False

        except Exception as e:
            logger.error(f"Failed to trigger NUC: {e}")
            print(f"[ThermalCamera] NUC trigger error: {e}")
            return False

    def stop(self):
        """Stop thermal camera capture"""
        self.running = False

        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)

        if self.cap:
            self.cap.release()

        logger.info("Thermal camera stopped")
        print("[ThermalCamera] Stopped")

    def __del__(self):
        """Cleanup on destruction"""
        self.stop()
