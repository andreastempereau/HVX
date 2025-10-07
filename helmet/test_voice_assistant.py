#!/usr/bin/env python3
"""Test voice assistant functionality"""

import os
import sys
from pathlib import Path

# Add libs to path
sys.path.append(str(Path(__file__).parent / "libs"))
sys.path.append(str(Path(__file__).parent / "apps" / "visor-ui"))

# Load environment
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from voice_assistant import VoiceAssistant
from utils.config import get_config

def test_assistant():
    """Test the voice assistant"""
    print("="*60)
    print("VOICE ASSISTANT TEST")
    print("="*60)

    # Get config
    config = get_config('dev')

    # Get API keys
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    elevenlabs_key = os.environ.get('ELEVENLABS_API_KEY')

    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    if not elevenlabs_key:
        print("ERROR: ELEVENLABS_API_KEY not set")
        return

    print(f"✓ Anthropic API key found: {anthropic_key[:20]}...")
    print(f"✓ ElevenLabs API key found: {elevenlabs_key[:20]}...")

    # Get config
    voice_id = config.get('assistant.voice_id', '21m00Tcm4TlvDq8ikWAM')
    output_device = config.get('assistant.output_device_index', None)
    system_prompt = config.get('assistant.system_prompt',
        "You are a helpful AI assistant integrated into an AR helmet. Provide concise, clear responses suitable for voice interaction.")

    print(f"\nConfiguration:")
    print(f"  Voice ID: {voice_id}")
    print(f"  Output device: {output_device or 'default (pulse -> KT USB Audio)'}")
    print(f"  System prompt: {system_prompt[:80]}...")

    # Create assistant
    print(f"\nInitializing voice assistant...")
    assistant = VoiceAssistant(
        anthropic_api_key=anthropic_key,
        elevenlabs_api_key=elevenlabs_key,
        system_prompt=system_prompt,
        voice_id=voice_id,
        output_device_index=output_device
    )

    print("✓ Assistant initialized")

    # Start assistant
    print("\nStarting assistant...")
    assistant.start()
    print("✓ Assistant started")

    # Send test message
    test_message = "Hello, can you hear me?"
    print(f"\nSending test message: '{test_message}'")
    assistant.process_message(test_message)

    # Wait for processing
    print("\nWaiting for response (this may take a few seconds)...")
    import time
    time.sleep(15)  # Wait for Claude response + TTS + audio playback

    # Stop assistant
    print("\nStopping assistant...")
    assistant.stop()
    print("✓ Assistant stopped")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\nIf you heard a voice response, everything is working!")

if __name__ == '__main__':
    test_assistant()
