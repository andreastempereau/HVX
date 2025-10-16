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
        output_volume: float = 1.0,  # Output volume multiplier (0.0-1.0)
        wake_word_detector=None,  # Reference to wake word detector to resume it
        frame_getter=None,  # Function to get current camera frame on-demand
        system_monitor=None,  # System telemetry monitor
        video_recorder=None,  # Video recorder for recording control
    ):
        self.openai_api_key = openai_api_key
        self.system_prompt = system_prompt or "You are a helpful AI assistant."
        self.voice = voice
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        self.output_volume = max(0.0, min(1.0, output_volume))  # Clamp to 0.0-1.0
        self.wake_word_detector = wake_word_detector
        self.frame_getter = frame_getter  # On-demand frame capture
        self.system_monitor = system_monitor  # System telemetry
        self.video_recorder = video_recorder  # Video recorder

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

        # Send initial greeting
        if self.loop and self.websocket:
            asyncio.run_coroutine_threadsafe(
                self._send_greeting(),
                self.loop
            )

    def deactivate(self):
        """Deactivate the assistant and resume wake word detection"""
        print("[OpenAI Assistant] Deactivating...")
        self.is_active = False
        self.send_audio_enabled = False  # Stop sending mic audio to OpenAI

        # Give async loops time to finish current operations
        import time
        time.sleep(0.2)

        # Close audio streams to release microphone (in proper order)
        if self.input_stream:
            print("[OpenAI Assistant] Closing input stream...")
            try:
                self.input_stream.stop_stream()
            except:
                pass
            try:
                self.input_stream.close()
            except:
                pass
            self.input_stream = None

        if self.output_stream:
            print("[OpenAI Assistant] Closing output stream...")
            try:
                self.output_stream.stop_stream()
            except:
                pass
            try:
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

        # Terminate PyAudio instance
        if self.audio:
            print("[OpenAI Assistant] Terminating PyAudio...")
            try:
                self.audio.terminate()
            except:
                pass
            self.audio = None

        # Clear audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break

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
        """Configure the OpenAI Realtime session - with server VAD, vision, and web search support"""
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
                    "threshold": 0.95,  # Voice detection threshold (0.0-1.0) - very high to ignore assistant's own voice
                    "prefix_padding_ms": 300,  # Audio before speech starts
                    "silence_duration_ms": 1800,  # Silence to end turn (allow longer pauses in speech)
                },
                "temperature": 0.7,
                "max_response_output_tokens": 200,  # Keep responses brief but useful
                # Note: Vision support via gpt-4o model which supports multimodal inputs
                "model": "gpt-4o-realtime-preview-2024-10-01",
                "tools": [
                    {
                        "type": "function",
                        "name": "web_search",
                        "description": "Search the internet for current information, news, weather, facts, or any real-time data. Use this whenever you need up-to-date information you don't have.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "type": "function",
                        "name": "get_system_status",
                        "description": "Get current helmet system status including CPU usage, GPU usage, temperatures, RAM usage, power consumption, and FPS. Use this when the operator asks about system health, performance, temperatures, or resource usage.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "type": "function",
                        "name": "start_recording",
                        "description": "Start video recording from the helmet camera. Records until stopped or duration limit reached. Use when operator says 'start recording', 'record video', 'begin recording', etc.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "duration_seconds": {
                                    "type": "number",
                                    "description": "Optional duration in seconds. If not specified, records until manually stopped."
                                }
                            },
                            "required": []
                        }
                    },
                    {
                        "type": "function",
                        "name": "stop_recording",
                        "description": "Stop the current video recording and save the file. Use when operator says 'stop recording', 'end recording', 'save recording', etc.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "type": "function",
                        "name": "get_recording_status",
                        "description": "Check if currently recording and get recording info (duration, frames). Use when operator asks 'are you recording', 'recording status', etc.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                ],
                "tool_choice": "auto"  # Let model decide when to use tools
            }
        }

        await self.websocket.send(json.dumps(config))
        logger.info("Session configured (server VAD + vision + web search enabled)")

    async def _get_system_status(self) -> str:
        """Get current system status from telemetry"""
        try:
            print("[System Status] Reading telemetry...")

            if not self.system_monitor:
                return "System monitor not available."

            # Get latest telemetry
            t = self.system_monitor.get_telemetry()

            # Format concise status report
            status = (
                f"System status: "
                f"CPU {t['cpu_usage']:.0f}% at {t['cpu_temp']:.0f}°C, "
                f"GPU {t['gpu_usage']:.0f}% at {t['gpu_temp']:.0f}°C, "
                f"RAM {t['ram_usage']:.0f}% used, "
                f"power draw {t['power_total_mw']/1000:.1f} watts"
            )

            # Add warnings if needed
            warnings = []
            if t['cpu_temp'] > 70:
                warnings.append("CPU temperature elevated")
            if t['gpu_temp'] > 70:
                warnings.append("GPU temperature elevated")
            if t['ram_usage'] > 85:
                warnings.append("RAM usage high")

            if warnings:
                status += ". Warnings: " + ", ".join(warnings)

            print(f"[System Status] {status}")
            return status

        except Exception as e:
            error_msg = f"Status check failed: {str(e)}"
            print(f"[System Status Error] {error_msg}")
            return error_msg

    async def _start_recording(self, duration_seconds: Optional[int] = None) -> str:
        """Start video recording"""
        try:
            print(f"[Recording] Starting recording (duration: {duration_seconds or 'unlimited'}s)...")

            if not self.video_recorder:
                return "Video recorder not available."

            if self.video_recorder.is_recording_active():
                return "Already recording."

            filename = self.video_recorder.start_recording(duration_seconds=duration_seconds)

            if duration_seconds:
                result = f"Recording started for {duration_seconds} seconds. File: {filename}"
            else:
                result = f"Recording started. Say 'stop recording' when done. File: {filename}"

            print(f"[Recording] {result}")
            return result

        except Exception as e:
            error_msg = f"Failed to start recording: {str(e)}"
            print(f"[Recording Error] {error_msg}")
            return error_msg

    async def _stop_recording(self) -> str:
        """Stop video recording"""
        try:
            print("[Recording] Stopping recording...")

            if not self.video_recorder:
                return "Video recorder not available."

            if not self.video_recorder.is_recording_active():
                return "Not currently recording."

            filename = self.video_recorder.stop_recording()
            info = self.video_recorder.get_recording_info()

            result = f"Recording stopped. Saved to {filename}"
            print(f"[Recording] {result}")
            return result

        except Exception as e:
            error_msg = f"Failed to stop recording: {str(e)}"
            print(f"[Recording Error] {error_msg}")
            return error_msg

    async def _get_recording_status(self) -> str:
        """Get recording status"""
        try:
            if not self.video_recorder:
                return "Video recorder not available."

            info = self.video_recorder.get_recording_info()

            if info['recording']:
                duration = info['duration']
                frames = info['frames']
                status = f"Currently recording: {duration:.1f} seconds, {frames} frames captured"
                if info['max_duration']:
                    remaining = info['max_duration'] - duration
                    status += f", {remaining:.0f} seconds remaining"
            else:
                status = "Not currently recording"

            print(f"[Recording Status] {status}")
            return status

        except Exception as e:
            error_msg = f"Failed to get recording status: {str(e)}"
            print(f"[Recording Error] {error_msg}")
            return error_msg

    async def _web_search(self, query: str) -> str:
        """Perform web search using DuckDuckGo"""
        try:
            print(f"[Web Search] Searching for: {query}")
            from ddgs import DDGS

            # Run blocking search in executor
            loop = asyncio.get_event_loop()
            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def do_search():
                ddgs = DDGS()
                results = list(ddgs.text(query, max_results=5))
                return results

            search_results = await loop.run_in_executor(executor, do_search)

            if not search_results:
                return "No results found."

            # Format results
            formatted = f"Search results for '{query}':\n\n"
            for i, result in enumerate(search_results[:3], 1):  # Top 3 results
                formatted += f"{i}. {result['title']}\n{result['body'][:200]}...\n\n"

            print(f"[Web Search] Found {len(search_results)} results")
            return formatted

        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            print(f"[Web Search Error] {error_msg}")
            return error_msg

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

                # Send vision description back to Realtime API for speaking
                # This keeps everything in one conversation flow
                await self._send_vision_result(vision_description)

                # Cleanup
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Error analyzing camera frame: {e}")
            import traceback
            traceback.print_exc()

    async def _send_vision_result(self, vision_text: str):
        """Send vision analysis result to Realtime API to speak"""
        if not self.websocket or not self.is_active:
            return

        try:
            # Create a conversation item with the vision result
            item = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "assistant",  # Assistant describing what it sees
                    "content": [
                        {
                            "type": "text",
                            "text": vision_text
                        }
                    ]
                }
            }

            await self.websocket.send(json.dumps(item))

            # Request the model to speak this
            response_request = {
                "type": "response.create",
                "response": {
                    "modalities": ["audio"],  # Only audio, we already have the text
                    "instructions": f"Say this exactly: {vision_text}"
                }
            }

            await self.websocket.send(json.dumps(response_request))
            print(f"[Vision] Sent to Realtime API for speaking")

        except Exception as e:
            logger.error(f"Error sending vision result: {e}")

    async def _speak_text_directly_OLD(self, text: str):
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

    async def _send_greeting(self):
        """Send initial greeting when activated"""
        if not self.websocket or not self.is_active:
            return

        try:
            # Request a simple greeting response
            response_request = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "Greet the user with just the word 'Sir' in a professional tone."
                }
            }

            await self.websocket.send(json.dumps(response_request))
            print(f"[OpenAI] Sending greeting...")

        except Exception as e:
            logger.error(f"Error sending greeting: {e}")

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
                print("[OpenAI] Response started - blocking microphone input")
            audio_b64 = message.get("delta")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                self.audio_queue.put(audio_bytes)

        # Response completed
        elif msg_type == "response.done":
            self.is_playing_response = False
            print("[OpenAI] Response complete - microphone listening resumed")

        # Input audio transcription (user's speech)
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            transcript = message.get("transcript", "").lower()
            logger.info(f"User said: {transcript}")
            print(f"[User Transcript]: {transcript}")

            # Check for dismissal phrases
            if any(phrase in transcript for phrase in self.dismissal_phrases):
                print(f"[OpenAI] Dismissal detected: '{transcript}'")
                self.deactivate()
                return

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

        # Function call requested
        elif msg_type == "response.function_call_arguments.done":
            call_id = message.get("call_id")
            function_name = message.get("name")
            arguments_str = message.get("arguments")

            print(f"[Function Call] {function_name}({arguments_str})")

            if function_name == "web_search":
                import json as json_module
                args = json_module.loads(arguments_str)
                query = args.get("query", "")

                # Perform web search
                result = await self._web_search(query)

                # Send result back to model
                await self.websocket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }))

                # Request response with the search result
                await self.websocket.send(json.dumps({
                    "type": "response.create"
                }))

            elif function_name == "get_system_status":
                # Get system status
                result = await self._get_system_status()

                # Send result back to model
                await self.websocket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }))

                # Request response with the status info
                await self.websocket.send(json.dumps({
                    "type": "response.create"
                }))

            elif function_name == "start_recording":
                import json as json_module
                args = json_module.loads(arguments_str)
                duration = args.get("duration_seconds")

                # Start recording
                result = await self._start_recording(duration_seconds=duration)

                # Send result back to model
                await self.websocket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }))

                # Request response
                await self.websocket.send(json.dumps({
                    "type": "response.create"
                }))

            elif function_name == "stop_recording":
                # Stop recording
                result = await self._stop_recording()

                # Send result back to model
                await self.websocket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }))

                # Request response
                await self.websocket.send(json.dumps({
                    "type": "response.create"
                }))

            elif function_name == "get_recording_status":
                # Get recording status
                result = await self._get_recording_status()

                # Send result back to model
                await self.websocket.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }))

                # Request response
                await self.websocket.send(json.dumps({
                    "type": "response.create"
                }))

        # Error handling
        elif msg_type == "error":
            error = message.get("error", {})
            # Suppress "input_audio_buffer_commit_empty" errors (expected when blocking mic)
            if error.get("code") != "input_audio_buffer_commit_empty":
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

            # Output stream (speakers) - try 44.1kHz first (most compatible), then 48kHz, then 24kHz
            self.output_native_rate = 44100
            self.needs_output_resampling = True

            for test_rate in [44100, 48000, 24000]:
                try:
                    self.output_stream = self.audio.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=test_rate,
                        output=True,
                        output_device_index=self.output_device_index,
                        frames_per_buffer=int(test_rate * 0.05),  # 50ms buffer
                    )
                    self.output_native_rate = test_rate
                    self.needs_output_resampling = (test_rate != 24000)
                    print(f"[OpenAI Audio] Output: {test_rate}Hz (resample={self.needs_output_resampling})")
                    break
                except Exception as e:
                    if test_rate == 44100:  # Last attempt
                        raise
                    continue

            print(f"[OpenAI Audio] Streams initialized")
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

                if self.input_stream:
                    # Calculate chunk size at native rate (20ms)
                    native_chunk = int(self.input_native_rate * 0.02)

                    # Read audio in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    audio_data = await loop.run_in_executor(
                        executor,
                        lambda: self.input_stream.read(native_chunk, exception_on_overflow=False)
                    )

                    # If assistant is speaking, discard mic input (don't send it)
                    # This prevents the assistant from hearing itself
                    if self.is_playing_response:
                        continue  # Discard the audio, don't send to OpenAI

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
        import numpy as np
        from scipy import signal as scipy_signal

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        while self.is_running:
            try:
                # Get audio from queue (non-blocking)
                try:
                    audio_data = self.audio_queue.get_nowait()
                    print(f"[Audio Play] Got {len(audio_data)} bytes from queue, output_stream={self.output_stream is not None}")

                    if self.output_stream:
                        # Convert to numpy for processing
                        audio_np = np.frombuffer(audio_data, dtype=np.int16)

                        # Apply volume control
                        if self.output_volume != 1.0:
                            audio_np = (audio_np * self.output_volume).astype(np.int16)

                        # Resample if needed (OpenAI sends 24kHz, device might need different rate)
                        if self.needs_output_resampling:
                            num_samples = int(len(audio_np) * self.output_native_rate / 24000)
                            audio_np = scipy_signal.resample(audio_np, num_samples).astype(np.int16)

                        audio_data = audio_np.tobytes()

                        # Run blocking write in executor to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        print(f"[Audio Play] Writing {len(audio_data)} bytes to speaker...")
                        await loop.run_in_executor(
                            executor,
                            self.output_stream.write,
                            audio_data
                        )
                        print(f"[Audio Play] Write complete")
                except queue.Empty:
                    await asyncio.sleep(0.01)
            except Exception as e:
                # Suppress "Stream closed" errors (expected when deactivating)
                if "Stream closed" not in str(e) and "Unanticipated host error" not in str(e):
                    logger.error(f"Error playing audio: {e}")
                    print(f"[OpenAI Audio Error]: {e}")

    @property
    def is_speaking(self):
        """Check if assistant is currently speaking"""
        return not self.audio_queue.empty()
