#!/usr/bin/env python3
"""
Simple test script for BNO055 gyroscope sensor
"""

import time
from gyro_sensor import GyroSensor

def on_orientation_update(data):
    """Callback for orientation updates"""
    euler = data['euler']
    calibration = data['calibration']

    # Clear screen and print orientation
    print("\033[2J\033[H")  # Clear screen
    print("=" * 60)
    print("BNO055 Orientation Test")
    print("=" * 60)
    print(f"\nHeading: {euler[0]:>8.2f}°")
    print(f"Roll:    {euler[1]:>8.2f}°  (Tilt left/right)")
    print(f"Pitch:   {euler[2]:>8.2f}°  (Tilt forward/back)")
    print(f"\nCalibration Status (0-3, 3=best):")
    print(f"  System:  {calibration[0]}")
    print(f"  Gyro:    {calibration[1]}")
    print(f"  Accel:   {calibration[2]}")
    print(f"  Mag:     {calibration[3]}")
    print("\nPress Ctrl+C to exit")

def main():
    print("Initializing BNO055 on I2C bus 7...")
    sensor = GyroSensor(i2c_bus=7)

    if not sensor.sensor:
        print("ERROR: Failed to initialize sensor")
        return

    print("Starting sensor (30 Hz)...")
    sensor.start(callback=on_orientation_update, rate_hz=30)

    print("\nTilt your head to see orientation changes!\n")

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping sensor...")
        sensor.stop()
        print("Done!")

if __name__ == "__main__":
    main()
