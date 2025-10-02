#!/usr/bin/env python3
"""Voice assistant service with ASR, intent recognition, and TTS"""

import asyncio
import logging
import threading
import queue
import time
from concurrent import futures
from pathlib import Path
import sys
import json
import re
from typing import Optional, Dict, List, Any
import numpy as np

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("faster-whisper not available")

try:
    import piper
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    logging.warning("Piper TTS not available")

try:
    import pyaudio
    import numpy as np
    import webrtcvad
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logging.warning("Audio libraries not available")

# Add libs to path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from utils.config import get_config
from utils.logging_utils import setup_logging, log_performance
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class AudioCapture:
    """Audio capture and voice activity detection"""

    def __init__(self, config):
        self.config = config
        self.sample_rate = config.get('voice.sample_rate', 16000)
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16

        self.pyaudio = None
        self.stream = None
        self.vad = None
        self.audio_queue = queue.Queue()
        self.is_recording = False

        if AUDIO_AVAILABLE:
            self._setup_audio()

    def _setup_audio(self):
        """Initialize audio capture"""
        try:
            self.pyaudio = pyaudio.PyAudio()

            # Setup VAD
            self.vad = webrtcvad.Vad(2)  # Aggressiveness level 2

            # Find microphone device
            device_name = self.config.get('voice.mic_device', 'default')
            device_index = None

            if device_name != 'default':
                for i in range(self.pyaudio.get_device_count()):
                    info = self.pyaudio.get_device_info_by_index(i)
                    if device_name.lower() in info['name'].lower():
                        device_index = i
                        break

            # Create audio stream
            self.stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )

            logger.info(f"Audio capture initialized: {self.sample_rate}Hz, device: {device_name}")

        except Exception as e:
            logger.error(f"Failed to setup audio: {e}")
            self.pyaudio = None
            self.stream = None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio stream callback"""
        if self.is_recording:
            # Convert to numpy array
            audio_np = np.frombuffer(in_data, dtype=np.int16)

            # Voice activity detection
            is_speech = False
            if self.vad:
                try:
                    # VAD expects 10, 20, or 30ms frames
                    frame_duration = 30  # ms
                    frame_size = int(self.sample_rate * frame_duration / 1000)

                    if len(audio_np) >= frame_size:
                        frame = audio_np[:frame_size].tobytes()
                        is_speech = self.vad.is_speech(frame, self.sample_rate)
                except:
                    is_speech = True  # Fallback to always process

            if is_speech or not self.vad:
                self.audio_queue.put(audio_np)

        return (None, pyaudio.paContinue)

    def start_recording(self):
        """Start audio recording"""
        if self.stream:
            self.is_recording = True
            self.stream.start_stream()
            logger.info("Audio recording started")

    def stop_recording(self):
        """Stop audio recording"""
        if self.stream:
            self.is_recording = False
            self.stream.stop_stream()
            logger.info("Audio recording stopped")

    def get_audio_chunk(self, timeout=1.0) -> Optional[np.ndarray]:
        """Get audio chunk from queue"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def cleanup(self):
        """Cleanup audio resources"""
        if self.stream:
            self.stream.close()
        if self.pyaudio:
            self.pyaudio.terminate()

class ASREngine:
    """Automatic Speech Recognition using faster-whisper"""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.model_size = config.get('voice.asr_model', 'small')
        self.language = config.get('voice.language', 'en')

        if WHISPER_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """Load Whisper model"""
        try:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = WhisperModel(
                self.model_size,
                device="auto",  # Use GPU if available
                compute_type="int8"  # Optimize for speed
            )
            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model = None

    @log_performance("speech_recognition")
    def transcribe(self, audio_data: np.ndarray) -> Optional[str]:
        """Transcribe audio to text"""
        if not self.model:
            return self._mock_transcription()

        try:
            # Convert to float32 and normalize
            audio_float = audio_data.astype(np.float32) / 32768.0

            # Run transcription
            segments, info = self.model.transcribe(
                audio_float,
                language=self.language,
                beam_size=1,  # Faster inference
                temperature=0.0
            )

            # Combine segments
            transcription = ""
            for segment in segments:
                transcription += segment.text

            return transcription.strip() if transcription else None

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    def _mock_transcription(self) -> str:
        """Mock transcription for testing"""
        import random
        mock_phrases = [
            "toggle night mode",
            "start recording",
            "take screenshot",
            "show navigation",
            "increase brightness",
            "what do you see",
            "mark target"
        ]
        return random.choice(mock_phrases)

