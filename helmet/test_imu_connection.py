#!/usr/bin/env python3
"""
BNO055 IMU Connection Diagnostic Tool
Continuously scans I2C buses to detect when IMU appears
"""

import time
import sys
from smbus2 import SMBus

# BNO055 configuration
BNO055_CHIP_ID = 0xA0
BNO055_CHIP_ID_ADDR = 0x00
BNO055_ADDRESSES = [0x28, 0x29]  # Default addresses
I2C_BUSES = [0, 1, 2, 4, 5, 7, 9, 10]

def test_single_bus_address(bus_num, addr):
    """Test a single bus/address combination"""
    try:
        bus = SMBus(bus_num)
        chip_id = bus.read_byte_data(addr, BNO055_CHIP_ID_ADDR)
        bus.close()
        return chip_id
    except Exception as e:
        return None

def scan_for_imu():
    """Scan all buses for BNO055"""
    results = []
    for bus_num in I2C_BUSES:
        for addr in BNO055_ADDRESSES:
            chip_id = test_single_bus_address(bus_num, addr)
            if chip_id is not None:
                results.append((bus_num, addr, chip_id))
    return results

def main():
    print("=" * 70)
    print("BNO055 IMU CONNECTION DIAGNOSTIC")
    print("=" * 70)
    print("\nThis tool will continuously scan for your IMU.")
    print("Adjust the wiring and watch for detection.\n")

    print("BNO055 Wiring Guide:")
    print("  VIN  → 3.3V or 5V (check your module)")
    print("  GND  → Ground")
    print("  SDA  → I2C Data (GPIO pin)")
    print("  SCL  → I2C Clock (GPIO pin)")
    print("  PS0  → GND (for I2C mode)")
    print("  PS1  → GND (for I2C mode)\n")

    print("Common Issues:")
    print("  • Loose connections")
    print("  • Wrong voltage (some BNO055 modules are 3.3V only)")
    print("  • SDA/SCL swapped")
    print("  • PS0/PS1 not grounded (puts sensor in UART mode)")
    print("  • Pull-up resistors missing (usually built-in)\n")

    print("Starting scan... (Press Ctrl+C to exit)\n")

    scan_count = 0
    last_found = None

    try:
        while True:
            scan_count += 1
            results = scan_for_imu()

            # Clear line and print status
            sys.stdout.write(f"\rScan #{scan_count}: ", )

            if results:
                for bus_num, addr, chip_id in results:
                    if chip_id == BNO055_CHIP_ID:
                        msg = f"✓ BNO055 FOUND on bus {bus_num}, address 0x{addr:02x}!"
                        print(f"\n{'='*70}")
                        print(msg)
                        print(f"{'='*70}")
                        print(f"\nUpdate your config to use:")
                        print(f"  gyro.i2c_bus = {bus_num}")
                        print(f"\nYou can test it with:")
                        print(f"  python3 -c \"from apps.visor_ui.gyro_sensor import GyroSensor; s=GyroSensor(i2c_bus={bus_num}); print('Success!' if s.sensor else 'Failed')\"")
                        sys.exit(0)
                    else:
                        sys.stdout.write(f"Device at bus {bus_num}, addr 0x{addr:02x} (ID: 0x{chip_id:02x}, not BNO055)")
            else:
                sys.stdout.write("No I2C devices responding...")

            sys.stdout.flush()
            time.sleep(0.5)  # Scan every 0.5 seconds

    except KeyboardInterrupt:
        print("\n\nScan stopped by user.")
        print("\nIf IMU was not detected, check:")
        print("  1. Power LED on IMU module (if present)")
        print("  2. Voltage level (3.3V vs 5V)")
        print("  3. Physical connection of all 4 wires")
        print("  4. PS0 and PS1 pins grounded for I2C mode")
        sys.exit(0)

if __name__ == "__main__":
    main()
