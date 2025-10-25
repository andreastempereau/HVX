"""Direct dual CSI camera capture using GStreamer (for Jetson IMX219 cameras with split-screen)"""

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


class DirectCamera:
    """Direct dual CSI camera handler using GStreamer with split-screen"""

    def __init__(self, sensor_id=0, width=1280, height=720, fps=30, dual_mode=True, device_left='/dev/video0', device_right='/dev/video1'):
        self.sensor_id = sensor_id
        self.dual_mode = dual_mode
        self.device_left = device_left
        self.device_right = device_right

        # Extract sensor IDs from device paths (video0 = sensor 0, video1 = sensor 1)
        self.sensor_id_left = int(device_left.split('video')[-1])
        self.sensor_id_right = int(device_right.split('video')[-1])

        self.pipeline_left = None
        self.pipeline_right = None
        self.running = False
        self.current_frame_left = None
        self.current_frame_right = None
        self.frame_lock = threading.Lock()
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0

    def start(self):
        """Start dual CSI camera capture using GStreamer"""
        if self.running:
            return True

        try:
            if self.dual_mode:
                print(f"Starting dual CSI camera with GStreamer:")
                print(f"  Left: sensor-id={self.sensor_id_left}, {self.width}x{self.height}@{self.fps}fps")
                print(f"  Right: sensor-id={self.sensor_id_right}, {self.width}x{self.height}@{self.fps}fps")

                # Build GStreamer pipeline for left camera (flip-method=2 rotates 180 degrees)
                pipeline_left_str = (
                    f"nvarguscamerasrc sensor-id={self.sensor_id_left} ! "
                    f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, "
                    f"format=NV12, framerate={self.fps}/1 ! "
                    f"nvvidconv flip-method=2 ! "
                    f"video/x-raw, width={self.width}, height={self.height}, format=BGRx ! "
                    f"videoconvert ! "
                    f"video/x-raw, format=BGR ! "
                    f"appsink name=sink_left emit-signals=true max-buffers=1 drop=true sync=false"
                )

                # Build GStreamer pipeline for right camera (flip-method=2 rotates 180 degrees)
                pipeline_right_str = (
                    f"nvarguscamerasrc sensor-id={self.sensor_id_right} ! "
                    f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, "
                    f"format=NV12, framerate={self.fps}/1 ! "
                    f"nvvidconv flip-method=2 ! "
                    f"video/x-raw, width={self.width}, height={self.height}, format=BGRx ! "
                    f"videoconvert ! "
                    f"video/x-raw, format=BGR ! "
                    f"appsink name=sink_right emit-signals=true max-buffers=1 drop=true sync=false"
                )

                # Create left pipeline
                self.pipeline_left = Gst.parse_launch(pipeline_left_str)
                self.appsink_left = self.pipeline_left.get_by_name('sink_left')
                self.appsink_left.connect('new-sample', self._on_new_sample_left)

                # Create right pipeline
                self.pipeline_right = Gst.parse_launch(pipeline_right_str)
                self.appsink_right = self.pipeline_right.get_by_name('sink_right')
                self.appsink_right.connect('new-sample', self._on_new_sample_right)

                # Start both pipelines
                ret_left = self.pipeline_left.set_state(Gst.State.PLAYING)
                ret_right = self.pipeline_right.set_state(Gst.State.PLAYING)

                if ret_left == Gst.StateChangeReturn.FAILURE or ret_right == Gst.StateChangeReturn.FAILURE:
                    logger.error("Failed to start one or both GStreamer pipelines")
                    return False

                self.running = True
                print(f"✓ Dual CSI cameras started successfully")
                logger.info(f"Dual CSI cameras started: sensor {self.sensor_id_left} and {self.sensor_id_right}")
                return True

            else:
                # Single camera mode (fallback)
                logger.error("Single camera mode not implemented")
                return False

        except Exception as e:
            logger.error(f"Failed to start dual cameras: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _on_new_sample_left(self, appsink):
        """Callback for new frame from left camera"""
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

            # Convert to numpy array (same as rear_camera.py)
            frame = np.ndarray(
                shape=(self.height, self.width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )

            # Store frame (make a copy since buffer will be unmapped)
            with self.frame_lock:
                self.current_frame_left = frame.copy()
                self.frame_count += 1

                # Debug: print first few frames
                if self.frame_count <= 5:
                    print(f"[DirectCamera] Left camera frame {self.frame_count}: {frame.shape}, dtype={frame.dtype}, min={frame.min()}, max={frame.max()}")

            # Unmap buffer
            buf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            logger.error(f"Error in left camera callback: {e}")
            return Gst.FlowReturn.ERROR

    def _on_new_sample_right(self, appsink):
        """Callback for new frame from right camera"""
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

            # Convert to numpy array (same as rear_camera.py)
            frame = np.ndarray(
                shape=(self.height, self.width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )

            # Store frame (make a copy since buffer will be unmapped)
            with self.frame_lock:
                self.current_frame_right = frame.copy()

                # Debug: print first few frames
                if self.frame_count <= 5:
                    print(f"[DirectCamera] Right camera frame {self.frame_count}: {frame.shape}, dtype={frame.dtype}, min={frame.min()}, max={frame.max()}")

            # Unmap buffer
            buf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            logger.error(f"Error in right camera callback: {e}")
            return Gst.FlowReturn.ERROR

    def stop(self):
        """Stop dual camera capture"""
        self.running = False
        if self.pipeline_left:
            self.pipeline_left.set_state(Gst.State.NULL)
        if self.pipeline_right:
            self.pipeline_right.set_state(Gst.State.NULL)
        logger.info("Dual cameras stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        """Get current merged frame from both cameras (same BGR->RGB conversion as rear_camera.py)"""
        with self.frame_lock:
            if self.dual_mode:
                # Both frames must be available
                if self.current_frame_left is not None and self.current_frame_right is not None:
                    # Reverse conversion - nvvidconv BGRx actually outputs RGB data
                    left_rgb = cv2.cvtColor(self.current_frame_left, cv2.COLOR_RGB2BGR)
                    right_rgb = cv2.cvtColor(self.current_frame_right, cv2.COLOR_RGB2BGR)

                    # Merge side-by-side (right | left) - swapped to match physical camera positions
                    merged = np.hstack([right_rgb, left_rgb])

                    # Debug first few merged frames
                    if self.frame_count <= 5:
                        print(f"[DirectCamera] get_frame() returning merged: {merged.shape}")

                    return merged
                # If only one frame is available, return it (graceful degradation)
                elif self.current_frame_left is not None:
                    if self.frame_count <= 5:
                        print(f"[DirectCamera] get_frame() returning left only: {self.current_frame_left.shape}")
                    return cv2.cvtColor(self.current_frame_left, cv2.COLOR_RGB2BGR)
                elif self.current_frame_right is not None:
                    if self.frame_count <= 5:
                        print(f"[DirectCamera] get_frame() returning right only: {self.current_frame_right.shape}")
                    return cv2.cvtColor(self.current_frame_right, cv2.COLOR_RGB2BGR)
                else:
                    # Only print first 5 times to avoid spam
                    if self.frame_count <= 5:
                        print(f"[DirectCamera] get_frame() returning None - no frames available yet")
            else:
                # Single camera mode (not used)
                if self.current_frame_left is not None:
                    return cv2.cvtColor(self.current_frame_left, cv2.COLOR_RGB2BGR)
        return None
