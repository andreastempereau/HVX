#!/usr/bin/env python3
"""Standalone wake word detector test - verifies microphone and model are working"""

import sys
import time

# Test 1: Check openwakeword installation
print("=" * 60)
print("WAKE WORD DETECTOR TEST")
print("=" * 60)

print("\n[1/6] Checking openwakeword installation...")
try:
    from openwakeword.model import Model
    print(f"✓ openwakeword installed")
except ImportError as e:
    print(f"✗ openwakeword not installed: {e}")
    print("Install with: pip install openwakeword")
    sys.exit(1)

# Test 2: Check PyAudio installation
print("\n[2/6] Checking PyAudio installation...")
try:
    import pyaudio
    print(f"✓ PyAudio installed")
except ImportError as e:
    print(f"✗ PyAudio not installed: {e}")
    print("Install with: pip install pyaudio")
    sys.exit(1)

# Test 3: List audio devices
print("\n[3/6] Listing audio input devices...")
p = pyaudio.PyAudio()
print("\nAvailable audio input devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f"  Device {i}: {info['name']}")
        print(f"    Channels: {info['maxInputChannels']}")
        print(f"    Sample rates: {info['defaultSampleRate']}Hz")
p.terminate()

# Test 4: Load wake word model
print("\n[4/6] Loading wake word model...")
try:
    model = Model(
        wakeword_models=["hey_jarvis"],
        inference_framework="tflite"
    )
    print(f"✓ Model loaded successfully")
    print(f"  Available models: {list(model.models.keys())}")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Open audio stream on device 4
print("\n[5/6] Opening audio stream on device 4...")
DEVICE_INDEX = 4
TARGET_RATE = 16000
CHUNK = 1280

p = pyaudio.PyAudio()
try:
    # Try to open stream on device 4
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=TARGET_RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK,
    )
    print(f"✓ Audio stream opened on device {DEVICE_INDEX} at {TARGET_RATE}Hz")
    stream.close()
except Exception as e:
    print(f"✗ Failed to open audio stream: {e}")
    print("\nTrying with auto sample rate detection...")

    # Try different sample rates
    for test_rate in [16000, 48000, 44100]:
        try:
            chunk_size = int(CHUNK * test_rate / TARGET_RATE)
            print(f"  Testing {test_rate}Hz...")
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=test_rate,
                input=True,
                input_device_index=DEVICE_INDEX,
                frames_per_buffer=chunk_size,
            )
            print(f"  ✓ Success at {test_rate}Hz")
            stream.close()
            TARGET_RATE = test_rate
            CHUNK = chunk_size
            break
        except Exception as e2:
            print(f"  ✗ {test_rate}Hz failed: {e2}")
            if test_rate == 44100:
                p.terminate()
                sys.exit(1)

# Test 6: Run live detection for 30 seconds
print("\n[6/6] Running live wake word detection...")
print(f"Listening for 'hey jarvis' for 30 seconds...")
print("(Try saying 'hey jarvis' into the microphone)")
print("-" * 60)

import numpy as np

try:
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=TARGET_RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK,
    )

    start_time = time.time()
    frame_count = 0
    max_score = 0.0

    while time.time() - start_time < 30:
        # Read audio
        audio_data = stream.read(CHUNK, exception_on_overflow=False)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Get prediction
        prediction = model.predict(audio_array)

        frame_count += 1

        # Track max score
        for keyword, score in prediction.items():
            if score > max_score:
                max_score = score

        # Print status every 50 frames (~4 seconds)
        if frame_count % 50 == 0:
            elapsed = time.time() - start_time
            scores_str = ", ".join([f"{k}: {v:.3f}" for k, v in prediction.items()])
            print(f"[{elapsed:5.1f}s] {scores_str} (max so far: {max_score:.3f})")

        # Check for detection (threshold 0.5)
        for keyword, score in prediction.items():
            if score > 0.5:
                print(f"\n🎤 WAKE WORD DETECTED: '{keyword}' (confidence: {score:.2f})")
                print(f"✓ Wake word detection is working!")
                stream.close()
                p.terminate()
                sys.exit(0)

    stream.close()
    p.terminate()

    print(f"\n⚠ No wake word detected in 30 seconds")
    print(f"Max score observed: {max_score:.3f} (threshold is 0.5)")
    print("\nPossible issues:")
    print("  - Microphone not picking up audio (check volume/positioning)")
    print("  - Wake phrase unclear (try speaking louder/clearer)")
    print("  - Wrong microphone selected (check device list above)")

except KeyboardInterrupt:
    print("\n\nTest interrupted by user")
    stream.close()
    p.terminate()
except Exception as e:
    print(f"\n✗ Error during detection: {e}")
    import traceback
    traceback.print_exc()
    stream.close()
    p.terminate()
    sys.exit(1)
