"""Thermal monitoring abstraction with cross-platform and Pi implementations."""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ThermalMonitorBase(ABC):
    """Abstract base class for CPU temperature monitoring."""

    @abstractmethod
    def get_cpu_temp(self) -> float:
        """Get current CPU temperature in Celsius."""

    def should_throttle(self, throttle_temp: float) -> bool:
        """Check if processing should be throttled."""
        return self.get_cpu_temp() >= throttle_temp

    def should_pause(self, pause_temp: float) -> bool:
        """Check if processing should be paused entirely."""
        return self.get_cpu_temp() >= pause_temp


class PsutilThermalMonitor(ThermalMonitorBase):
    """Cross-platform thermal monitoring using psutil.

    Falls back to a safe default (50.0C) if temperature sensors
    are unavailable (common on macOS).
    """

    def __init__(self, default_temp: float = 50.0):
        self._default_temp = default_temp

    def get_cpu_temp(self) -> float:
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            if not temps:
                return self._default_temp

            # Try common sensor names across platforms
            for name in ("coretemp", "cpu_thermal", "cpu-thermal", "k10temp", "acpitz"):
                if name in temps and temps[name]:
                    return temps[name][0].current

            # Use first available sensor
            for sensor_list in temps.values():
                if sensor_list:
                    return sensor_list[0].current

        except (AttributeError, ImportError):
            # psutil.sensors_temperatures() not available on all platforms (e.g., macOS)
            pass
        except Exception as e:
            logger.debug("Temperature read failed: %s", e)

        return self._default_temp


class MockThermalMonitor(ThermalMonitorBase):
    """Returns a configurable temperature for testing throttle/pause logic."""

    def __init__(self, temperature: float = 45.0):
        self._temperature = temperature

    def get_cpu_temp(self) -> float:
        return self._temperature

    def set_temperature(self, temp: float) -> None:
        self._temperature = temp


class VcgencmdThermalMonitor(ThermalMonitorBase):
    """Raspberry Pi thermal monitoring using vcgencmd.

    Reads GPU/SoC temperature directly from the VideoCore firmware,
    which is the most accurate temperature source on Pi.
    Falls back to reading /sys/class/thermal if vcgencmd is unavailable.
    """

    def __init__(self, default_temp: float = 50.0):
        self._default_temp = default_temp

    def get_cpu_temp(self) -> float:
        # Try vcgencmd first (most accurate on Pi)
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                # Output format: "temp=42.5'C"
                temp_str = result.stdout.strip()
                temp_val = temp_str.split("=")[1].split("'")[0]
                return float(temp_val)
        except (FileNotFoundError, subprocess.TimeoutExpired, IndexError, ValueError):
            pass

        # Fallback: read from sysfs thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                millideg = int(f.read().strip())
                return millideg / 1000.0
        except (FileNotFoundError, ValueError, PermissionError):
            pass

        logger.debug("Could not read Pi temperature, using default %.1f", self._default_temp)
        return self._default_temp
