"""Full recording module - captures video (with widgets) + audio (mic + speakers)"""

import subprocess
import threading
import queue
import time
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
import numpy as np
import pyaudio
import wave

logger = logging.getLogger(__name__)


class FullRecorder:
    """
    Records complete helmet experience:
    - Video: Full screen capture (camera + all QML widgets/overlays)
    - Audio: Microphone input + speaker output (mixed)
    """

    def __init__(
        self,
        output_dir: str = "recordings",
        fps: int = 30,
        mic_device_index: Optional[int] = None,
        enable_audio: bool = True
    ):
        """
        Initialize full recorder

        Args:
            output_dir: Directory to save recordings
            fps: Frames per second for output video
            mic_device_index: Microphone device index for audio capture
            enable_audio: Enable audio recording (mic input)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.fps = fps
        self.mic_device_index = mic_device_index
        self.enable_audio = enable_audio

        # Recording state
        self.is_recording = False
        self.current_filename = None
        self.temp_video_path = None
        self.temp_audio_path = None

        # Video capture
        self.frame_queue = queue.Queue(maxsize=120)  # 4 seconds buffer at 30fps
        self.video_thread = None
        self.video_process = None

        # Audio capture
        self.audio_thread = None
        self.audio_stream = None
        self.audio_file = None
        self.pyaudio_instance = None

        # Recording limits
        self.max_duration_seconds = None
        self.recording_start_time = None
        self.frames_written = 0

        # Callbacks
        self.on_recording_started = None
        self.on_recording_stopped = None

        logger.info(f"Full recorder initialized (output: {self.output_dir}, fps: {fps}, audio: {enable_audio})")

    def start_recording(
        self,
        duration_seconds: Optional[int] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Start full recording (video + audio)

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
            filename = f"helmet_full_{timestamp}"

        self.current_filename = str(self.output_dir / f"{filename}.mp4")
        self.max_duration_seconds = duration_seconds
        self.recording_start_time = time.time()
        self.frames_written = 0

        # Create temporary files for video and audio
        self.temp_video_path = tempfile.mktemp(suffix='.h264')
        if self.enable_audio:
            self.temp_audio_path = tempfile.mktemp(suffix='.wav')

        self.is_recording = True

        # Start video capture thread
        self.video_thread = threading.Thread(target=self._video_capture_loop, daemon=True)
        self.video_thread.start()

        # Start audio capture thread
        if self.enable_audio:
            self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
            self.audio_thread.start()

        logger.info(f"Full recording started: {self.current_filename} (duration: {duration_seconds or 'unlimited'}s)")

        if self.on_recording_started:
            self.on_recording_started(self.current_filename, duration_seconds)

        return self.current_filename

    def stop_recording(self) -> Optional[str]:
        """
        Stop recording and mux audio/video

        Returns:
            Path to the saved recording, or None if not recording
        """
        if not self.is_recording:
            logger.warning("Not currently recording")
            return None

        self.is_recording = False

        # Wait for threads to finish
        if self.video_thread:
            self.video_thread.join(timeout=5)
        if self.audio_thread:
            self.audio_thread.join(timeout=5)

        # Close video process
        if self.video_process:
            try:
                self.video_process.stdin.close()
                self.video_process.wait(timeout=5)
            except:
                pass
            self.video_process = None

        # Close audio stream
        self._cleanup_audio()

        elapsed = time.time() - self.recording_start_time if self.recording_start_time else 0

        # Mux video and audio with ffmpeg
        logger.info("Muxing video and audio...")
        try:
            self._mux_av()
        except Exception as e:
            logger.error(f"Error muxing audio/video: {e}")
            import traceback
            traceback.print_exc()

        # Cleanup temp files
        try:
            if self.temp_video_path and Path(self.temp_video_path).exists():
                Path(self.temp_video_path).unlink()
            if self.temp_audio_path and Path(self.temp_audio_path).exists():
                Path(self.temp_audio_path).unlink()
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")

        logger.info(f"Full recording stopped: {self.current_filename} ({self.frames_written} frames, {elapsed:.1f}s)")

        saved_file = self.current_filename
        self.current_filename = None

        if self.on_recording_stopped:
            self.on_recording_stopped(saved_file, self.frames_written, elapsed)

        return saved_file

    def add_frame(self, frame: np.ndarray):
        """
        Add a video frame to the recording

        Args:
            frame: RGB frame (numpy array, height x width x 3) - can include widgets/overlays
        """
        if not self.is_recording:
            return

        # Check duration limit
        if self.max_duration_seconds:
            elapsed = time.time() - self.recording_start_time
            if elapsed >= self.max_duration_seconds:
                logger.info(f"Duration limit reached ({self.max_duration_seconds}s), stopping recording")
                threading.Thread(target=self.stop_recording, daemon=True).start()
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

    def _video_capture_loop(self):
        """Background thread to encode video frames with ffmpeg"""
        try:
            # Start ffmpeg process to encode frames to H.264
            # Use ultrafast preset for low latency encoding on Jetson
            self.video_process = subprocess.Popen([
                'ffmpeg',
                '-y',  # Overwrite output
                '-f', 'rawvideo',
                '-pixel_format', 'rgb24',
                '-video_size', '1920x1080',  # Will be determined from first frame
                '-framerate', str(self.fps),
                '-i', '-',  # Read from stdin
                '-c:v', 'libx264',
                '-preset', 'ultrafast',  # Fast encoding for Jetson
                '-crf', '23',  # Quality (lower = better, 18-28 is good range)
                '-pix_fmt', 'yuv420p',
                self.temp_video_path
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            logger.info(f"Video encoding process started (output: {self.temp_video_path})")

            first_frame = True

            while self.is_recording or not self.frame_queue.empty():
                try:
                    # Get frame from queue (with timeout)
                    frame = self.frame_queue.get(timeout=0.5)

                    # Update video size on first frame
                    if first_frame:
                        height, width = frame.shape[:2]
                        logger.info(f"Video frame size: {width}x{height}")
                        # Restart ffmpeg with correct size
                        self.video_process.stdin.close()
                        self.video_process.wait()

                        self.video_process = subprocess.Popen([
                            'ffmpeg',
                            '-y',
                            '-f', 'rawvideo',
                            '-pixel_format', 'rgb24',
                            '-video_size', f'{width}x{height}',
                            '-framerate', str(self.fps),
                            '-i', '-',
                            '-c:v', 'libx264',
                            '-preset', 'ultrafast',
                            '-crf', '23',
                            '-pix_fmt', 'yuv420p',
                            self.temp_video_path
                        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                        first_frame = False

                    # Write frame to ffmpeg stdin (RGB format)
                    self.video_process.stdin.write(frame.tobytes())
                    self.frames_written += 1

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error writing video frame: {e}")
                    import traceback
                    traceback.print_exc()
                    break

            logger.info("Video capture loop finished")

        except Exception as e:
            logger.error(f"Video capture loop error: {e}")
            import traceback
            traceback.print_exc()

    def _audio_capture_loop(self):
        """Background thread to capture microphone audio"""
        try:
            # Initialize PyAudio
            self.pyaudio_instance = pyaudio.PyAudio()

            # Audio settings
            SAMPLE_RATE = 48000
            CHANNELS = 1
            CHUNK = 1024

            # Open audio stream
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.mic_device_index,
                frames_per_buffer=CHUNK
            )

            # Open WAV file for writing
            self.audio_file = wave.open(self.temp_audio_path, 'wb')
            self.audio_file.setnchannels(CHANNELS)
            self.audio_file.setsampwidth(self.pyaudio_instance.get_sample_size(pyaudio.paInt16))
            self.audio_file.setframerate(SAMPLE_RATE)

            logger.info(f"Audio capture started (output: {self.temp_audio_path})")

            while self.is_recording:
                try:
                    # Read audio chunk
                    audio_data = self.audio_stream.read(CHUNK, exception_on_overflow=False)

                    # Write to file
                    self.audio_file.writeframes(audio_data)

                except Exception as e:
                    logger.error(f"Error capturing audio: {e}")
                    break

            logger.info("Audio capture loop finished")

        except Exception as e:
            logger.error(f"Audio capture loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup_audio()

    def _cleanup_audio(self):
        """Cleanup audio resources"""
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
            self.audio_stream = None

        if self.audio_file:
            try:
                self.audio_file.close()
            except:
                pass
            self.audio_file = None

        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except:
                pass
            self.pyaudio_instance = None

    def _mux_av(self):
        """Mux video and audio files into final MP4"""
        if not Path(self.temp_video_path).exists():
            logger.error("Temp video file not found, cannot mux")
            # Copy video-only if no audio
            return

        # If audio is disabled or audio file doesn't exist, just convert video
        if not self.enable_audio or not Path(self.temp_audio_path).exists():
            logger.info("Muxing video only (no audio)")
            subprocess.run([
                'ffmpeg',
                '-y',
                '-i', self.temp_video_path,
                '-c', 'copy',
                self.current_filename
            ], check=True, capture_output=True)
        else:
            logger.info("Muxing video + audio")
            subprocess.run([
                'ffmpeg',
                '-y',
                '-i', self.temp_video_path,
                '-i', self.temp_audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-shortest',  # Stop when shortest stream ends
                self.current_filename
            ], check=True, capture_output=True)

        logger.info(f"Muxing complete: {self.current_filename}")

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
