#!/usr/bin/env python3
"""Video capture and streaming service with GStreamer support"""

import asyncio
import logging
import threading
import time
from concurrent import futures
from pathlib import Path
import sys
import cv2
import numpy as np
from typing import Optional, Iterator

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

# Add libs to path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from utils.config import get_config
from utils.logging_utils import setup_logging, log_performance
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class VideoCapture:
    """Video capture abstraction supporting mock files and real cameras"""

    def __init__(self, config):
        self.config = config
        self.cap = None
        self.frame_id = 0
        self.lock = threading.Lock()
        self._setup_capture()

    def _setup_capture(self):
        """Initialize video capture based on configuration"""
        try:
            camera_type = self.config.get('video.camera_type', 'webcam')  # webcam, file, csi

            if camera_type == 'file':
                # Video file source (for testing with sample footage)
                source_path = self.config.get('video.source_path', 'demo.mp4')
                if not Path(source_path).exists():
                    logger.warning(f"Video file not found: {source_path}, falling back to webcam")
                    camera_type = 'webcam'
                else:
                    logger.info(f"Using video file: {source_path}")
                    self.cap = cv2.VideoCapture(source_path)
                    # Loop video file
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            if camera_type == 'webcam':
                # Windows webcam / USB camera (development)
                camera_id = self.config.get('video.camera_id', 0)
                logger.info(f"Connecting to webcam ID: {camera_id}")

                # On Windows, try DirectShow backend for better compatibility
                import platform
                if platform.system() == 'Windows':
                    self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                else:
                    self.cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

                # Force MJPEG format to avoid YUYV conversion issues
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))

            elif camera_type == 'csi':
                # CSI camera on Jetson (production)
                sensor_id = self.config.get('video.csi_sensor_id', 0)
                width = self.config.get('video.width', 1920)
                height = self.config.get('video.height', 1080)
                fps = self.config.get('video.fps', 30)

                # GStreamer pipeline for IMX219 CSI camera
                gst_pipeline = (
                    f"nvarguscamerasrc sensor-id={sensor_id} ! "
                    f"video/x-raw(memory:NVMM), width={width}, height={height}, "
                    f"format=NV12, framerate={fps}/1 ! "
                    f"nvvideoconvert flip-method=0 ! "
                    f"video/x-raw, width={width}, height={height}, format=BGRx ! "
                    f"videoconvert ! "
                    f"video/x-raw, format=BGR ! appsink max-buffers=1 drop=true"
                )

                logger.info(f"Using CSI camera with GStreamer: {gst_pipeline}")
                self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

            # Set capture properties (for webcam/USB cameras)
            if camera_type in ['webcam', 'file']:
                width = self.config.get('video.width', 1920)
                height = self.config.get('video.height', 1080)
                fps = self.config.get('video.fps', 30)

                # Try to set properties, but don't fail if unsupported
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    self.cap.set(cv2.CAP_PROP_FPS, fps)

                except Exception as prop_error:
                    logger.warning(f"Could not set camera properties: {prop_error}")

                # Get actual properties
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

                logger.info(f"Camera properties - Requested: {width}x{height}@{fps}fps")
                logger.info(f"Camera properties - Actual: {actual_width}x{actual_height}@{actual_fps}fps")

            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open {camera_type} camera")

            # Test capture with retries (camera needs warm-up time)
            # Flush initial frames from buffer
            for _ in range(5):
                self.cap.grab()

            test_success = False
            for attempt in range(10):
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None and test_frame.size > 0:
                    logger.info(f"Video capture test successful: {test_frame.shape}")
                    test_success = True
                    break
                else:
                    logger.warning(f"Frame read attempt {attempt + 1} failed, retrying...")
                    time.sleep(0.5)

            if not test_success:
                logger.error("Video capture test failed after 10 attempts")
                raise RuntimeError("Unable to read frames from camera")

            logger.info(f"Video capture initialized successfully with {camera_type} camera")

        except Exception as e:
            logger.error(f"Failed to setup video capture: {e}")
            # Final fallback to default webcam
            logger.info("Attempting fallback to default webcam...")
            try:
                self.cap = cv2.VideoCapture(0)
                if self.cap.isOpened():
                    logger.info("Fallback webcam connected successfully")
                else:
                    raise RuntimeError("No video source available")
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise RuntimeError("No video source available")

    @log_performance("frame_capture")
    def get_frame(self) -> Optional[helmet_pb2.FrameMeta]:
        """Capture a single frame"""
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                logger.error("Camera not opened, attempting to reconnect...")
                self._setup_capture()
                if not self.cap or not self.cap.isOpened():
                    return None

            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame from camera, retrying...")
                # Try one more time with a small delay
                time.sleep(0.1)
                ret, frame = self.cap.read()

                if not ret or frame is None:
                    # Loop video file if using file source
                    if self.config.get('video.camera_type', 'webcam') == 'file':
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                        if not ret:
                            logger.error("Failed to read frame even after loop")
                            return None
                    else:
                        # Webcam might be frozen, try to reinitialize
                        logger.warning("Camera appears frozen, reinitializing...")
                        self.cap.release()
                        time.sleep(0.5)
                        self._setup_capture()

                        if self.cap and self.cap.isOpened():
                            ret, frame = self.cap.read()
                            if not ret or frame is None:
                                logger.error("Failed to read frame after reinitialization")
                                return None
                        else:
                            logger.error("Failed to reinitialize camera")
                            return None

            logger.debug(f"Successfully captured frame: {frame.shape}")

            # Fix YUYV misinterpretation (camera outputs YUYV but OpenCV reads as BGR)
            # Check if we have the YUYV problem (only green channel has data)
            if frame[:,:,0].max() < 10 and frame[:,:,2].max() < 10 and frame[:,:,1].max() > 10:
                logger.info("Detected YUYV format, extracting luminance channel")
                # Extract Y (luminance) channel from green channel and convert to RGB
                gray = frame[:,:,1]
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            elif self.config.get('video.format', 'RGB') == 'RGB':
                # Normal BGR to RGB conversion
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create protobuf message
            frame_meta = helmet_pb2.FrameMeta()
            frame_meta.frame_id = self.frame_id
            frame_meta.width = frame.shape[1]
            frame_meta.height = frame.shape[0]
            frame_meta.format = self.config.get('video.format', 'RGB')
            frame_meta.data = frame.tobytes()

            # Set timestamp
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            frame_meta.timestamp.CopyFrom(timestamp)

            self.frame_id += 1
            return frame_meta

    def release(self):
        """Release video capture resources"""
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
                logger.info("Video capture released")

