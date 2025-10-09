"""Power management system for helmet displays"""

import logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PowerProfile(Enum):
    """Power profiles with different performance/battery tradeoffs"""
    PERFORMANCE = "performance"  # 30 FPS, full analytics
    BALANCED = "balanced"        # 20 FPS, moderate features
    SAVER = "saver"             # 10 FPS, minimal features


class PowerManager:
    """Manage power profiles and frame rates"""

    def __init__(self, initial_profile: PowerProfile = PowerProfile.BALANCED):
        self.current_profile = initial_profile
        self.profile_change_callback = None

        # Profile configurations
        self.profile_configs = {
            PowerProfile.PERFORMANCE: {
                'fps': 30,
                'frame_interval_ms': 33,  # 1000/30
                'description': 'Maximum performance',
                'features': {
                    'hud': True,
                    'detections': True,
                    'rear_camera': True,
                    'gyro_rate_hz': 60
                }
            },
            PowerProfile.BALANCED: {
                'fps': 20,
                'frame_interval_ms': 50,  # 1000/20
                'description': 'Balanced performance and battery',
                'features': {
                    'hud': True,
                    'detections': False,  # Disable CPU-heavy perception
                    'rear_camera': True,
                    'gyro_rate_hz': 30
                }
            },
            PowerProfile.SAVER: {
                'fps': 10,
                'frame_interval_ms': 100,  # 1000/10
                'description': 'Maximum battery life',
                'features': {
                    'hud': True,
                    'detections': False,
                    'rear_camera': False,  # Disable rear camera
                    'gyro_rate_hz': 15
                }
            }
        }

        logger.info(f"Power manager initialized with profile: {self.current_profile.value}")

    def set_profile(self, profile: PowerProfile):
        """
        Set power profile

        Args:
            profile: New power profile to activate
        """
        if profile == self.current_profile:
            logger.info(f"Already in {profile.value} profile")
            return

        old_profile = self.current_profile
        self.current_profile = profile

        config = self.profile_configs[profile]
        logger.info(f"Power profile changed: {old_profile.value} -> {profile.value}")
        logger.info(f"  FPS: {config['fps']}, Features: {config['features']}")

        # Notify callback
        if self.profile_change_callback:
            self.profile_change_callback(profile, config)

    def get_current_config(self) -> dict:
        """Get configuration for current profile"""
        return self.profile_configs[self.current_profile]

    def get_frame_interval_ms(self) -> int:
        """Get frame update interval in milliseconds"""
        return self.profile_configs[self.current_profile]['frame_interval_ms']

    def get_target_fps(self) -> int:
        """Get target FPS for current profile"""
        return self.profile_configs[self.current_profile]['fps']

    def register_callback(self, callback: Callable[[PowerProfile, dict], None]):
        """
        Register callback for profile changes

        Args:
            callback: Function called with (new_profile, config) when profile changes
        """
        self.profile_change_callback = callback

    def auto_adjust(self, battery_level: float, temperature: float):
        """
        Automatically adjust power profile based on battery and temperature

        Args:
            battery_level: Battery percentage (0-100)
            temperature: CPU temperature in Celsius
        """
        # Auto-switch to SAVER mode if battery critical or overheating
        if battery_level < 15 or temperature > 75:
            if self.current_profile != PowerProfile.SAVER:
                logger.warning(f"Auto-switching to SAVER mode (battery: {battery_level}%, temp: {temperature}°C)")
                self.set_profile(PowerProfile.SAVER)
                return True

        # Auto-switch to BALANCED if battery moderate or temp elevated
        elif battery_level < 30 or temperature > 65:
            if self.current_profile == PowerProfile.PERFORMANCE:
                logger.warning(f"Auto-switching to BALANCED mode (battery: {battery_level}%, temp: {temperature}°C)")
                self.set_profile(PowerProfile.BALANCED)
                return True

        return False

    def set_profile_by_name(self, name: str):
        """Set profile by string name (for voice commands)"""
        name_lower = name.lower().strip()

        if name_lower in ['performance', 'perf', 'high', 'max']:
            self.set_profile(PowerProfile.PERFORMANCE)
        elif name_lower in ['balanced', 'balance', 'medium', 'normal']:
            self.set_profile(PowerProfile.BALANCED)
        elif name_lower in ['saver', 'save', 'low', 'eco', 'economy']:
            self.set_profile(PowerProfile.SAVER)
        else:
            logger.warning(f"Unknown power profile: {name}")
            return False

        return True

    def get_status_string(self) -> str:
        """Get human-readable status string"""
        config = self.get_current_config()
        return (
            f"Power profile: {self.current_profile.value}, "
            f"{config['fps']} FPS, "
            f"{config['description']}"
        )


if __name__ == "__main__":
    """Test power manager"""
    logging.basicConfig(level=logging.INFO)

    print("Power Manager Test\n" + "="*50)

    manager = PowerManager(PowerProfile.BALANCED)

    def on_profile_change(profile, config):
        print(f"\n[Profile Change] New profile: {profile.value}")
        print(f"  FPS: {config['fps']}")
        print(f"  Frame interval: {config['frame_interval_ms']}ms")
        print(f"  Features: {config['features']}")

    manager.register_callback(on_profile_change)

    print(f"\nInitial status: {manager.get_status_string()}")

    print("\n\nTesting manual profile changes:")
    print("-" * 50)
    manager.set_profile(PowerProfile.PERFORMANCE)
    manager.set_profile(PowerProfile.SAVER)
    manager.set_profile(PowerProfile.BALANCED)

    print("\n\nTesting voice command profile setting:")
    print("-" * 50)
    manager.set_profile_by_name("performance")
    manager.set_profile_by_name("eco")
    manager.set_profile_by_name("normal")

    print("\n\nTesting auto-adjustment:")
    print("-" * 50)
    print("Simulating low battery (10%)...")
    manager.auto_adjust(battery_level=10, temperature=50)

    print("\nSimulating overheating (80°C)...")
    manager.set_profile(PowerProfile.PERFORMANCE)
    manager.auto_adjust(battery_level=50, temperature=80)

    print("\nSimulating normal conditions...")
    manager.auto_adjust(battery_level=80, temperature=55)

    print(f"\n\nFinal status: {manager.get_status_string()}")
