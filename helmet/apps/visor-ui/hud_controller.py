"""HUD (Heads-Up Display) controller for system status"""

import psutil
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class HUDController:
    """Controller for HUD status and telemetry"""

    def __init__(self, config, system_monitor=None):
        self.config = config
        self.frame_count = 0
        self.last_fps_time = 0
        self.current_fps = 0

        # FPS tracking
        self.fps_window = []  # Rolling window of frame times
        self.fps_window_size = 30  # Track last 30 frames
        self.last_frame_time = time.time()

        # System monitor (optional - provides real telemetry)
        self.system_monitor = system_monitor

    def get_status(self) -> Dict[str, Any]:
        """Get current system status for HUD display"""
        try:
            # Get telemetry from system monitor if available
            if self.system_monitor:
                telemetry = self.system_monitor.get_telemetry()
                cpu_usage = telemetry['cpu_usage']
                memory_usage = telemetry['ram_usage']
                temperature = telemetry['cpu_temp']
            else:
                # Fallback to psutil
                cpu_usage = self._get_cpu_usage()
                memory_usage = self._get_memory_usage()
                temperature = self._get_temperature()

            status = {
                # System metrics
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'temperature': temperature,
                'battery_level': self._get_battery_level(),

                # Application metrics
                'fps': self.current_fps,
                'recording': False,  # TODO: Implement recording status
                'mode': 'normal',   # TODO: Get from orchestrator

                # Display settings
                'show_fps': self.config.get('ui.hud.show_fps', True),
                'show_battery': self.config.get('ui.hud.show_battery', True),
                'show_temp': self.config.get('ui.hud.show_temp', True),
                'overlay_alpha': self.config.get('ui.hud.overlay_alpha', 0.8),

                # Voice status
                'mic_active': False,  # TODO: Get from voice service
                'mic_level': 0.0,     # TODO: Get from voice service

                # Detection count
                'detection_count': 0,  # TODO: Get from perception

                # Status message
                'status_message': 'System operational'
            }

            return status

        except Exception as e:
            logger.error(f"Error getting HUD status: {e}")
            return self._get_fallback_status()

    def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage"""
        try:
            return psutil.cpu_percent(interval=None)
        except:
            return 0.0

    def _get_memory_usage(self) -> float:
        """Get memory usage percentage"""
        try:
            return psutil.virtual_memory().percent
        except:
            return 0.0

    def _get_temperature(self) -> float:
        """Get system temperature (CPU)"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Get first available temperature sensor
                for sensor_name, sensor_list in temps.items():
                    if sensor_list:
                        return sensor_list[0].current
            return 0.0
        except:
            # Fallback: try to read from common Linux paths
            try:
                temp_paths = [
                    '/sys/class/thermal/thermal_zone0/temp',
                    '/sys/class/hwmon/hwmon0/temp1_input'
                ]
                for temp_path in temp_paths:
                    if Path(temp_path).exists():
                        with open(temp_path, 'r') as f:
                            temp = int(f.read().strip())
                            # Convert millidegrees to degrees if needed
                            if temp > 1000:
                                temp = temp / 1000
                            return float(temp)
            except:
                pass
            return 0.0

    def _get_battery_level(self) -> float:
        """Get battery level percentage"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return battery.percent
            return 100.0  # Assume full charge if no battery info
        except:
            return 100.0

    def update_fps(self, fps: float):
        """Update FPS counter"""
        self.current_fps = fps

    def record_frame(self):
        """
        Record a frame for FPS calculation

        Call this each time a frame is rendered to track actual FPS
        """
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        self.last_frame_time = current_time

        # Add to rolling window
        self.fps_window.append(frame_time)
        if len(self.fps_window) > self.fps_window_size:
            self.fps_window.pop(0)

        # Calculate FPS from average frame time
        if len(self.fps_window) > 0:
            avg_frame_time = sum(self.fps_window) / len(self.fps_window)
            if avg_frame_time > 0:
                self.current_fps = round(1.0 / avg_frame_time, 1)
            else:
                self.current_fps = 0

        self.frame_count += 1

    def update_detection_count(self, count: int):
        """Update detection count"""
        self._detection_count = count

    def _get_fallback_status(self) -> Dict[str, Any]:
        """Fallback status when there are errors"""
        return {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'temperature': 0.0,
            'battery_level': 100.0,
            'fps': 0,
            'recording': False,
            'mode': 'error',
            'show_fps': True,
            'show_battery': True,
            'show_temp': True,
            'overlay_alpha': 0.8,
            'mic_active': False,
            'mic_level': 0.0,
            'detection_count': 0,
            'status_message': 'System error'
        }