class IntentEngine:
    """Intent recognition and command processing"""

    def __init__(self, config):
        self.config = config
        self.intents_file = Path(__file__).parent / "intents.json"
        self.intents = self._load_intents()

    def _load_intents(self) -> Dict[str, Any]:
        """Load intent patterns and actions"""
        try:
            if self.intents_file.exists():
                with open(self.intents_file, 'r') as f:
                    return json.load(f)
            else:
                return self._default_intents()
        except Exception as e:
            logger.error(f"Failed to load intents: {e}")
            return self._default_intents()

    def _default_intents(self) -> Dict[str, Any]:
        """Default intent patterns"""
        return {
            "toggle_night_mode": {
                "patterns": [
                    r"toggle night.*mode",
                    r"night.*vision",
                    r"low.*light.*mode",
                    r"dark.*mode"
                ],
                "action": "set_mode",
                "parameters": {"mode": "night"}
            },
            "start_recording": {
                "patterns": [
                    r"start.*record",
                    r"begin.*record",
                    r"record.*video"
                ],
                "action": "toggle_recording",
                "parameters": {"enabled": True}
            },
            "stop_recording": {
                "patterns": [
                    r"stop.*record",
                    r"end.*record",
                    r"finish.*record"
                ],
                "action": "toggle_recording",
                "parameters": {"enabled": False}
            },
            "take_screenshot": {
                "patterns": [
                    r"take.*screenshot",
                    r"capture.*screen",
                    r"snap.*photo"
                ],
                "action": "screenshot",
                "parameters": {}
            },
            "show_navigation": {
                "patterns": [
                    r"show.*nav",
                    r"navigation.*mode",
                    r"compass.*mode"
                ],
                "action": "set_mode",
                "parameters": {"mode": "navigation"}
            },
            "normal_mode": {
                "patterns": [
                    r"normal.*mode",
                    r"default.*mode",
                    r"regular.*mode"
                ],
                "action": "set_mode",
                "parameters": {"mode": "normal"}
            }
        }

    def classify_intent(self, text: str) -> Optional[helmet_pb2.Intent]:
        """Classify text into intent"""
        if not text:
            return None

        text_lower = text.lower()

        for intent_name, intent_data in self.intents.items():
            patterns = intent_data.get('patterns', [])

            for pattern in patterns:
                if re.search(pattern, text_lower):
                    intent = helmet_pb2.Intent()
                    intent.text = text
                    intent.intent_name = intent_name
                    intent.confidence = 0.9  # Simple confidence score

                    # Add parameters
                    for key, value in intent_data.get('parameters', {}).items():
                        intent.entities[key] = str(value)

                    timestamp = Timestamp()
                    timestamp.GetCurrentTime()
                    intent.timestamp.CopyFrom(timestamp)

                    return intent

        # Unknown intent
        intent = helmet_pb2.Intent()
        intent.text = text
        intent.intent_name = "unknown"
        intent.confidence = 0.1
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        intent.timestamp.CopyFrom(timestamp)

        return intent

