"""Simple rear camera capture using GStreamer (for Jetson CSI cameras)"""

import threading
import logging
from typing import Optional
import numpy as np
import cv2
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

logger = logging.getLogger(__name__)

# Initialize GStreamer
Gst.init(None)


class RearCamera:
    """Rear camera handler for CSI camera using GStreamer"""

    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.pipeline = None
        self.running = False
        self.thread = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.width = 720
        self.height = 1280

    def start(self, use_gstreamer=True):
        """Start camera capture using GStreamer"""
        if self.running:
            return True

        try:
            # Build GStreamer pipeline for Jetson CSI camera
            pipeline_str = (
                f"nvarguscamerasrc sensor-id={self.camera_id} ! "
                f"video/x-raw(memory:NVMM), width=1280, height=720, format=NV12, framerate=10/1 ! "
                f"nvvidconv flip-method=3 ! "
                f"video/x-raw, width={self.width}, height={self.height}, format=BGRx ! "
                f"videoconvert ! "
                f"video/x-raw, format=BGR ! "
                f"appsink name=sink emit-signals=true max-buffers=1 drop=true"
            )

            print(f"Starting rear camera with GStreamer pipeline:")
            print(f"  sensor-id={self.camera_id}, output={self.width}x{self.height}")

            # Create pipeline
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.appsink = self.pipeline.get_by_name('sink')

            # Connect to new-sample signal
            self.appsink.connect('new-sample', self._on_new_sample)

            # Start pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to start GStreamer pipeline")
                return False

            self.running = True
            print(f"Rear camera started successfully (sensor-id {self.camera_id})")
            logger.info(f"Rear camera started on sensor {self.camera_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start rear camera: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _on_new_sample(self, appsink):
        """Callback for new frame from GStreamer"""
        try:
            # Pull sample from appsink
            sample = appsink.emit('pull-sample')
            if sample is None:
                return Gst.FlowReturn.OK

            # Get buffer from sample
            buf = sample.get_buffer()
            caps = sample.get_caps()

            # Get buffer data
            success, map_info = buf.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK

            # Convert to numpy array
            frame = np.ndarray(
                shape=(self.height, self.width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )

            # Store frame (make a copy since buffer will be unmapped)
            with self.frame_lock:
                self.current_frame = frame.copy()

            # Unmap buffer
            buf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            logger.error(f"Error in frame callback: {e}")
            return Gst.FlowReturn.ERROR

    def stop(self):
        """Stop camera capture"""
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        logger.info("Rear camera stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        """Get current frame (BGR format from GStreamer, convert to RGB)"""
        with self.frame_lock:
            if self.current_frame is not None:
                # GStreamer gives us BGR, convert to RGB
                return cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        return None
