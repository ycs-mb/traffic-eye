"""Tests for thermal monitoring."""

from src.utils.thermal import MockThermalMonitor, PsutilThermalMonitor


class TestMockThermalMonitor:
    def test_default_temp(self):
        mon = MockThermalMonitor(temperature=45.0)
        assert mon.get_cpu_temp() == 45.0

    def test_set_temperature(self):
        mon = MockThermalMonitor()
        mon.set_temperature(80.0)
        assert mon.get_cpu_temp() == 80.0

    def test_should_throttle(self):
        mon = MockThermalMonitor(temperature=76.0)
        assert mon.should_throttle(75.0) is True
        assert mon.should_throttle(80.0) is False

    def test_should_pause(self):
        mon = MockThermalMonitor(temperature=81.0)
        assert mon.should_pause(80.0) is True
        assert mon.should_pause(85.0) is False


class TestPsutilThermalMonitor:
    def test_returns_float(self):
        mon = PsutilThermalMonitor()
        temp = mon.get_cpu_temp()
        assert isinstance(temp, float)
        assert temp > 0

    def test_default_fallback(self):
        mon = PsutilThermalMonitor(default_temp=55.0)
        # On macOS, sensors_temperatures() may not be available
        temp = mon.get_cpu_temp()
        assert isinstance(temp, float)
