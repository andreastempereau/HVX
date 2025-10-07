"""Real-time closed caption system using Deepgram"""

import os
import threading
import queue
import logging
from typing import Callable, Optional
import asyncio

logger = logging.getLogger(__name__)


class CaptionClient:
    """Real-time speech-to-text using Deepgram"""

    def __init__(self, deepgram_api_key: str, device_index: Optional[int] = None, parent_app=None):
        self.deepgram_api_key = deepgram_api_key
        self.device_index = device_index
        self.parent_app = parent_app  # Reference to VisorApp for Qt signal

        self.is_running = False
        self.callback = None
        self.thread = None

        # Deepgram connection
        self.dg_connection = None

        logger.info("Caption client initialized")

    def start(self, callback: Callable[[str, bool], None]):
        """
        Start capturing and transcribing audio
        callback(text, is_final) - is_final indicates if this is a final transcript
        """
        if self.is_running:
            return

        self.callback = callback
        self.is_running = True

        # Start Deepgram in a separate thread
        self.thread = threading.Thread(target=self._run_deepgram, daemon=True)
        self.thread.start()

        logger.info("Caption client started")

    def stop(self):
        """Stop transcription"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Caption client stopped")

    def _run_deepgram(self):
        """Run Deepgram transcription in async loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._deepgram_stream())

    async def _deepgram_stream(self):
        """Stream audio to Deepgram for real-time transcription"""
        try:
            from deepgram import (
                DeepgramClient,
                DeepgramClientOptions,
                LiveTranscriptionEvents,
                LiveOptions,
            )
            import pyaudio

            # Setup Deepgram
            config = DeepgramClientOptions(
                options={"keepalive": "true"}
            )
            deepgram = DeepgramClient(self.deepgram_api_key, config)

            dg_connection = deepgram.listen.asynclive.v("1")

            # Capture parent_app in closure
            parent_app = self.parent_app

            # Handle transcription events
            async def on_message(self, result, **kwargs):
                sentence = result.channel.alternatives[0].transcript

                if len(sentence) == 0:
                    return

                is_final = result.is_final

                logger.info(f"Deepgram caption: '{sentence}' (final={is_final})")
                print(f"Caption: {sentence}")

                # Send caption directly to UI via Qt signal (thread-safe)
                if parent_app:
                    try:
                        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                        print(f"Attempting to invoke _emit_caption_signal on main thread...")
                        # Invoke on main Qt thread
                        invoke_result = QMetaObject.invokeMethod(
                            parent_app,
                            "_emit_caption_signal",
                            Qt.QueuedConnection,
                            Q_ARG(str, sentence),
                            Q_ARG(bool, is_final)
                        )
                        print(f"QMetaObject.invokeMethod result: {invoke_result}")
                    except Exception as e:
                        import traceback
                        print(f"Error emitting caption signal: {e}")
                        traceback.print_exc()
                else:
                    print("WARNING: No parent_app set!")

            async def on_error(self, error, **kwargs):
                logger.error(f"Deepgram error: {error}")

            # Register event handlers
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)

            # Configure transcription options - OPTIMIZED for lower latency
            options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="linear16",
                channels=1,
                sample_rate=16000,  # Will be updated to match actual audio rate
                punctuate=True,
                interim_results=True,  # Keep interim results for responsiveness
                endpointing=300,  # Reduced from 1500ms - faster finalization
                vad_events=True,  # Enable voice activity detection
                utterance_end_ms=1000,  # End utterance after 1s silence (reduced from default)
            )

            # Start connection (will be updated with correct sample rate below)
            logger.info("Preparing Deepgram connection...")

            # Setup audio stream - OPTIMIZED for low latency
            CHUNK = 512  # Smaller chunks = lower latency (reduced from 1024)
            audio = pyaudio.PyAudio()

            device_info = audio.get_device_info_by_index(self.device_index or 0)
            logger.info(f"Recording from: {device_info['name']}")

            # Skip sample rate probing - just use 16kHz (Deepgram's preferred rate)
            # If it fails, fall back to device default
            supported_rate = 16000
            device_default_rate = int(device_info.get('defaultSampleRate', 44100))

            try:
                # Try 16kHz first (optimal for Deepgram)
                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=CHUNK,
                )
                supported_rate = 16000
                logger.info(f"Using sample rate: {supported_rate}Hz")
                print(f"Audio: Using sample rate {supported_rate}Hz")
            except Exception as e:
                # Fallback to device default rate
                logger.info(f"16kHz not supported, falling back to {device_default_rate}Hz")
                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=device_default_rate,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=CHUNK,
                )
                supported_rate = device_default_rate
                print(f"Audio: Using fallback sample rate {supported_rate}Hz")

            # Update Deepgram options with actual sample rate
            options.sample_rate = supported_rate

            # Start Deepgram connection with correct sample rate
            if await dg_connection.start(options) is False:
                logger.error("Failed to start Deepgram connection")
                stream.stop_stream()
                stream.close()
                audio.terminate()
                return

            logger.info(f"Deepgram connection established with {supported_rate}Hz audio")
            logger.info("Audio stream started - listening for speech...")

            # Stream audio to Deepgram - OPTIMIZED non-blocking
            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            loop = asyncio.get_event_loop()

            while self.is_running:
                try:
                    # Read audio in thread pool to avoid blocking event loop
                    data = await loop.run_in_executor(
                        executor,
                        lambda: stream.read(CHUNK, exception_on_overflow=False)
                    )
                    await dg_connection.send(data)
                    # No sleep needed - executor handles blocking
                except Exception as e:
                    logger.error(f"Error sending audio: {e}")
                    break

            executor.shutdown(wait=False)

            # Cleanup
            stream.stop_stream()
            stream.close()
            await dg_connection.finish()
            audio.terminate()

            logger.info("Deepgram stream closed")

        except ImportError as e:
            logger.error(f"Missing dependencies: {e}")
            logger.error("Install: pip install deepgram-sdk pyaudio")
            print(f"ERROR: Missing dependencies: {e}")
        except Exception as e:
            logger.error(f"Deepgram stream error: {e}")
            print(f"ERROR: Deepgram stream error: {e}")
