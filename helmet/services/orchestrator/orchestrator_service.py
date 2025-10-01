#!/usr/bin/env python3
"""Orchestrator service for system coordination and state management"""

import asyncio
import logging
import sqlite3
import json
import time
from concurrent import futures
from pathlib import Path
from datetime import datetime
import sys
from typing import Dict, Any, Optional

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
import psutil

# Add libs to path
sys.path.append(str(Path(__file__).parent.parent.parent / "libs"))
from utils.config import get_config
from utils.logging_utils import setup_logging, log_performance
from messages import helmet_pb2, helmet_pb2_grpc

logger = logging.getLogger(__name__)

class SystemState:
    """Manages system state and configuration"""

    def __init__(self, config):
        self.config = config
        self.db_path = Path(config.get('system.log_dir', 'logs')) / 'system_state.db'
        self.current_mode = "normal"
        self.recording = False
        self.brightness = 100
        self.zoom_level = 1.0
        self.marked_targets = []

        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for state persistence"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        timestamp TEXT
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS telemetry_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        component TEXT,
                        metric TEXT,
                        value REAL
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS command_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        intent TEXT,
                        action TEXT,
                        parameters TEXT,
                        success BOOLEAN
                    )
                ''')

            logger.info(f"Database initialized: {self.db_path}")
            self._load_state()

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    def _load_state(self):
        """Load persisted state from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT key, value FROM system_state')
                for key, value in cursor.fetchall():
                    if key == 'mode':
                        self.current_mode = value
                    elif key == 'recording':
                        self.recording = value == 'true'
                    elif key == 'brightness':
                        self.brightness = float(value)
                    elif key == 'zoom_level':
                        self.zoom_level = float(value)

            logger.info("System state loaded from database")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def _save_state(self, key: str, value: Any):
        """Save state to database"""
        try:
            timestamp = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO system_state (key, value, timestamp) VALUES (?, ?, ?)',
                    (key, str(value), timestamp)
                )
            logger.debug(f"State saved: {key} = {value}")

        except Exception as e:
            logger.error(f"Failed to save state {key}: {e}")

    def set_mode(self, mode: str) -> bool:
        """Set system operating mode"""
        valid_modes = ["normal", "night", "navigation", "debug", "emergency"]
        if mode in valid_modes:
            self.current_mode = mode
            self._save_state('mode', mode)
            logger.info(f"Mode changed to: {mode}")
            return True
        else:
            logger.warning(f"Invalid mode: {mode}")
            return False

    def toggle_recording(self, enabled: Optional[bool] = None) -> bool:
        """Toggle or set recording state"""
        if enabled is None:
            self.recording = not self.recording
        else:
            self.recording = enabled

        self._save_state('recording', self.recording)
        logger.info(f"Recording {'started' if self.recording else 'stopped'}")
        return True

    def adjust_brightness(self, direction: str) -> bool:
        """Adjust display brightness"""
        if direction == "up":
            self.brightness = min(100, self.brightness + 10)
        elif direction == "down":
            self.brightness = max(10, self.brightness - 10)
        else:
            return False

        self._save_state('brightness', self.brightness)
        logger.info(f"Brightness adjusted to: {self.brightness}%")
        return True

    def adjust_zoom(self, direction: str) -> bool:
        """Adjust zoom level"""
        if direction == "in":
            self.zoom_level = min(5.0, self.zoom_level * 1.2)
        elif direction == "out":
            self.zoom_level = max(0.5, self.zoom_level / 1.2)
        else:
            return False

        self._save_state('zoom_level', self.zoom_level)
        logger.info(f"Zoom level adjusted to: {self.zoom_level:.1f}x")
        return True

    def mark_target(self, x: float = 0.5, y: float = 0.5) -> bool:
        """Mark a target at specified coordinates"""
        target = {
            "id": len(self.marked_targets) + 1,
            "x": x,
            "y": y,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.marked_targets.append(target)
        logger.info(f"Target marked at ({x:.2f}, {y:.2f})")
        return True

    def emergency_mode(self) -> bool:
        """Activate emergency mode"""
        self.current_mode = "emergency"
        self.recording = True  # Auto-start recording
        self._save_state('mode', self.current_mode)
        self._save_state('recording', self.recording)
        logger.critical("EMERGENCY MODE ACTIVATED")
        return True

    def log_telemetry(self, component: str, metric: str, value: float):
        """Log telemetry data"""
        try:
            timestamp = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT INTO telemetry_log (timestamp, component, metric, value) VALUES (?, ?, ?, ?)',
                    (timestamp, component, metric, value)
                )
        except Exception as e:
            logger.error(f"Failed to log telemetry: {e}")

    def log_command(self, intent: str, action: str, parameters: Dict, success: bool):
        """Log executed commands"""
        try:
            timestamp = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT INTO command_log (timestamp, intent, action, parameters, success) VALUES (?, ?, ?, ?, ?)',
                    (timestamp, intent, action, json.dumps(parameters), success)
                )
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

class ServiceClients:
    """Manages connections to other services"""

    def __init__(self, config):
        self.config = config
        self.video_client = None
        self.perception_client = None
        self.voice_client = None
        self._connect_services()

    def _connect_services(self):
        """Connect to other services"""
        try:
            # These would be actual gRPC clients in production
            # For now, we'll create mock connections
            logger.info("Connecting to services...")

            # Video service
            video_port = self.config.get('services.video_port', 50051)
            self.video_channel = grpc.insecure_channel(f'localhost:{video_port}')
            self.video_client = helmet_pb2_grpc.VideoServiceStub(self.video_channel)

            # Perception service
            perception_port = self.config.get('services.perception_port', 50052)
            self.perception_channel = grpc.insecure_channel(f'localhost:{perception_port}')
            self.perception_client = helmet_pb2_grpc.PerceptionServiceStub(self.perception_channel)

            # Voice service
            voice_port = self.config.get('services.voice_port', 50053)
            self.voice_channel = grpc.insecure_channel(f'localhost:{voice_port}')
            self.voice_client = helmet_pb2_grpc.VoiceServiceStub(self.voice_channel)

            logger.info("Service connections established")

        except Exception as e:
            logger.error(f"Failed to connect to services: {e}")

    def disconnect(self):
        """Disconnect from services"""
        for channel_name in ['video_channel', 'perception_channel', 'voice_channel']:
            channel = getattr(self, channel_name, None)
            if channel:
                channel.close()

class OrchestratorServiceImpl(helmet_pb2_grpc.OrchestratorServiceServicer):
    """gRPC orchestrator service implementation"""

    def __init__(self, config):
        self.config = config
        self.system_state = SystemState(config)
        self.service_clients = ServiceClients(config)
        self._status_cache = {}
        self._last_status_update = 0

        logger.info("Orchestrator service initialized")

    def ExecuteCommand(self, request, context):
        """Execute system commands from voice intents or UI"""
        try:
            action = request.action
            parameters = dict(request.parameters)

            logger.info(f"Executing command: {action} with params: {parameters}")

            success = False
            message = ""

            # Route commands to appropriate handlers
            if action == "set_mode":
                mode = parameters.get("mode", "normal")
                success = self.system_state.set_mode(mode)
                message = f"Mode set to {mode}" if success else f"Invalid mode: {mode}"

            elif action == "toggle_recording":
                enabled = parameters.get("enabled")
                if enabled is not None:
                    enabled = str(enabled).lower() == "true"
                success = self.system_state.toggle_recording(enabled)
                message = f"Recording {'started' if self.system_state.recording else 'stopped'}"

            elif action == "adjust_brightness":
                direction = parameters.get("direction", "up")
                success = self.system_state.adjust_brightness(direction)
                message = f"Brightness adjusted {direction}"

            elif action == "adjust_zoom":
                direction = parameters.get("direction", "in")
                success = self.system_state.adjust_zoom(direction)
                message = f"Zoom adjusted {direction}"

            elif action == "mark_target":
                x = float(parameters.get("x", 0.5))
                y = float(parameters.get("y", 0.5))
                success = self.system_state.mark_target(x, y)
                message = "Target marked"

            elif action == "screenshot":
                success = self._take_screenshot()
                message = "Screenshot captured" if success else "Screenshot failed"

            elif action == "emergency_mode":
                success = self.system_state.emergency_mode()
                message = "Emergency mode activated"

            elif action == "system_status":
                success = True
                message = self._get_system_status_message()

            elif action == "describe_scene":
                success, message = self._describe_current_scene()

            elif action == "ui_command":
                command = parameters.get("command", "")
                success = self._handle_ui_command(command)
                message = f"UI command executed: {command}" if success else f"UI command failed: {command}"

            else:
                success = False
                message = f"Unknown action: {action}"

            # Log command execution
            self.system_state.log_command(
                intent=parameters.get("intent", "unknown"),
                action=action,
                parameters=parameters,
                success=success
            )

            # Create response
            response = helmet_pb2.CommandResponse()
            response.success = success
            response.message = message
            response.timestamp.GetCurrentTime()

            return response

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            response = helmet_pb2.CommandResponse()
            response.success = False
            response.message = f"Command failed: {str(e)}"
            response.timestamp.GetCurrentTime()
            return response

    def GetStatus(self, request, context):
        """Get current system status"""
        try:
            status = self._get_hud_status()
            return status
        except Exception as e:
            logger.error(f"Status retrieval error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return helmet_pb2.HUDStatus()

    def StreamStatus(self, request, context):
        """Stream system status updates"""
        logger.info("Starting status stream")

        try:
            while context.is_active():
                status = self._get_hud_status()
                yield status

                # Update every second
                time.sleep(1.0)

        except Exception as e:
            logger.error(f"Status stream error: {e}")

    def _get_hud_status(self) -> helmet_pb2.HUDStatus:
        """Get current HUD status"""
        current_time = time.time()

        # Cache status for 1 second to avoid excessive computation
        if current_time - self._last_status_update < 1.0:
            return self._status_cache.get('hud_status', helmet_pb2.HUDStatus())

        try:
            # System metrics
            system_status = helmet_pb2.SystemStatus()
            system_status.cpu_usage = psutil.cpu_percent(interval=None)
            system_status.memory_usage = psutil.virtual_memory().percent
            system_status.temperature = self._get_temperature()
            system_status.battery_level = self._get_battery_level()
            system_status.recording = self.system_state.recording
            system_status.current_mode = self.system_state.current_mode
            system_status.timestamp.GetCurrentTime()

            # HUD status
            hud_status = helmet_pb2.HUDStatus()
            hud_status.system.CopyFrom(system_status)
            hud_status.mic_active = False  # TODO: Get from voice service
            hud_status.mic_level = 0.0     # TODO: Get from voice service
            hud_status.fps = 30            # TODO: Get from video service
            hud_status.detection_count = 0  # TODO: Get from perception service
            hud_status.status_message = self._get_status_message()

            # Log telemetry
            self.system_state.log_telemetry("system", "cpu_usage", system_status.cpu_usage)
            self.system_state.log_telemetry("system", "memory_usage", system_status.memory_usage)
            self.system_state.log_telemetry("system", "temperature", system_status.temperature)

            # Cache result
            self._status_cache['hud_status'] = hud_status
            self._last_status_update = current_time

            return hud_status

        except Exception as e:
            logger.error(f"Error getting HUD status: {e}")
            return helmet_pb2.HUDStatus()

    def _get_temperature(self) -> float:
        """Get system temperature"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for sensor_name, sensor_list in temps.items():
                    if sensor_list:
                        return sensor_list[0].current
        except:
            pass
        return 45.0  # Default temperature

    def _get_battery_level(self) -> float:
        """Get battery level"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return battery.percent
        except:
            pass
        return 100.0  # Default to full battery

    def _get_status_message(self) -> str:
        """Get current status message"""
        if self.system_state.current_mode == "emergency":
            return "EMERGENCY MODE ACTIVE"
        elif self.system_state.recording:
            return "Recording in progress"
        elif self.system_state.current_mode == "night":
            return "Night vision active"
        elif self.system_state.current_mode == "navigation":
            return "Navigation mode active"
        else:
            return "System operational"

    def _get_system_status_message(self) -> str:
        """Get detailed system status"""
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        temp = self._get_temperature()

        status_items = []
        if cpu > 80:
            status_items.append("High CPU usage")
        if mem > 80:
            status_items.append("High memory usage")
        if temp > 70:
            status_items.append("High temperature")

        if status_items:
            return "System warnings: " + ", ".join(status_items)
        else:
            return "All systems nominal"

    def _take_screenshot(self) -> bool:
        """Take a screenshot (mock implementation)"""
        try:
            # In a real implementation, this would capture the current frame
            # and save it to the recordings directory
            recording_dir = Path(self.config.get('system.recording_dir', 'recordings'))
            recording_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = recording_dir / f"screenshot_{timestamp}.jpg"

            # Mock screenshot creation
            logger.info(f"Screenshot saved: {screenshot_path}")
            return True

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False

    def _describe_current_scene(self):
        """Describe the current scene using perception data"""
        try:
            # In a real implementation, this would get the latest perception results
            # and generate a natural language description
            description = "I can see several objects in the current view including people and vehicles."
            return True, description

        except Exception as e:
            logger.error(f"Scene description failed: {e}")
            return False, "Unable to analyze current scene"

    def _handle_ui_command(self, command: str) -> bool:
        """Handle UI-specific commands (overlays, crosshairs, etc.)"""
        try:
            # Store UI state for the UI to query
            if command in ["show_hud", "show_detections", "hide_overlays", "show_crosshair"]:
                self.system_state._save_state(f'ui_{command}', 'true')
                logger.info(f"UI command processed: {command}")
                return True
            else:
                logger.warning(f"Unknown UI command: {command}")
                return False

        except Exception as e:
            logger.error(f"UI command failed: {e}")
            return False

    def shutdown(self):
        """Shutdown the orchestrator"""
        if self.service_clients:
            self.service_clients.disconnect()

def serve():
    """Start the gRPC server"""
    config = get_config()

    # Setup logging
    log_level = config.get('system.log_level', 'INFO')
    log_dir = Path(config.get('system.log_dir', 'logs'))
    setup_logging('orchestrator-service', log_level, log_dir)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    orchestrator_service = OrchestratorServiceImpl(config)
    helmet_pb2_grpc.add_OrchestratorServiceServicer_to_server(orchestrator_service, server)

    # Configure server
    port = config.get('services.orchestrator_port', 50054)
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)

    # Start server
    server.start()
    logger.info(f"Orchestrator service started on {listen_addr}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        orchestrator_service.shutdown()
        server.stop(5)
        logger.info("Orchestrator service stopped")

def main():
    """Main entry point"""
    try:
        serve()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()