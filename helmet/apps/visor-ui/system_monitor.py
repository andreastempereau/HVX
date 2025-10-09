"""System telemetry monitoring for Jetson Orin Nano"""

import threading
import time
import logging
import re
from typing import Dict, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor Jetson system telemetry: CPU/GPU usage, temps, power, RAM"""

    def __init__(self):
        self.is_running = False
        self.thread = None
        self.callback = None

        # Latest telemetry data
        self.telemetry = {
            'cpu_usage': 0.0,  # Average CPU usage %
            'cpu_per_core': [],  # Per-core usage
            'gpu_usage': 0.0,  # GPU usage %
            'ram_used_mb': 0,
            'ram_total_mb': 0,
            'ram_usage': 0.0,  # RAM usage %
            'swap_used_mb': 0,
            'swap_total_mb': 0,
            'cpu_temp': 0.0,  # °C
            'gpu_temp': 0.0,  # °C
            'soc_temp': 0.0,  # °C (average of soc0/1/2)
            'tj_temp': 0.0,   # Junction temp
            'power_total_mw': 0,  # Total power draw (VDD_IN)
            'power_cpu_gpu_mw': 0,  # CPU+GPU power
            'power_soc_mw': 0,  # SoC power
            'timestamp': 0.0
        }

        # Thermal zone mapping
        self.thermal_zones = self._detect_thermal_zones()
        logger.info(f"Detected thermal zones: {self.thermal_zones}")

    def _detect_thermal_zones(self) -> Dict[str, int]:
        """Map thermal zone names to zone numbers"""
        zones = {}
        thermal_path = Path("/sys/class/thermal")

        for zone_dir in thermal_path.glob("thermal_zone*"):
            zone_num = int(zone_dir.name.replace("thermal_zone", ""))
            type_file = zone_dir / "type"

            if type_file.exists():
                zone_type = type_file.read_text().strip()
                zones[zone_type] = zone_num

        return zones

    def _read_thermal_zone(self, zone_name: str) -> float:
        """Read temperature from thermal zone (returns °C)"""
        if zone_name not in self.thermal_zones:
            return 0.0

        zone_num = self.thermal_zones[zone_name]
        temp_file = Path(f"/sys/class/thermal/thermal_zone{zone_num}/temp")

        try:
            # Temperature is in millidegrees Celsius
            temp_millidegrees = int(temp_file.read_text().strip())
            return temp_millidegrees / 1000.0
        except:
            return 0.0

    def _parse_tegrastats_line(self, line: str) -> bool:
        """
        Parse a single line of tegrastats output

        Example line:
        10-09-2025 00:27:03 RAM 5173/7620MB (lfb 1x4MB) SWAP 111/3810MB (cached 0MB)
        CPU [45%@1728,30%@1728,42%@1728,28%@1728,46%@1113,39%@1113] GR3D_FREQ 55%
        cpu@48.781C soc2@48.093C soc0@48.156C gpu@50.718C tj@50.718C soc1@48.281C
        VDD_IN 6030mW/6030mW VDD_CPU_GPU_CV 1913mW/1913mW VDD_SOC 1557mW/1557mW
        """
        try:
            # RAM: "RAM 5173/7620MB"
            ram_match = re.search(r'RAM (\d+)/(\d+)MB', line)
            if ram_match:
                self.telemetry['ram_used_mb'] = int(ram_match.group(1))
                self.telemetry['ram_total_mb'] = int(ram_match.group(2))
                self.telemetry['ram_usage'] = (self.telemetry['ram_used_mb'] / self.telemetry['ram_total_mb']) * 100

            # SWAP: "SWAP 111/3810MB"
            swap_match = re.search(r'SWAP (\d+)/(\d+)MB', line)
            if swap_match:
                self.telemetry['swap_used_mb'] = int(swap_match.group(1))
                self.telemetry['swap_total_mb'] = int(swap_match.group(2))

            # CPU: "CPU [45%@1728,30%@1728,...]"
            cpu_match = re.search(r'CPU \[([\d%@,]+)\]', line)
            if cpu_match:
                cpu_data = cpu_match.group(1)
                # Extract percentages: "45%@1728,30%@1728,..." -> [45, 30, ...]
                percentages = re.findall(r'(\d+)%', cpu_data)
                self.telemetry['cpu_per_core'] = [int(p) for p in percentages]
                self.telemetry['cpu_usage'] = sum(self.telemetry['cpu_per_core']) / len(self.telemetry['cpu_per_core']) if self.telemetry['cpu_per_core'] else 0.0

            # GPU: "GR3D_FREQ 55%"
            gpu_match = re.search(r'GR3D_FREQ (\d+)%', line)
            if gpu_match:
                self.telemetry['gpu_usage'] = int(gpu_match.group(1))

            # Temperatures: "cpu@48.781C gpu@50.718C tj@50.718C soc0@48.156C soc1@48.281C soc2@48.093C"
            temp_matches = re.findall(r'(\w+)@([\d.]+)C', line)
            soc_temps = []
            for name, temp in temp_matches:
                temp_val = float(temp)
                if name == 'cpu':
                    self.telemetry['cpu_temp'] = temp_val
                elif name == 'gpu':
                    self.telemetry['gpu_temp'] = temp_val
                elif name == 'tj':
                    self.telemetry['tj_temp'] = temp_val
                elif name.startswith('soc'):
                    soc_temps.append(temp_val)

            if soc_temps:
                self.telemetry['soc_temp'] = sum(soc_temps) / len(soc_temps)

            # Power: "VDD_IN 6030mW/6030mW VDD_CPU_GPU_CV 1913mW/1913mW VDD_SOC 1557mW/1557mW"
            power_in_match = re.search(r'VDD_IN (\d+)mW', line)
            if power_in_match:
                self.telemetry['power_total_mw'] = int(power_in_match.group(1))

            power_cpu_gpu_match = re.search(r'VDD_CPU_GPU_CV (\d+)mW', line)
            if power_cpu_gpu_match:
                self.telemetry['power_cpu_gpu_mw'] = int(power_cpu_gpu_match.group(1))

            power_soc_match = re.search(r'VDD_SOC (\d+)mW', line)
            if power_soc_match:
                self.telemetry['power_soc_mw'] = int(power_soc_match.group(1))

            self.telemetry['timestamp'] = time.time()
            return True

        except Exception as e:
            logger.error(f"Error parsing tegrastats line: {e}")
            return False

    def _monitor_loop(self):
        """Background monitoring loop using tegrastats"""
        import subprocess

        logger.info("Starting system monitor loop...")

        try:
            # Run tegrastats with 1 second interval
            process = subprocess.Popen(
                ['tegrastats', '--interval', '1000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1
            )

            while self.is_running:
                line = process.stdout.readline()
                if not line:
                    break

                # Parse the line
                if self._parse_tegrastats_line(line):
                    # Call callback if registered
                    if self.callback:
                        self.callback(self.telemetry.copy())

            # Cleanup
            process.terminate()
            process.wait(timeout=2)

        except Exception as e:
            logger.error(f"System monitor error: {e}")
            import traceback
            traceback.print_exc()

        logger.info("System monitor loop stopped")

    def start(self, callback: Optional[Callable[[Dict], None]] = None):
        """
        Start system monitoring

        Args:
            callback: Optional function called with telemetry dict on each update
        """
        if self.is_running:
            return

        self.callback = callback
        self.is_running = True

        # Start monitoring thread
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

        logger.info("System monitor started")

    def stop(self):
        """Stop system monitoring"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=3)

        logger.info("System monitor stopped")

    def get_telemetry(self) -> Dict:
        """Get latest telemetry snapshot"""
        return self.telemetry.copy()

    def get_status_brief(self) -> str:
        """
        Get formatted status brief for voice assistant

        Returns concise summary of system state
        """
        t = self.telemetry

        # Format brief status
        brief = (
            f"System status: "
            f"CPU at {t['cpu_usage']:.0f}%, {t['cpu_temp']:.0f}°C. "
            f"GPU at {t['gpu_usage']:.0f}%, {t['gpu_temp']:.0f}°C. "
            f"RAM {t['ram_usage']:.0f}% used, {t['ram_used_mb']:.0f} of {t['ram_total_mb']:.0f} megabytes. "
            f"Total power draw {t['power_total_mw']/1000:.1f} watts."
        )

        # Add warnings if needed
        warnings = []
        if t['cpu_temp'] > 70:
            warnings.append("CPU temperature elevated")
        if t['gpu_temp'] > 70:
            warnings.append("GPU temperature elevated")
        if t['ram_usage'] > 85:
            warnings.append("RAM usage high")
        if t['power_total_mw'] > 15000:  # >15W
            warnings.append("High power consumption")

        if warnings:
            brief += " Warnings: " + ", ".join(warnings) + "."

        return brief


