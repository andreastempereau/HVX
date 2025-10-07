"""Voice assistant with Claude API and ElevenLabs TTS"""

import os
import threading
import queue
import logging
from typing import Callable, Optional
import asyncio
from io import BytesIO

logger = logging.getLogger(__name__)


class VoiceAssistant:
    """Voice assistant using Claude API for responses and ElevenLabs for TTS"""

    def __init__(
        self,
        anthropic_api_key: str,
        elevenlabs_api_key: str,
        system_prompt: Optional[str] = None,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Default: Rachel voice
        output_device_index: Optional[int] = None,
    ):
        self.anthropic_api_key = anthropic_api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        self.system_prompt = system_prompt or "You are a helpful AI assistant integrated into an AR helmet. Provide concise, clear responses."
        self.voice_id = voice_id
        self.output_device_index = output_device_index

        self.is_running = False
        self.is_active = False  # Track if assistant is actively listening (post wake word)
        self.conversation_history = []
        self.message_queue = queue.Queue()
        self.thread = None

        # Dismissal phrases (case insensitive)
        self.dismissal_phrases = [
            'okay thanks', 'ok thanks', 'thank you', 'thanks',
            'that\'s all', 'thats all', 'all done', 'done',
            'i don\'t need you', 'don\'t need you', 'go away',
            'dismiss', 'dismissed', 'stop listening', 'never mind',
            'goodbye', 'bye', 'see you later'
        ]

        logger.info("Voice assistant initialized")

    def start(self):
        """Start the voice assistant processing thread"""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._run_assistant, daemon=True)
        self.thread.start()
        logger.info("Voice assistant started")

    def stop(self):
        """Stop the voice assistant"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Voice assistant stopped")

    def process_message(self, user_message: str, is_wake_word: bool = False):
        """Queue a user message for processing"""
        if not self.is_running:
            logger.warning("Voice assistant not running")
            return

        self.message_queue.put((user_message, is_wake_word))
        logger.info(f"Queued message: {user_message} (wake_word={is_wake_word})")

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def _run_assistant(self):
        """Run the assistant processing loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                # Get message from queue (with timeout to allow checking is_running)
                try:
                    user_message, is_wake_word = self.message_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Process the message
                loop.run_until_complete(self._process_message_async(user_message, is_wake_word))

            except Exception as e:
                logger.error(f"Error in assistant loop: {e}")
                import traceback
                traceback.print_exc()

    async def _process_message_async(self, user_message: str, is_wake_word: bool = False):
        """Process a user message and generate response with TTS"""
        try:
            # If this is a wake word activation, set active
            if is_wake_word:
                self.is_active = True
                print(f"[Assistant] Activated - now listening continuously")

            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            print(f"\n[User]: {user_message}")

            # Check for dismissal phrases
            user_lower = user_message.lower().strip()
            is_dismissal = any(phrase in user_lower for phrase in self.dismissal_phrases)

            if is_dismissal:
                self.is_active = False
                print(f"[Assistant] Dismissal detected - deactivating")
                dismissal_response = "Understood, Sir. I'll be here if you need me."

                # Add to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": dismissal_response
                })

                print(f"[Assistant]: {dismissal_response}")
                await self._speak(dismissal_response)
                print(f"[TTS] Speech playback complete")
                return

            # Get response from Claude
            assistant_response = await self._get_claude_response()

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })

            print(f"[Assistant]: {assistant_response}")

            # Generate and play TTS
            print(f"[TTS] Generating speech for response...")
            await self._speak(assistant_response)
            print(f"[TTS] Speech playback complete")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()

    async def _get_claude_response(self) -> str:
        """Get response from Claude API"""
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.anthropic_api_key)

            # Create message with system prompt and conversation history
            # Limit tokens to reduce TTS generation time
            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,  # Shorter responses = faster TTS
                system=self.system_prompt,
                messages=self.conversation_history
            )

            # Extract text from response
            assistant_message = response.content[0].text
            return assistant_message

        except ImportError:
            logger.error("anthropic package not installed. Install: pip install anthropic")
            return "Error: Anthropic SDK not installed."
        except Exception as e:
            logger.error(f"Error getting Claude response: {e}")
            return f"Error: {str(e)}"

    async def _speak(self, text: str):
        """Generate speech with ElevenLabs and play it"""
        try:
            from elevenlabs import AsyncElevenLabs
            import pyaudio
            import wave

            print(f"[TTS] Connecting to ElevenLabs API...")
            # Generate speech
            client = AsyncElevenLabs(api_key=self.elevenlabs_api_key)

            print(f"[TTS] Requesting audio generation (voice_id={self.voice_id})...")
            # Generate audio stream (convert returns async generator directly)
            # Using eleven_turbo_v2 for faster generation (lower latency)
            audio_generator = client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id="eleven_turbo_v2",  # Faster than eleven_monolingual_v1
                output_format="mp3_22050_32"  # Lower quality = faster/smaller
            )

            print(f"[TTS] Collecting audio chunks...")
            # Collect audio data
            audio_data = BytesIO()
            chunk_count = 0
            async for chunk in audio_generator:
                audio_data.write(chunk)
                chunk_count += 1

            print(f"[TTS] Received {chunk_count} chunks, total size: {audio_data.tell()} bytes")

            # Play audio
            audio_data.seek(0)
            print(f"[TTS] Starting audio playback...")
            await self._play_audio(audio_data.read())
            print(f"[TTS] Audio playback finished")

        except ImportError:
            logger.error("elevenlabs package not installed. Install: pip install elevenlabs")
        except Exception as e:
            logger.error(f"Error generating/playing speech: {e}")
            import traceback
            traceback.print_exc()

    async def _play_audio(self, audio_data: bytes):
        """Play audio data using mpg123"""
        try:
            import subprocess
            import tempfile
            import os

            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            logger.info(f"Playing audio via mpg123...")
            print(f"[Audio] Saved {len(audio_data)} bytes to {temp_path}")

            # Use PulseAudio to route to USB audio device
            # Force output to USB KT Audio device (index 0)
            env = os.environ.copy()
            env['PULSE_SINK'] = 'alsa_output.usb-KTMicro_KT_USB_Audio_2021-06-07-0000-0000-0000--00.analog-stereo'

            # Use mpg123 with PulseAudio backend (-o pulse)
            mpg123_args = ['mpg123', '-q', '-o', 'pulse', temp_path]

            print(f"[Audio] Running: {' '.join(mpg123_args)}")
            print(f"[Audio] PULSE_SINK={env['PULSE_SINK']}")
            result = subprocess.run(
                mpg123_args,
                capture_output=True,
                text=True,
                env=env
            )

            print(f"[Audio] mpg123 exit code: {result.returncode}")
            if result.returncode != 0:
                logger.error(f"mpg123 failed: {result.stderr}")
                print(f"[Audio] mpg123 stderr: {result.stderr}")
            else:
                print(f"[Audio] mpg123 completed successfully")
                if result.stdout:
                    print(f"[Audio] mpg123 stdout: {result.stdout}")

            # Cleanup
            os.unlink(temp_path)

            logger.info("Audio playback complete")

        except FileNotFoundError:
            logger.error("mpg123 not found. Install: sudo apt-get install mpg123")
            print("ERROR: mpg123 not installed. Run: sudo apt-get install mpg123")
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            import traceback
            traceback.print_exc()