class VideoServiceImpl(helmet_pb2_grpc.VideoServiceServicer):
    """gRPC video service implementation"""

    def __init__(self, config):
        self.config = config
        self.capture = VideoCapture(config)
        self._streaming = False
        logger.info("Video service initialized")

    def GetFrame(self, request, context):
        """Get a single frame"""
        try:
            frame_meta = self.capture.get_frame()
            if frame_meta is None:
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("No frame available")
                return helmet_pb2.FrameMeta()

            return frame_meta
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return helmet_pb2.FrameMeta()

    def StreamFrames(self, request, context):
        """Stream frames continuously"""
        logger.info("Starting frame stream")
        self._streaming = True

        target_fps = self.config.get('video.fps', 30)
        frame_time = 1.0 / target_fps

        try:
            while self._streaming and context.is_active():
                start_time = time.time()

                frame_meta = self.capture.get_frame()
                if frame_meta is None:
                    logger.warning("No frame available for streaming")
                    continue

                yield frame_meta

                # Maintain target FPS
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_time - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Error in frame stream: {e}")
        finally:
            self._streaming = False
            logger.info("Frame stream ended")

    def shutdown(self):
        """Shutdown the service"""
        self._streaming = False
        if self.capture:
            self.capture.release()

def serve():
    """Start the gRPC server"""
    config = get_config()

    # Setup logging
    log_level = config.get('system.log_level', 'INFO')
    log_dir = Path(config.get('system.log_dir', 'logs'))
    setup_logging('video-service', log_level, log_dir)

    # Create gRPC server with increased message size for high-res frames
    # 50MB max message size to handle high-resolution camera frames
    options = [
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
    ]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options=options)
    video_service = VideoServiceImpl(config)
    helmet_pb2_grpc.add_VideoServiceServicer_to_server(video_service, server)

    # Configure server
    port = config.get('services.video_port', 50051)
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)

    # Start server
    server.start()
    logger.info(f"Video service started on {listen_addr}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        video_service.shutdown()
        server.stop(5)
        logger.info("Video service stopped")

def main():
    """Main entry point"""
    try:
        serve()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()