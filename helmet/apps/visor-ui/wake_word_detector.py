"""Lightweight wake word detection using openWakeWord"""

import threading
import logging
from typing import Callable, Optional
import numpy as np

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Lightweight wake word detector using openWakeWord (works on Jetson)"""

    def __init__(
        self,
        access_key: str = None,  # Not needed for openWakeWord, kept for compatibility
        keywords: list = None,
        device_index: Optional[int] = None,
    ):
        """
        Initialize wake word detector

        Args:
            access_key: Not used (kept for API compatibility)
            keywords: List of wake words - supports: "alexa", "hey_jarvis", "hey_mycroft", "ok_naomi"
            device_index: Audio input device index
        """
        self.keywords = keywords or ["hey_jarvis"]  # Default wake word
        self.device_index = device_index

        self.is_running = False
        self.callback = None
        self.thread = None
        self.owwModel = None
        self.audio_stream = None
        self.pyaudio_instance = None

        logger.info(f"Wake word detector initialized with keywords: {self.keywords}")

    def start(self, callback: Callable[[str], None]):
        """
        Start wake word detection

        Args:
            callback: Function called when wake word detected, receives keyword string
        """
        if self.is_running:
            return

        self.callback = callback
        self.is_running = True

        # Start detection in separate thread
        self.thread = threading.Thread(target=self._run_detection, daemon=True)
        self.thread.start()

        logger.info("Wake word detector started")

    def stop(self):
        """Stop wake word detection"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)

        self._cleanup_audio()
        logger.info("Wake word detector stopped")

    def pause(self):
        """Pause wake word detection (release microphone)"""
        if self.audio_stream:
            print("[Wake Word] Pausing - releasing microphone...")
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
        logger.info("Wake word detector paused (mic released)")

    def resume(self):
        """Resume wake word detection (reacquire microphone)"""
        # This will be handled automatically when the detection loop sees audio_stream is None
        print("[Wake Word] Resuming - will reacquire microphone...")
        logger.info("Wake word detector resuming")

    def _cleanup_audio(self):
        """Cleanup audio resources"""
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
            self.audio_stream = None
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except:
                pass
            self.pyaudio_instance = None

    def _run_detection(self):
        """Run wake word detection loop"""
        try:
            from openwakeword.model import Model
            import pyaudio

            print(f"[Wake Word] Initializing model for keywords: {self.keywords}")

            # Create openWakeWord model
            self.owwModel = Model(
                wakeword_models=self.keywords,
                inference_framework="tflite"  # Use TFLite (models are .tflite format)
            )

            logger.info(f"openWakeWord initialized:")
            logger.info(f"  Models loaded: {list(self.owwModel.models.keys())}")
            print(f"[Wake Word] Models loaded: {list(self.owwModel.models.keys())}")

            # Setup audio stream (16kHz required by openWakeWord)
            # Auto-detect supported sample rate and resample if needed
            TARGET_RATE = 16000  # openWakeWord requires 16kHz
            CHUNK_16K = 1280  # 80ms at 16kHz

            self.pyaudio_instance = pyaudio.PyAudio()

            # Try 16kHz first, then fallback to higher rates with resampling
            self.native_rate = TARGET_RATE
            self.needs_resampling = False

            for test_rate in [16000, 48000, 44100]:
                try:
                    chunk_native = int(CHUNK_16K * test_rate / TARGET_RATE)
                    print(f"[Wake Word] Testing {test_rate}Hz...")
                    self.audio_stream = self.pyaudio_instance.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=test_rate,
                        input=True,
                        input_device_index=self.device_index,
                        frames_per_buffer=chunk_native,
                    )
                    self.native_rate = test_rate
                    self.needs_resampling = (test_rate != TARGET_RATE)
                    print(f"[Wake Word] ✓ Audio opened: {test_rate}Hz (resample={self.needs_resampling})")
                    break
                except Exception as e:
                    if test_rate == 44100:  # Last attempt
                        raise
                    continue

            print(f"[Wake Word] Listening for: {', '.join(self.keywords)} (threshold: 0.5)")
            logger.info(f"Audio stream started - listening for wake words")

            frame_count = 0
            # Detection loop
            while self.is_running:
                try:
                    # Check if audio stream is still open (may be paused)
                    if not self.audio_stream:
                        import time
                        time.sleep(0.1)
                        continue

                    # Read audio frame at native rate
                    TARGET_RATE = 16000
                    chunk_native = int(1280 * self.native_rate / TARGET_RATE)
                    audio_data = self.audio_stream.read(chunk_native, exception_on_overflow=False)

                    # Convert to numpy array
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)

                    # Resample to 16kHz if needed
                    if self.needs_resampling:
                        from scipy import signal as scipy_signal
                        num_samples_16k = int(len(audio_array) * TARGET_RATE / self.native_rate)
                        audio_array = scipy_signal.resample(audio_array, num_samples_16k).astype(np.int16)

                    # Process frame - returns dict of predictions
                    prediction = self.owwModel.predict(audio_array)

                    frame_count += 1

                    # Debug: Print scores every 50 frames (~4 seconds)
                    if frame_count % 50 == 0:
                        scores_str = ", ".join([f"{k}: {v:.3f}" for k, v in prediction.items()])
                        print(f"[Wake Word Debug] Frame {frame_count}: {scores_str}")

                    # Check if any wake word detected (threshold 0.5)
                    for keyword, score in prediction.items():
                        if score > 0.5:
                            detected_keyword = keyword
                            logger.info(f"Wake word detected: {detected_keyword} (score: {score:.2f})")
                            print(f"\n🎤 [Wake Word] DETECTED: '{detected_keyword}' (confidence: {score:.2f})\n")

                            # Pause detection and call callback
                            if self.callback:
                                # Release microphone before calling callback
                                self.pause()
                                self.callback(detected_keyword)

                except Exception as e:
                    logger.error(f"Error processing audio frame: {e}")
                    print(f"[Wake Word Error] {e}")
                    continue

            # Cleanup
            self._cleanup_audio()

            logger.info("Wake word detection stopped")

        except ImportError:
            logger.error("openwakeword not installed. Install: pip install openwakeword")
            print("ERROR: openwakeword not installed. Run: pip install openwakeword")
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            print(f"ERROR: Wake word detection failed: {e}")
            import traceback
            traceback.print_exc()
