#!/usr/bin/env python3
"""Quick test to show raw NMEA data from GPS"""

import serial
import sys

def test_raw_gps(port='/dev/ttyUSB0', baudrate=115200, duration=10):
    """Show raw NMEA sentences from GPS"""
    print(f"Opening {port} at {baudrate} baud...")
    print(f"Will display raw data for {duration} seconds")
    print("="*60)

    try:
        ser = serial.Serial(port, baudrate, timeout=1.0)
        print("Connected! Raw NMEA data:")
        print("="*60)

        import time
        start_time = time.time()
        line_count = 0

        while time.time() - start_time < duration:
            line = ser.readline()
            if line:
                try:
                    line_str = line.decode('ascii', errors='ignore').strip()
                    if line_str:
                        line_count += 1
                        print(f"{line_count:3d}: {line_str}")
                except:
                    pass

        ser.close()
        print("="*60)
        print(f"Received {line_count} NMEA sentences in {duration} seconds")

        if line_count == 0:
            print("\nWARNING: No data received from GPS!")
            print("Check:")
            print("  1. Is the GPS powered on?")
            print("  2. Is the antenna connected?")
            print("  3. Try a different baud rate (9600 or 38400)")
        else:
            print("\nGPS is transmitting data successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_raw_gps()