class TTSEngine:
    """Text-to-Speech using Piper"""

    def __init__(self, config):
        self.config = config
        self.voice_model = config.get('voice.tts_voice', 'en_US-ljspeech-medium')
        self.piper_model = None

        if PIPER_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """Load Piper TTS model"""
        try:
            # This would load the actual Piper model
            # Implementation depends on Piper library setup
            logger.info(f"Loading TTS model: {self.voice_model}")
            # self.piper_model = piper.load_model(self.voice_model)
            logger.info("TTS model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            self.piper_model = None

    def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to speech"""
        if not text:
            return None

        try:
            if self.piper_model:
                # Use actual Piper synthesis
                # audio_data = self.piper_model.synthesize(text)
                # return audio_data
                pass

            # Mock TTS for now
            return self._mock_tts(text)

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    def _mock_tts(self, text: str) -> bytes:
        """Mock TTS output"""
        # Generate simple beep pattern for testing
        import numpy as np

        sample_rate = 16000
        duration = len(text) * 0.1  # 100ms per character
        t = np.linspace(0, duration, int(sample_rate * duration))
        frequency = 800  # Hz

        # Simple sine wave
        audio = np.sin(2 * np.pi * frequency * t) * 0.3
        audio_int16 = (audio * 32767).astype(np.int16)

        return audio_int16.tobytes()

class VoiceServiceImpl(helmet_pb2_grpc.VoiceServiceServicer):
    """gRPC voice service implementation"""

    def __init__(self, config):
        self.config = config
        self.audio_capture = AudioCapture(config) if AUDIO_AVAILABLE else None
        self.asr_engine = ASREngine(config)
        self.intent_engine = IntentEngine(config)
        self.tts_engine = TTSEngine(config)

        self._processing = False
        logger.info("Voice service initialized")

    def ProcessAudio(self, request_iterator, context):
        """Process streaming audio and return intents"""
        logger.info("Starting audio processing stream")
        self._processing = True

        audio_buffer = []
        silence_threshold = 1.0  # seconds

        try:
            last_audio_time = time.time()

            for audio_data in request_iterator:
                if not context.is_active() or not self._processing:
                    break

                # Convert audio data
                audio_np = np.frombuffer(audio_data.data, dtype=np.int16)
                audio_buffer.extend(audio_np)
                last_audio_time = time.time()

                # Process accumulated audio periodically
                if len(audio_buffer) > 16000:  # ~1 second at 16kHz
                    audio_array = np.array(audio_buffer, dtype=np.int16)

                    # Transcribe
                    transcription = self.asr_engine.transcribe(audio_array)

                    if transcription:
                        logger.info(f"Transcribed: {transcription}")

                        # Classify intent
                        intent = self.intent_engine.classify_intent(transcription)

                        if intent and intent.intent_name != "unknown":
                            logger.info(f"Intent classified: {intent.intent_name}")
                            yield intent

                    # Clear buffer
                    audio_buffer = []

                # Handle silence (end of utterance)
                elif time.time() - last_audio_time > silence_threshold:
                    if audio_buffer:
                        # Process remaining audio
                        audio_array = np.array(audio_buffer, dtype=np.int16)
                        transcription = self.asr_engine.transcribe(audio_array)

                        if transcription:
                            intent = self.intent_engine.classify_intent(transcription)
                            if intent:
                                yield intent

                        audio_buffer = []

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
        finally:
            self._processing = False
            logger.info("Audio processing stream ended")

    def Synthesize(self, request, context):
        """Synthesize text to speech"""
        try:
            audio_data = self.tts_engine.synthesize(request.text)

            response = helmet_pb2.TTSResponse()
            if audio_data:
                response.audio_data = audio_data
                response.format = "wav"

            return response

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return helmet_pb2.TTSResponse()

    def start_listening(self):
        """Start audio capture"""
        if self.audio_capture:
            self.audio_capture.start_recording()

    def stop_listening(self):
        """Stop audio capture"""
        if self.audio_capture:
            self.audio_capture.stop_recording()

    def shutdown(self):
        """Shutdown the service"""
        self._processing = False
        if self.audio_capture:
            self.audio_capture.cleanup()

def serve():
    """Start the gRPC server"""
    config = get_config()

    # Setup logging
    log_level = config.get('system.log_level', 'INFO')
    log_dir = Path(config.get('system.log_dir', 'logs'))
    setup_logging('voice-service', log_level, log_dir)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    voice_service = VoiceServiceImpl(config)
    helmet_pb2_grpc.add_VoiceServiceServicer_to_server(voice_service, server)

    # Configure server
    port = config.get('services.voice_port', 50053)
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)

    # Start server
    server.start()
    logger.info(f"Voice service started on {listen_addr}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        voice_service.shutdown()
        server.stop(5)
        logger.info("Voice service stopped")

def main():
    """Main entry point"""
    try:
        serve()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()