if __name__ == "__main__":
    """Test system monitor"""
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Starting system monitor test...")

    def print_telemetry(telemetry):
        """Print telemetry updates"""
        print(f"\n{'='*60}")
        print(f"CPU: {telemetry['cpu_usage']:.1f}% avg, {telemetry['cpu_temp']:.1f}°C")
        print(f"  Per-core: {telemetry['cpu_per_core']}")
        print(f"GPU: {telemetry['gpu_usage']:.0f}%, {telemetry['gpu_temp']:.1f}°C")
        print(f"RAM: {telemetry['ram_used_mb']}/{telemetry['ram_total_mb']}MB ({telemetry['ram_usage']:.1f}%)")
        print(f"SWAP: {telemetry['swap_used_mb']}/{telemetry['swap_total_mb']}MB")
        print(f"SoC: {telemetry['soc_temp']:.1f}°C, Junction: {telemetry['tj_temp']:.1f}°C")
        print(f"Power: {telemetry['power_total_mw']/1000:.1f}W total, "
              f"{telemetry['power_cpu_gpu_mw']/1000:.1f}W CPU+GPU, "
              f"{telemetry['power_soc_mw']/1000:.1f}W SoC")
        print(f"{'='*60}")

    monitor = SystemMonitor()
    monitor.start(callback=print_telemetry)

    try:
        print("\nMonitoring system (Ctrl+C to stop)...")
        print("\nStatus brief test:")
        time.sleep(2)  # Wait for first reading
        print(monitor.get_status_brief())

        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        monitor.stop()
        print("Done!")
