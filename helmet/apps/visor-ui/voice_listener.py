"""Simple voice listener for HVX commands"""

import threading
import queue
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class VoiceListener:
    """Voice activation listener using speech recognition"""

    def __init__(self, device_index: Optional[int] = None):
        self.device_index = device_index
        self.is_listening = False
        self.callback = None
        self.thread = None
        self.command_queue = queue.Queue()

        # Check if libraries are available
        self.recognizer = None
        self.microphone = None
        self._setup()

    def _setup(self):
        """Setup speech recognition"""
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()

            # Adjust for ambient noise sensitivity
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

            # Get microphone
            if self.device_index is not None:
                self.microphone = sr.Microphone(device_index=self.device_index)
            else:
                self.microphone = sr.Microphone()

            # Calibrate for ambient noise
            with self.microphone as source:
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)

            logger.info(f"Voice listener initialized (device: {self.device_index or 'default'})")

        except ImportError:
            logger.warning("speech_recognition not available. Install with: pip install SpeechRecognition pyaudio")
        except Exception as e:
            logger.error(f"Failed to setup voice listener: {e}")

    def start(self, callback: Callable[[str], None]):
        """Start listening for voice commands"""
        if not self.recognizer or not self.microphone:
            logger.error("Voice listener not available")
            return False

        self.callback = callback
        self.is_listening = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info("Voice listener started")
        return True

    def stop(self):
        """Stop listening"""
        self.is_listening = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Voice listener stopped")

    def _listen_loop(self):
        """Main listening loop"""
        import speech_recognition as sr

        logger.info("Listening for wake words: 'analyze', 'what am I looking at'...")

        while self.is_listening:
            try:
                with self.microphone as source:
                    # Listen for audio
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)

                try:
                    # Recognize speech using Google Speech Recognition
                    text = self.recognizer.recognize_google(audio).lower()
                    logger.debug(f"Heard: {text}")

                    # Check for commands
                    command = self._parse_command(text)
                    if command and self.callback:
                        logger.info(f"Voice command detected: {command}")
                        self.callback(command)

                except sr.UnknownValueError:
                    # Could not understand audio
                    pass
                except sr.RequestError as e:
                    logger.error(f"Could not request results from Google Speech Recognition: {e}")

            except sr.WaitTimeoutError:
                # No speech detected, continue
                pass
            except Exception as e:
                if self.is_listening:  # Only log if we're still supposed to be listening
                    logger.error(f"Error in listen loop: {e}")

    def _parse_command(self, text: str) -> Optional[str]:
        """Parse voice input into commands"""
        text = text.lower().strip()

        # Analyze commands
        if any(phrase in text for phrase in ['analyze', 'what am i looking at', 'whats this', 'identify']):
            return 'analyze'

        # Show/hide detection
        if any(phrase in text for phrase in ['show detection', 'show objects', 'detect']):
            return 'show_detections'

        if any(phrase in text for phrase in ['hide detection', 'hide objects']):
            return 'hide_detections'

        # Show/hide HUD
        if any(phrase in text for phrase in ['show hud', 'show status']):
            return 'show_hud'

        if any(phrase in text for phrase in ['hide hud', 'hide status', 'clear display']):
            return 'hide_hud'

        return None

    @staticmethod
    def list_microphones():
        """List available microphone devices"""
        try:
            import speech_recognition as sr
            mics = []
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                mics.append((index, name))
                print(f"{index}: {name}")
            return mics
        except ImportError:
            print("speech_recognition not available")
            return []
        except Exception as e:
            print(f"Error listing microphones: {e}")
            return []


if __name__ == "__main__":
    # Test script to list available microphones
    print("Available microphones:")
    VoiceListener.list_microphones()
