#!/usr/bin/env python3
"""
FLIR Boson thermal camera interface
Low-latency thermal imaging for helmet HUD
"""

import cv2
import numpy as np
import threading
import logging

logger = logging.getLogger(__name__)

class ThermalCamera:
    """FLIR Boson thermal camera handler - optimized for low latency"""

    def __init__(self, device='/dev/video2', width=640, height=512):
        """
        Initialize thermal camera

        Args:
            device: Video device path (default /dev/video2 for FLIR)
            width: Frame width (640 for Boson)
            height: Frame height (512 for Boson)
        """
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

            # Set format to YUV for efficiency
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))

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
