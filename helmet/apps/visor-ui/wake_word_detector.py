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
        print("[Wake Word] Resuming - will reacquire microphone...", flush=True)
        logger.info("Wake word detector resuming")

        # Wait a moment to let audio streams settle
        import time
        time.sleep(0.3)

        # Reinitialize audio stream
        import pyaudio
        try:
            self.pyaudio_instance = pyaudio.PyAudio()

            TARGET_RATE = 16000
            CHUNK_16K = 1280

            # Try to open at the native rate we used before
            for test_rate in [self.native_rate, 16000, 48000, 44100]:
                try:
                    chunk_native = int(CHUNK_16K * test_rate / TARGET_RATE)
                    print(f"[Wake Word] Reopening audio at {test_rate}Hz on device {self.device_index}...", flush=True)
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
                    dev_info = self.pyaudio_instance.get_device_info_by_index(self.device_index)
                    print(f"[Wake Word] ✓ Audio reopened at {test_rate}Hz on device '{dev_info['name']}'", flush=True)
                    break
                except Exception as e:
                    print(f"[Wake Word]   Failed to reopen at {test_rate}Hz: {e}", flush=True)
                    if test_rate == 44100:
                        print(f"[Wake Word] ERROR: Failed to reopen audio: {e}", flush=True)
                        raise
                    continue

            # Clear audio buffer and add cooldown period
            if self.audio_stream:
                print(f"[Wake Word] Clearing audio buffer and starting cooldown...", flush=True)
                # Drain buffer by reading and discarding frames for 1 second
                frames_to_clear = int(self.native_rate / CHUNK_16K) * 10  # ~1 second worth
                for _ in range(frames_to_clear):
                    try:
                        chunk_size = int(CHUNK_16K * self.native_rate / TARGET_RATE)
                        self.audio_stream.read(chunk_size, exception_on_overflow=False)
                    except:
                        break
                print(f"[Wake Word] Buffer cleared, ready for detection", flush=True)

        except Exception as e:
            print(f"[Wake Word] ERROR resuming: {e}", flush=True)
            import traceback
            traceback.print_exc()

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
        import sys

        # Force unbuffered output for debugging
        try:
            import io
            sys.stdout = io.TextIOWrapper(open(sys.stdout.fileno(), 'wb', 0), write_through=True)
        except Exception as e:
            # If unbuffered output fails, continue anyway
            print(f"[Wake Word] Warning: Could not set unbuffered output: {e}", flush=True)

        print(f"[Wake Word] _run_detection thread started", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()

        try:
            print(f"[Wake Word] Importing openwakeword...", flush=True)
            sys.stdout.flush()
            from openwakeword.model import Model

            print(f"[Wake Word] Importing pyaudio...", flush=True)
            sys.stdout.flush()
            import pyaudio

            print(f"[Wake Word] Initializing model for keywords: {self.keywords}", flush=True)
            sys.stdout.flush()

            # Create openWakeWord model with custom model path
            import os
            model_dir = os.path.expanduser("~/.local/lib/python3.10/site-packages/openwakeword/resources/models")

            # Build list of model paths
            model_paths = []
            for keyword in self.keywords:
                model_file = f"{keyword}_v0.1.tflite"
                model_path = os.path.join(model_dir, model_file)
                if os.path.exists(model_path):
                    model_paths.append(model_path)
                    print(f"[Wake Word] Found model: {model_path}", flush=True)
                else:
                    print(f"[Wake Word] WARNING: Model not found: {model_path}", flush=True)

            if not model_paths:
                raise ValueError(f"No wake word models found for keywords: {self.keywords}")

            self.owwModel = Model(
                wakeword_models=model_paths,
                inference_framework="tflite"  # Use TFLite (models are .tflite format)
            )

            logger.info(f"openWakeWord initialized:")
            logger.info(f"  Models loaded: {list(self.owwModel.models.keys())}")
            print(f"[Wake Word] Models loaded: {list(self.owwModel.models.keys())}", flush=True)
            print(f"[Wake Word] Model details:", flush=True)
            for model_name, model_obj in self.owwModel.models.items():
                print(f"  - {model_name}: {type(model_obj)}", flush=True)

            # Setup audio stream (16kHz required by openWakeWord)
            # Auto-detect supported sample rate and resample if needed
            TARGET_RATE = 16000  # openWakeWord requires 16kHz
            CHUNK_16K = 1280  # 80ms at 16kHz

            print(f"[Wake Word] Initializing PyAudio (this may take a moment)...", flush=True)
            sys.stdout.flush()

            # Suppress ALSA error messages temporarily
            import os
            import ctypes
            ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
            def py_error_handler(filename, line, function, err, fmt):
                pass
            c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
            try:
                asound = ctypes.cdll.LoadLibrary('libasound.so.2')
                asound.snd_lib_error_set_handler(c_error_handler)
            except:
                pass

            self.pyaudio_instance = pyaudio.PyAudio()
            print(f"[Wake Word] PyAudio initialized", flush=True)
            sys.stdout.flush()

            # Find a working input device with proper sample rate support
            original_device = self.device_index
            working_device = None
            working_rate = None

            print(f"[Wake Word] Looking for working audio input...", flush=True)

            # Build device list - specified device first, then others
            devices_to_try = []
            if original_device is not None:
                devices_to_try.append(original_device)

            # Add other input devices as fallback
            for i in range(self.pyaudio_instance.get_device_count()):
                if i not in devices_to_try:
                    try:
                        dev_info = self.pyaudio_instance.get_device_info_by_index(i)
                        if dev_info['maxInputChannels'] > 0:
                            devices_to_try.append(i)
                    except:
                        pass

            # Try each device with multiple sample rates
            for dev_idx in devices_to_try:
                try:
                    dev_info = self.pyaudio_instance.get_device_info_by_index(dev_idx)
                    dev_name = dev_info['name']

                    # Skip internal NVIDIA APE devices (they don't have real mics)
                    if 'APE' in dev_name and dev_idx != original_device:
                        continue

                    print(f"[Wake Word] Trying device {dev_idx}: {dev_name}", flush=True)

                    # Try different sample rates
                    for test_rate in [48000, 44100, 16000]:
                        try:
                            chunk_size = int(1280 * test_rate / 16000)
                            test_stream = self.pyaudio_instance.open(
                                format=pyaudio.paInt16,
                                channels=1,
                                rate=test_rate,
                                input=True,
                                input_device_index=dev_idx,
                                frames_per_buffer=chunk_size,
                            )
                            # Try to read a frame to make sure it works
                            test_data = test_stream.read(chunk_size, exception_on_overflow=False)
                            test_stream.close()

                            working_device = dev_idx
                            working_rate = test_rate
                            print(f"[Wake Word] ✓ Device {dev_idx} works at {test_rate}Hz: {dev_name}", flush=True)
                            break
                        except Exception as e:
                            print(f"[Wake Word]   {test_rate}Hz failed: {e}", flush=True)
                            continue

                    if working_device is not None:
                        break

                except Exception as e:
                    print(f"[Wake Word]   Device {dev_idx} error: {e}", flush=True)
                    continue

            if working_device is None:
                raise RuntimeError("No working audio input device found!")

            self.device_index = working_device
            self.native_rate = working_rate
            self.needs_resampling = (working_rate != TARGET_RATE)

            if original_device is not None and working_device != original_device:
                print(f"[Wake Word] ⚠ Using device {working_device} instead of configured {original_device}", flush=True)

            # Open the audio stream
            chunk_native = int(CHUNK_16K * self.native_rate / TARGET_RATE)
            dev_info = self.pyaudio_instance.get_device_info_by_index(self.device_index)
            print(f"[Wake Word] Opening audio stream...", flush=True)
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.native_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=chunk_native,
            )
            print(f"[Wake Word] ✓ Audio opened: {self.native_rate}Hz on '{dev_info['name']}' (resample={self.needs_resampling})", flush=True)

            print(f"[Wake Word] Listening for wake words (threshold: 0.3)", flush=True)
            for model_path in model_paths:
                print(f"[Wake Word] Listening for: {os.path.basename(model_path)}", flush=True)
            logger.info(f"Audio stream started - listening for wake words")

            frame_count = 0
            print(f"[Wake Word] Starting detection loop...", flush=True)
            print(f"[Wake Word] 🎤 LISTENING - say 'Hey Jarvis' now!", flush=True)

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

                    # Debug first few frames to verify audio capture
                    if frame_count < 3:
                        audio_rms_check = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
                        print(f"[Wake Word] Frame {frame_count}: len={len(audio_array)}, min={np.min(audio_array)}, max={np.max(audio_array)}, RMS={audio_rms_check:.0f}", flush=True)
                        if audio_rms_check < 10:
                            print(f"[Wake Word] ⚠ WARNING: Audio level very low - mic may not be working!", flush=True)

                    # Process frame - returns dict of predictions
                    prediction = self.owwModel.predict(audio_array)

                    frame_count += 1

                    # Calculate audio level (RMS) to verify mic is working
                    audio_rms = np.sqrt(np.mean(audio_array.astype(np.float32)**2))

                    # Debug: Print scores every 25 frames (~2 seconds) with audio level
                    if frame_count % 25 == 0 and frame_count > 0:
                        scores_str = ", ".join([f"{k}: {v:.3f}" for k, v in prediction.items()])
                        status = "🔇 silent" if audio_rms < 50 else "🔊 audio"
                        print(f"[Wake Word] [{status}] Frame {frame_count}: {scores_str} | RMS: {audio_rms:.0f}", flush=True)

                    # Show high scores even between debug intervals
                    max_score = max(prediction.values()) if prediction else 0
                    if max_score > 0.1:  # Show any elevated activity
                        scores_str = ", ".join([f"{k}: {v:.3f}" for k, v in prediction.items()])
                        print(f"[Wake Word] 👂 HEARD SOMETHING: {scores_str} | RMS: {audio_rms:.0f}", flush=True)

                    # Check if any wake word detected (threshold 0.3 - lowered from 0.5 for better sensitivity)
                    # Note: openWakeWord default threshold is 0.5, but we're using 0.3 to catch more detections
                    DETECTION_THRESHOLD = 0.3
                    for keyword, score in prediction.items():
                        if score > DETECTION_THRESHOLD:
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

        except ImportError as e:
            logger.error("openwakeword not installed. Install: pip install openwakeword")
            print(f"ERROR: openwakeword not installed: {e}", flush=True)
            print("Run: pip install openwakeword", flush=True)
            import sys
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            print(f"ERROR: Wake word detection failed: {e}", flush=True)
            import sys
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
