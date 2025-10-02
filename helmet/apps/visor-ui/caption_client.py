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

            # Configure transcription options
            options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="linear16",
                channels=1,
                sample_rate=16000,
                punctuate=True,
                interim_results=True,
            )

            # Start connection
            if await dg_connection.start(options) is False:
                logger.error("Failed to start Deepgram connection")
                return

            logger.info("Deepgram connection established")

            # Setup audio stream
            CHUNK = 1024
            audio = pyaudio.PyAudio()

            device_info = audio.get_device_info_by_index(self.device_index or 0)
            logger.info(f"Recording from: {device_info['name']}")

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=CHUNK,
            )

            logger.info("Audio stream started - listening for speech...")

            # Stream audio to Deepgram
            while self.is_running:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    await dg_connection.send(data)
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error sending audio: {e}")
                    break

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
