#!/usr/bin/env python3
"""Scan for BNO055 IMU on all I2C buses"""

from smbus2 import SMBus
import sys

BNO055_CHIP_ID = 0xA0
BNO055_ADDRESSES = [0x28, 0x29]  # Common BNO055 addresses
I2C_BUSES = [0, 1, 2, 4, 5, 7, 9, 10, 11]  # Available buses on your system

print("Scanning for BNO055 IMU...")
print("="*60)

found_devices = []

for bus_num in I2C_BUSES:
    for addr in BNO055_ADDRESSES:
        try:
            with SMBus(bus_num) as bus:
                # Try to read chip ID register (address 0x00)
                chip_id = bus.read_byte_data(addr, 0x00)

                if chip_id == BNO055_CHIP_ID:
                    print(f"✓ FOUND BNO055 on bus {bus_num} at address 0x{addr:02X}")
                    print(f"  Chip ID: 0x{chip_id:02X} (correct)")
                    found_devices.append((bus_num, addr))
                else:
                    print(f"⚠ Device on bus {bus_num} at 0x{addr:02X} but wrong chip ID: 0x{chip_id:02X}")

        except Exception as e:
            # Device not found at this address - this is normal
            pass

print("="*60)

if found_devices:
    print(f"\nFound {len(found_devices)} BNO055 sensor(s):")
    for bus, addr in found_devices:
        print(f"  - Bus {bus}, Address 0x{addr:02X}")
        print(f"\nTo use this sensor, update your config:")
        print(f"  gyro.i2c_bus={bus}")
else:
    print("\n❌ No BNO055 sensors found!")
    print("\nPossible issues:")
    print("  1. Sensor is not connected properly")
    print("  2. Sensor is not powered")
    print("  3. Wrong I2C pins/connections")
    print("  4. Sensor is on a different bus not scanned")
    print("\nTry:")
    print("  - Check physical connection")
    print("  - Check power LED on sensor board")
    print("  - Verify I2C wiring (SDA, SCL, VCC, GND)")
