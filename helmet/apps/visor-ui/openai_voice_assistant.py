"""OpenAI Realtime API voice assistant for low-latency voice interaction"""

import os
import asyncio
import json
import base64
import logging
from typing import Optional
import pyaudio
import threading
import queue

logger = logging.getLogger(__name__)


class OpenAIRealtimeAssistant:
    """Voice assistant using OpenAI Realtime API for low-latency speech-to-speech"""

    def __init__(
        self,
        openai_api_key: str,
        system_prompt: Optional[str] = None,
        voice: str = "alloy",  # alloy, echo, fable, onyx, nova, shimmer
        input_device_index: Optional[int] = None,
        output_device_index: Optional[int] = None,
        wake_word_detector=None,  # Reference to wake word detector to resume it
        frame_getter=None,  # Function to get current camera frame on-demand
    ):
        self.openai_api_key = openai_api_key
        self.system_prompt = system_prompt or "You are a helpful AI assistant."
        self.voice = voice
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        self.wake_word_detector = wake_word_detector
        self.frame_getter = frame_getter  # On-demand frame capture

        self.is_running = False
        self.is_active = False  # Activated by wake word detection
        self.websocket = None
        self.thread = None
        self.send_audio_enabled = False  # Controls if we stream mic to OpenAI
        self.is_playing_response = False  # Track if assistant is speaking

        # Audio setup
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        self.audio_queue = queue.Queue()
        self.input_audio_buffer = queue.Queue()  # Buffer for microphone input

        # Dismissal phrases
        self.dismissal_phrases = [
            'okay thanks', 'ok thanks', 'thank you', 'thanks',
            'that\'s all', 'thats all', 'all done', 'done',
            'i don\'t need you', 'don\'t need you', 'go away',
            'dismiss', 'dismissed', 'stop listening', 'never mind',
            'goodbye', 'bye', 'see you later'
        ]

        logger.info("OpenAI Realtime assistant initialized")

    def start(self):
        """Start the voice assistant"""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._run_assistant, daemon=True)
        self.thread.start()
        logger.info("OpenAI Realtime assistant started")

    def stop(self):
        """Stop the voice assistant"""
        self.is_running = False
        self.is_active = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("OpenAI Realtime assistant stopped")

    def activate(self):
        """Activate the assistant (called when wake word detected)"""
        self.is_active = True
        self.send_audio_enabled = True  # Start sending mic audio to OpenAI

        # Initialize audio streams now (mic becomes available after wake word detector releases it)
        if self.audio is None:
            print("[OpenAI Assistant] Initializing audio streams...")
            self._init_audio_lazy()

        print("[OpenAI Assistant] Activated - now listening continuously")
        logger.info("Assistant activated")

    def deactivate(self):
        """Deactivate the assistant and resume wake word detection"""
        self.is_active = False
        self.send_audio_enabled = False  # Stop sending mic audio to OpenAI

        # Close audio streams to release microphone
        if self.input_stream:
            print("[OpenAI Assistant] Closing audio streams...")
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        if self.audio:
            self.audio.terminate()
            self.audio = None

        # Resume wake word detection
        if self.wake_word_detector:
            self.wake_word_detector.resume()

        print("[OpenAI Assistant] Deactivated - microphone released")
        logger.info("Assistant deactivated")


    def process_transcript(self, text: str):
        """Process a transcript from external source (Deepgram)"""
        if not self.is_active:
            return

        # Check for dismissal
        text_lower = text.lower().strip()
        if any(phrase in text_lower for phrase in self.dismissal_phrases):
            self.deactivate()
            # Send dismissal response
            asyncio.run_coroutine_threadsafe(
                self._send_text_message("Understood, Sir. I'll be here if you need me."),
                self.loop
            )
            return

        # Send to OpenAI
        asyncio.run_coroutine_threadsafe(
            self._send_text_message(text),
            self.loop
        )

    def _run_assistant(self):
        """Run the assistant in an async loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self._connect_and_run())
        except Exception as e:
            logger.error(f"Error in assistant loop: {e}")
            import traceback
            traceback.print_exc()

    async def _connect_and_run(self):
        """Connect to OpenAI Realtime API and run - with auto-reconnect"""
        retry_count = 0
        max_retries = 3

        while self.is_running and retry_count < max_retries:
            try:
                import websockets

                # Setup audio (lazy init - no blocking here)
                self._setup_audio()

                # Connect to OpenAI Realtime API
                url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

                print(f"[OpenAI] Connecting to Realtime API (attempt {retry_count + 1}/{max_retries})...")

                # CRITICAL: Add ping/pong for connection health + shorter timeout
                async with websockets.connect(
                    url,
                    additional_headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "OpenAI-Beta": "realtime=v1"
                    },
                    ping_interval=20,  # Send ping every 20s
                    ping_timeout=10,   # Timeout if no pong in 10s
                    close_timeout=5,   # Faster close
                ) as ws:
                    self.websocket = ws
                    print("[OpenAI] Connected!")
                    retry_count = 0  # Reset on successful connection

                    # Configure session
                    await self._configure_session()

                    # Don't initialize audio streams yet - wait for wake word activation
                    # This allows wake word detector to use the microphone

                    # Start audio tasks
                    audio_output_task = asyncio.create_task(self._play_audio())
                    audio_input_task = asyncio.create_task(self._send_audio())

                    # Handle WebSocket messages
                    try:
                        async for message in ws:
                            if not self.is_running:
                                break
                            await self._handle_message(json.loads(message))
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("WebSocket connection closed")
                        if self.is_running:
                            print("[OpenAI] Connection lost, will retry...")

                    # Cleanup
                    audio_output_task.cancel()
                    audio_input_task.cancel()
                    try:
                        await audio_output_task
                    except asyncio.CancelledError:
                        pass
                    try:
                        await audio_input_task
                    except asyncio.CancelledError:
                        pass

            except ImportError:
                logger.error("websockets package not installed. Install: pip install websockets")
                print("ERROR: Install websockets: pip install websockets")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Error in Realtime API connection: {e}")
                import traceback
                traceback.print_exc()

                if self.is_running and retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 10)  # Exponential backoff, max 10s
                    print(f"[OpenAI] Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            finally:
                self._cleanup_audio()

        if retry_count >= max_retries:
            print(f"[OpenAI] Failed to connect after {max_retries} attempts")
            logger.error(f"Failed to connect after {max_retries} attempts")

    def _setup_audio(self):
        """Setup PyAudio streams - LAZY INIT to avoid blocking on startup"""
        # Don't initialize PyAudio here - defer until first audio playback
        # This prevents USB audio device blocking during startup
        self.audio = None
        self.output_stream = None
        logger.info("Audio setup deferred (lazy init on first playback)")
        print(f"[OpenAI Audio] Deferred initialization (lazy init)")

    def _cleanup_audio(self):
        """Cleanup PyAudio streams"""
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        if self.audio:
            self.audio.terminate()
        logger.info("Audio streams cleaned up")

    async def _configure_session(self):
        """Configure the OpenAI Realtime session - with server VAD and vision support"""
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.system_prompt,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"  # Enable transcription for server-side VAD
                },
                "turn_detection": {  # Enable server-side VAD
                    "type": "server_vad",
                    "threshold": 0.8,  # Voice detection threshold (0.0-1.0) - higher = less sensitive to noise
                    "prefix_padding_ms": 300,  # Audio before speech starts
                    "silence_duration_ms": 500,  # Silence to end turn (low latency)
                },
                "temperature": 0.7,
                "max_response_output_tokens": 150,
                # Note: Vision support via gpt-4o model which supports multimodal inputs
                "model": "gpt-4o-realtime-preview-2024-10-01",
            }
        }

        await self.websocket.send(json.dumps(config))
        logger.info("Session configured (server VAD + vision support enabled)")

    async def _send_camera_frame(self):
        """Analyze current camera frame using GPT-4 Vision (Chat API) and speak the response"""
        if not self.frame_getter:
            print("[Vision] No frame getter available")
            return

        try:
            import tempfile
            import os
            from openai import OpenAI

            # Get current frame on-demand
            current_frame = self.frame_getter()
            if not current_frame:
                print("[Vision] No camera frame available")
                return

            # Save frame to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_path = temp_file.name
            temp_file.close()

            if current_frame.save(temp_path, "JPG", 85):
                # Read as base64
                with open(temp_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

                print(f"[Vision] Captured frame, sending to GPT-4 Vision...")

                # Use OpenAI Chat Completions API for vision (Realtime API doesn't support images)
                client = OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Describe what you see in 2-3 concise sentences."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img_data}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=150
                )

                vision_description = response.choices[0].message.content
                print(f"[Vision] GPT-4 Vision response: {vision_description}")

                # Use OpenAI TTS to speak the vision description directly
                # (Don't send to Realtime API - causes conversation flow issues)
                await self._speak_text_directly(vision_description)

                # Cleanup
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Error analyzing camera frame: {e}")
            import traceback
            traceback.print_exc()

    async def _speak_text_directly(self, text: str):
        """Speak text directly using OpenAI TTS (bypasses Realtime API conversation)"""
        try:
            from openai import OpenAI

            print(f"[Vision TTS] Speaking: {text}")

            # Generate speech using TTS API
            client = OpenAI(api_key=self.openai_api_key)
            response = client.audio.speech.create(
                model="tts-1",  # Use fast model for low latency
                voice=self.voice,
                input=text,
                response_format="pcm"  # Raw PCM for direct playback
            )

            # Get raw audio bytes
            audio_bytes = response.content

            # Play audio directly through output stream
            if self.output_stream:
                self.is_playing_response = True

                # Write audio in chunks to avoid blocking
                chunk_size = 4096
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i+chunk_size]
                    self.audio_queue.put(chunk)

                # Wait for playback to finish
                import asyncio
                while not self.audio_queue.empty():
                    await asyncio.sleep(0.1)

                self.is_playing_response = False
                print("[Vision TTS] Playback complete")

        except Exception as e:
            logger.error(f"Error speaking text: {e}")
            import traceback
            traceback.print_exc()

    async def _send_text_message(self, text: str):
        """Send a text message to OpenAI"""
        if not self.websocket or not self.is_active:
            return

        try:
            # Create conversation item
            item = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": text
                        }
                    ]
                }
            }

            await self.websocket.send(json.dumps(item))

            # Request response
            response_request = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"]
                }
            }

            await self.websocket.send(json.dumps(response_request))

            print(f"[OpenAI] Sent: {text}")

        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _handle_message(self, message: dict):
        """Handle incoming WebSocket message"""
        msg_type = message.get("type")

        # Response started
        if msg_type == "response.audio.delta":
            if not self.is_playing_response:
                self.is_playing_response = True
                print("[OpenAI] Response started - reducing mic sensitivity")
            audio_b64 = message.get("delta")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                self.audio_queue.put(audio_bytes)

        # Response completed
        elif msg_type == "response.done":
            self.is_playing_response = False
            print("[OpenAI] Response complete - restoring mic sensitivity")

        # Input audio transcription (user's speech)
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            transcript = message.get("transcript", "").lower()
            logger.info(f"User said: {transcript}")

            # Check if user is asking about vision
            vision_keywords = ["what do you see", "what am i looking at", "describe this",
                             "analyze this", "what is this", "look at", "can you see"]
            if any(keyword in transcript for keyword in vision_keywords):
                print(f"[Vision] Detected vision query, sending camera frame...")
                await self._send_camera_frame()

        # Transcript (text response from assistant)
        elif msg_type == "response.text.delta":
            text = message.get("delta", "")
            if text:
                print(f"[OpenAI Text]: {text}", end="", flush=True)

        # Error handling
        elif msg_type == "error":
            error = message.get("error", {})
            logger.error(f"OpenAI error: {error}")
            print(f"[OpenAI Error]: {error}")

    def _init_audio_lazy(self):
        """Initialize PyAudio on demand - both input and output with auto sample rate detection"""
        if self.audio is not None:
            return  # Already initialized

        try:
            import os
            import numpy as np
            from scipy import signal as scipy_signal

            self.audio = pyaudio.PyAudio()

            # Use PulseAudio environment variable to route to correct device
            os.environ['PULSE_SINK'] = 'alsa_output.usb-KTMicro_KT_USB_Audio_2021-06-07-0000-0000-0000--00.analog-stereo'

            # Input stream - auto-detect supported sample rate and resample to 24kHz
            # Try 24kHz first, then fallback to higher rates with resampling
            self.input_native_rate = 24000
            self.needs_resampling = False

            for test_rate in [24000, 48000, 44100]:
                try:
                    self.input_stream = self.audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=test_rate,
                        input=True,
                        input_device_index=self.input_device_index,
                        frames_per_buffer=int(test_rate * 0.02),  # 20ms at native rate
                    )
                    self.input_native_rate = test_rate
                    self.needs_resampling = (test_rate != 24000)
                    print(f"[OpenAI Audio] Input: {test_rate}Hz (resample={self.needs_resampling})")
                    break
                except Exception as e:
                    if test_rate == 44100:  # Last attempt
                        raise
                    continue

            # Output stream (speakers) - 24kHz mono for OpenAI audio output
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                output_device_index=self.output_device_index,
                frames_per_buffer=1200,  # 50ms buffer
            )

            print(f"[OpenAI Audio] Streams initialized (output: 24kHz)")
            logger.info("Audio streams initialized on-demand")

        except Exception as e:
            logger.error(f"Error initializing audio: {e}")
            import traceback
            traceback.print_exc()
            self.audio = None
            self.input_stream = None
            self.output_stream = None

    async def _send_audio(self):
        """Send microphone audio to OpenAI - only when activated"""
        import concurrent.futures
        import numpy as np
        from scipy import signal as scipy_signal

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        while self.is_running:
            try:
                # Only send audio if activated by wake word
                if not self.send_audio_enabled:
                    await asyncio.sleep(0.1)  # Wait for activation
                    continue

                # Don't send mic audio while assistant is speaking (prevent feedback loop)
                # User can still interrupt by speaking louder (server VAD will detect)
                if self.is_playing_response:
                    await asyncio.sleep(0.05)
                    continue

                if self.input_stream:
                    # Calculate chunk size at native rate (20ms)
                    native_chunk = int(self.input_native_rate * 0.02)

                    # Read audio in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    audio_data = await loop.run_in_executor(
                        executor,
                        lambda: self.input_stream.read(native_chunk, exception_on_overflow=False)
                    )

                    # Resample if needed
                    if self.needs_resampling:
                        # Convert bytes to numpy array
                        audio_np = np.frombuffer(audio_data, dtype=np.int16)

                        # Resample to 24kHz
                        num_samples_24k = int(len(audio_np) * 24000 / self.input_native_rate)
                        audio_resampled = scipy_signal.resample(audio_np, num_samples_24k)

                        # Convert back to int16 bytes
                        audio_data = audio_resampled.astype(np.int16).tobytes()

                    # Send to OpenAI as base64
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                    await self.websocket.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64
                    }))
                else:
                    await asyncio.sleep(0.02)  # Wait for audio init
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                await asyncio.sleep(0.1)

    async def _play_audio(self):
        """Play audio from queue - non-blocking with executor"""
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        while self.is_running:
            try:
                # Get audio from queue (non-blocking)
                try:
                    audio_data = self.audio_queue.get_nowait()

                    if self.output_stream:
                        # Run blocking write in executor to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            executor,
                            self.output_stream.write,
                            audio_data
                        )
                except queue.Empty:
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                import traceback
                traceback.print_exc()

    @property
    def is_speaking(self):
        """Check if assistant is currently speaking"""
        return not self.audio_queue.empty()
