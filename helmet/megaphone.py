#!/usr/bin/env python3
"""
Megaphone - Real-time audio passthrough from I2S/USB microphone to AB13X speaker
"""

import pyaudio
import signal
import sys

# Audio settings
CHUNK = 1024  # Buffer size (smaller = lower latency, but more CPU)
FORMAT = pyaudio.paInt16  # 16-bit audio
CHANNELS = 1  # Mono
RATE = 48000  # Sample rate (48kHz)
VOLUME = 1.5  # Volume multiplier (0.0-2.0)

# Audio device configuration
# INPUT: Adafruit SPH0645 I2S microphone on 40-pin header (APE card, device 0)
# OUTPUT: AB13X USB Audio speaker
INPUT_DEVICE_NAME = "NVIDIA Jetson Orin Nano APE"  # SPH0645 on I2S/APE
INPUT_DEVICE_CARD = 5  # APE card
INPUT_DEVICE_SUBDEV = 0  # First I2S device
OUTPUT_DEVICE_NAME = "AB13X USB Audio"  # AB13X speaker

running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global running
    print("\n[Megaphone] Stopping...")
    running = False


def find_device_by_name(p, device_name, is_input=True):
    """Find audio device by name"""
    device_count = p.get_device_count()

    for i in range(device_count):
        info = p.get_device_info_by_index(i)
        name = info['name']

        # Check if this matches the device name
        if device_name.lower() in name.lower():
            # Make sure it has the right capability
            if is_input and info['maxInputChannels'] > 0:
                return i, info
            elif not is_input and info['maxOutputChannels'] > 0:
                return i, info

    return None, None


def main():
    global running

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    print("="*60)
    print("MEGAPHONE - Real-time Audio Passthrough")
    print("="*60)
    print("Press Ctrl+C to stop")
    print()

    # Initialize PyAudio
    p = pyaudio.PyAudio()

    try:
        # List all devices for debugging
        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"  [{i}] {info['name']} (in:{info['maxInputChannels']}, out:{info['maxOutputChannels']})")
        print()

        # Find input device (SPH0645 on I2S/APE)
        input_device, input_info = find_device_by_name(p, INPUT_DEVICE_NAME, is_input=True)

        if input_device is None:
            print(f"[ERROR] Could not find input device: {INPUT_DEVICE_NAME}")
            print("Make sure the Adafruit SPH0645 I2S microphone is properly configured.")
            return

        # Find output device (AB13X speaker)
        output_device, output_info = find_device_by_name(p, OUTPUT_DEVICE_NAME, is_input=False)

        if output_device is None:
            print(f"[ERROR] Could not find output device: {OUTPUT_DEVICE_NAME}")
            return

        print(f"Input device: [{input_device}] {input_info['name']}")
        print(f"Output device: [{output_device}] {output_info['name']}")
        print(f"Sample rate: {RATE} Hz")
        print(f"Channels: {CHANNELS}")
        print(f"Buffer size: {CHUNK} samples ({CHUNK/RATE*1000:.1f} ms)")
        print(f"Volume: {VOLUME*100:.0f}%")
        print()

        # Open input stream (microphone)
        stream_in = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=input_device,
            frames_per_buffer=CHUNK
        )

        # Open output stream (speaker)
        stream_out = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            output_device_index=output_device,
            frames_per_buffer=CHUNK
        )

        print("[Megaphone] Running... speak into the microphone!")
        print()

        # Main loop - read from mic and write to speaker
        while running:
            try:
                # Read audio from microphone
                data = stream_in.read(CHUNK, exception_on_overflow=False)

                # Apply volume if needed
                if VOLUME != 1.0:
                    import numpy as np
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    audio_np = (audio_np * VOLUME).astype(np.int16)
                    data = audio_np.tobytes()

                # Write audio to speaker
                stream_out.write(data)

            except Exception as e:
                print(f"[Error] {e}")
                break

        # Cleanup
        print("[Megaphone] Cleaning up...")
        stream_in.stop_stream()
        stream_in.close()
        stream_out.stop_stream()
        stream_out.close()
        p.terminate()

        print("[Megaphone] Stopped")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        p.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
