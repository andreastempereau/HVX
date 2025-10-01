"""Configuration management for helmet services"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration manager"""

    def __init__(self, profile: str = "dev"):
        self.profile = profile
        self.config_dir = Path(__file__).parent.parent.parent / "configs"
        self.profile_path = self.config_dir / "profiles" / f"{profile}.json"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from profile file"""
        try:
            if self.profile_path.exists():
                with open(self.profile_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded config profile: {self.profile}")
                return config
            else:
                logger.warning(f"Config file not found: {self.profile_path}")
                return self._default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration fallback"""
        return {
            "video": {
                "mock_source": True,
                "source_path": "demo.mp4",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "format": "RGB"
            },
            "perception": {
                "model_path": "models/yolov8n.onnx",
                "confidence_threshold": 0.5,
                "nms_threshold": 0.4,
                "max_detections": 100,
                "input_size": [640, 640],
                "device": "cpu"
            },
            "voice": {
                "asr_model": "small",
                "language": "en",
                "mic_device": "default",
                "tts_voice": "en_US-ljspeech-medium",
                "sample_rate": 16000
            },
            "ui": {
                "fullscreen": True,
                "dual_eye": True,
                "lens_correction": {
                    "enabled": True,
                    "barrel_distortion": 0.1,
                    "left_offset": [-0.05, 0.0],
                    "right_offset": [0.05, 0.0]
                },
                "hud": {
                    "show_fps": True,
                    "show_battery": True,
                    "show_temp": True,
                    "overlay_alpha": 0.8
                }
            },
            "system": {
                "log_level": "INFO",
                "log_dir": "logs",
                "telemetry_enabled": True,
                "recording_dir": "recordings"
            },
            "services": {
                "video_port": 50051,
                "perception_port": 50052,
                "voice_port": 50053,
                "orchestrator_port": 50054
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'video.width')"""
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self) -> None:
        """Save current configuration to file"""
        try:
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.profile_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Saved config to {self.profile_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def reload(self) -> None:
        """Reload configuration from file"""
        self._config = self._load_config()

    @property
    def all(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return self._config.copy()

# Global config instance
_config_instance: Optional[Config] = None

def get_config(profile: Optional[str] = None) -> Config:
    """Get global configuration instance"""
    global _config_instance

    if _config_instance is None or (profile and _config_instance.profile != profile):
        profile = profile or os.getenv('HELMET_PROFILE', 'dev')
        _config_instance = Config(profile)

    return _config_instance