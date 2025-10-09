"""Video recording module for helmet camera feeds"""

import cv2
import numpy as np
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class VideoRecorder:
    """Record video from camera frames with configurable duration and quality"""

    def __init__(self, output_dir: str = "recordings", fps: int = 30, codec: str = "mp4v"):
        """
        Initialize video recorder

        Args:
            output_dir: Directory to save recordings
            fps: Frames per second for output video
            codec: FourCC codec code (mp4v, avc1, xvid, etc.)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.fps = fps
        self.codec = codec
        self.fourcc = cv2.VideoWriter_fourcc(*codec)

        # Recording state
        self.is_recording = False
        self.video_writer = None
        self.current_filename = None
        self.frame_queue = queue.Queue(maxsize=120)  # 4 seconds buffer at 30fps
        self.write_thread = None

        # Recording limits
        self.max_duration_seconds = None
        self.recording_start_time = None
        self.frames_written = 0

        # Callbacks
        self.on_recording_started = None
        self.on_recording_stopped = None

        logger.info(f"Video recorder initialized (output: {self.output_dir}, fps: {fps}, codec: {codec})")

    def start_recording(
        self,
        duration_seconds: Optional[int] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Start recording video

        Args:
            duration_seconds: Optional max duration in seconds (None = unlimited)
            filename: Optional custom filename (without extension)

        Returns:
            Path to the recording file
        """
        if self.is_recording:
            logger.warning("Already recording")
            return self.current_filename

        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"helmet_recording_{timestamp}"

        self.current_filename = str(self.output_dir / f"{filename}.mp4")
        self.max_duration_seconds = duration_seconds
        self.recording_start_time = time.time()
        self.frames_written = 0

        self.is_recording = True

        # Start writer thread
        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()

        logger.info(f"Recording started: {self.current_filename} (duration: {duration_seconds or 'unlimited'}s)")

        if self.on_recording_started:
            self.on_recording_started(self.current_filename, duration_seconds)

        return self.current_filename

    def stop_recording(self) -> Optional[str]:
        """
        Stop recording and finalize video file

        Returns:
            Path to the saved recording, or None if not recording
        """
        if not self.is_recording:
            logger.warning("Not currently recording")
            return None

        self.is_recording = False

        # Wait for write thread to finish
        if self.write_thread:
            self.write_thread.join(timeout=5)

        # Close video writer
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        elapsed = time.time() - self.recording_start_time if self.recording_start_time else 0

        logger.info(f"Recording stopped: {self.current_filename} ({self.frames_written} frames, {elapsed:.1f}s)")

        saved_file = self.current_filename
        self.current_filename = None

        if self.on_recording_stopped:
            self.on_recording_stopped(saved_file, self.frames_written, elapsed)

        return saved_file

    def add_frame(self, frame: np.ndarray):
        """
        Add a frame to the recording

        Args:
            frame: RGB frame (numpy array, height x width x 3)
        """
        if not self.is_recording:
            return

        # Check duration limit
        if self.max_duration_seconds:
            elapsed = time.time() - self.recording_start_time
            if elapsed >= self.max_duration_seconds:
                logger.info(f"Duration limit reached ({self.max_duration_seconds}s), stopping recording")
                self.stop_recording()
                return

        # Add to queue (non-blocking, drop oldest if full)
        try:
            self.frame_queue.put_nowait(frame.copy())
        except queue.Full:
            # Drop oldest frame and add new one
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame.copy())
                logger.warning("Frame queue full, dropped oldest frame")
            except:
                pass

    def _write_loop(self):
        """Background thread to write frames to video file"""
        try:
            while self.is_recording or not self.frame_queue.empty():
                try:
                    # Get frame from queue (with timeout)
                    frame = self.frame_queue.get(timeout=0.5)

                    # Initialize video writer on first frame
                    if self.video_writer is None:
                        height, width = frame.shape[:2]
                        logger.info(f"Initializing video writer: {width}x{height} @ {self.fps}fps")

                        self.video_writer = cv2.VideoWriter(
                            self.current_filename,
                            self.fourcc,
                            self.fps,
                            (width, height)
                        )

                        if not self.video_writer.isOpened():
                            logger.error("Failed to open video writer")
                            self.is_recording = False
                            return

                    # Convert RGB to BGR for OpenCV
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                    # Write frame
                    self.video_writer.write(frame_bgr)
                    self.frames_written += 1

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error writing frame: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            logger.error(f"Write loop error: {e}")
            import traceback
            traceback.print_exc()

        logger.info("Write loop finished")

    def is_recording_active(self) -> bool:
        """Check if currently recording"""
        return self.is_recording

    def get_recording_info(self) -> dict:
        """Get current recording information"""
        if not self.is_recording:
            return {
                'recording': False,
                'filename': None,
                'duration': 0,
                'frames': 0
            }

        elapsed = time.time() - self.recording_start_time if self.recording_start_time else 0

        return {
            'recording': True,
            'filename': self.current_filename,
            'duration': elapsed,
            'frames': self.frames_written,
            'max_duration': self.max_duration_seconds
        }


if __name__ == "__main__":
    """Test video recorder"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Video Recorder Test")
    print("="*60)

    # Create test recorder
    recorder = VideoRecorder(output_dir="/tmp/test_recordings", fps=10)

    def on_started(filename, duration):
        print(f"\n✓ Recording started: {filename}")
        if duration:
            print(f"  Max duration: {duration}s")

    def on_stopped(filename, frames, duration):
        print(f"\n✓ Recording stopped: {filename}")
        print(f"  Frames: {frames}")
        print(f"  Duration: {duration:.1f}s")

    recorder.on_recording_started = on_started
    recorder.on_recording_stopped = on_stopped

    # Test 1: Short recording with synthetic frames
    print("\nTest 1: 3-second recording with synthetic frames")
    print("-"*60)

    recorder.start_recording(duration_seconds=3, filename="test_recording")

    # Generate synthetic frames (640x480 RGB)
    for i in range(30):  # 30 frames at 10fps = 3 seconds
        # Create a test pattern (gradient)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :, 0] = (i * 8) % 256  # Red channel changes over time
        frame[:, :, 1] = 128  # Green constant
        frame[:, :, 2] = 255 - (i * 8) % 256  # Blue inverse

        # Add frame number text
        cv2.putText(
            frame,
            f"Frame {i+1}/30",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        recorder.add_frame(frame)
        time.sleep(0.1)  # 10fps

    # Wait for duration limit to trigger stop
    time.sleep(1)

    # Test 2: Manual stop
    print("\n\nTest 2: Manual stop after 1 second")
    print("-"*60)

    recorder.start_recording(filename="test_manual_stop")

    for i in range(10):  # 10 frames
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :, 1] = 255  # All green
        cv2.putText(
            frame,
            f"Frame {i+1}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        recorder.add_frame(frame)
        time.sleep(0.1)

    saved_file = recorder.stop_recording()

    print(f"\n\nTest complete!")
    print(f"Check recordings in: /tmp/test_recordings/")
