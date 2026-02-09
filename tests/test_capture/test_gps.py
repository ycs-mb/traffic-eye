"""Tests for GPS abstraction."""

import socket
import threading
import time
from datetime import datetime, timezone

from src.capture.gps import MockGPS, NetworkGPS
from src.models import GPSReading


class TestMockGPS:
    def test_default_reading(self):
        gps = MockGPS(default_lat=12.97, default_lon=77.59)
        gps.start()
        reading = gps.get_reading()
        assert reading is not None
        assert reading.latitude == 12.97
        assert reading.longitude == 77.59
        assert reading.speed_kmh == 30.0
        gps.stop()

    def test_no_reading_before_start(self):
        gps = MockGPS()
        assert gps.get_reading() is None
        assert gps.has_fix() is False

    def test_custom_readings(self):
        readings = [
            GPSReading(12.0, 77.0, 920, 25, 90, datetime.now(timezone.utc), 1, 8),
            GPSReading(12.1, 77.1, 920, 30, 95, datetime.now(timezone.utc), 1, 8),
        ]
        gps = MockGPS(readings=readings)
        gps.start()
        r1 = gps.get_reading()
        r2 = gps.get_reading()
        assert r1.latitude == 12.0
        assert r2.latitude == 12.1
        # Should loop
        r3 = gps.get_reading()
        assert r3.latitude == 12.0
        gps.stop()

    def test_set_fix(self):
        gps = MockGPS()
        gps.start()
        assert gps.has_fix() is True
        gps.set_fix(False)
        assert gps.has_fix() is False
        assert gps.get_reading() is None
        gps.stop()

    def test_set_heading(self):
        gps = MockGPS()
        gps.start()
        gps.set_heading(180.0)
        r = gps.get_reading()
        assert r.heading == 180.0
        gps.stop()

    def test_set_speed(self):
        gps = MockGPS()
        gps.start()
        gps.set_speed(0.0)
        r = gps.get_reading()
        assert r.speed_kmh == 0.0
        gps.stop()


# Valid NMEA test sentences
NMEA_RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
NMEA_GGA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
NMEA_RMC_NO_FIX = "$GPRMC,123519,V,,,,,,,230394,003.1,W*63"


class TestNetworkGPSUDP:
    def test_udp_reception(self):
        """Receive NMEA via UDP and verify parsed GPS reading."""
        gps = NetworkGPS(host="127.0.0.1", port=19001, protocol="udp")
        gps.start()
        time.sleep(0.3)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(NMEA_RMC.encode(), ("127.0.0.1", 19001))
        time.sleep(0.3)

        reading = gps.get_reading()
        assert reading is not None
        assert abs(reading.latitude - 48.1173) < 0.01
        assert abs(reading.longitude - 11.5167) < 0.01
        assert reading.speed_kmh > 0
        assert gps.has_fix()

        sender.close()
        gps.stop()

    def test_udp_with_gga(self):
        """Receive RMC + GGA and verify altitude/satellites are parsed."""
        gps = NetworkGPS(host="127.0.0.1", port=19002, protocol="udp")
        gps.start()
        time.sleep(0.3)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(NMEA_RMC.encode(), ("127.0.0.1", 19002))
        sender.sendto(NMEA_GGA.encode(), ("127.0.0.1", 19002))
        time.sleep(0.3)

        reading = gps.get_reading()
        assert reading is not None
        assert reading.altitude == 545.4
        assert reading.satellites == 8

        sender.close()
        gps.stop()

    def test_malformed_nmea(self):
        """Malformed data should not crash, valid data after should work."""
        gps = NetworkGPS(host="127.0.0.1", port=19003, protocol="udp")
        gps.start()
        time.sleep(0.3)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(b"THIS IS NOT NMEA", ("127.0.0.1", 19003))
        sender.sendto(b"$INVALID,SENTENCE,BAD*FF", ("127.0.0.1", 19003))
        time.sleep(0.2)
        assert gps.get_reading() is None

        # Now send valid data
        sender.sendto(NMEA_RMC.encode(), ("127.0.0.1", 19003))
        time.sleep(0.3)
        assert gps.get_reading() is not None

        sender.close()
        gps.stop()

    def test_no_fix_initially(self):
        """GPS starts without fix until data arrives."""
        gps = NetworkGPS(host="127.0.0.1", port=19004, protocol="udp")
        gps.start()
        time.sleep(0.2)

        assert gps.get_reading() is None
        assert not gps.has_fix()

        gps.stop()

    def test_stale_data(self):
        """Fix should be lost when data becomes stale."""
        gps = NetworkGPS(
            host="127.0.0.1", port=19005, protocol="udp",
            stale_threshold_seconds=1.0,
        )
        gps.start()
        time.sleep(0.3)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(NMEA_RMC.encode(), ("127.0.0.1", 19005))
        time.sleep(0.3)
        assert gps.has_fix()

        # Wait for data to become stale
        time.sleep(1.5)
        assert not gps.has_fix()
        # Reading still available, just not "fix"
        assert gps.get_reading() is not None

        sender.close()
        gps.stop()

    def test_multiline_datagram(self):
        """Handle multiple NMEA sentences in a single UDP packet."""
        gps = NetworkGPS(host="127.0.0.1", port=19006, protocol="udp")
        gps.start()
        time.sleep(0.3)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        combined = NMEA_RMC + "\n" + NMEA_GGA
        sender.sendto(combined.encode(), ("127.0.0.1", 19006))
        time.sleep(0.3)

        reading = gps.get_reading()
        assert reading is not None
        assert reading.altitude == 545.4  # From GGA
        assert reading.speed_kmh > 0  # From RMC

        sender.close()
        gps.stop()

    def test_start_stop_lifecycle(self):
        """Verify clean start/stop without errors."""
        gps = NetworkGPS(host="127.0.0.1", port=19007, protocol="udp", timeout=1.0)
        gps.start()
        time.sleep(0.3)
        gps.stop()
        # Should not hang or raise


class TestNetworkGPSTCP:
    def test_tcp_reception(self):
        """Receive NMEA via TCP and verify parsed GPS reading."""
        gps = NetworkGPS(host="127.0.0.1", port=19010, protocol="tcp")
        gps.start()
        time.sleep(0.3)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", 19010))
        client.sendall((NMEA_RMC + "\n").encode())
        time.sleep(0.3)

        reading = gps.get_reading()
        assert reading is not None
        assert abs(reading.latitude - 48.1173) < 0.01
        assert gps.has_fix()

        client.close()
        gps.stop()

    def test_tcp_reconnection(self):
        """TCP client can disconnect and reconnect."""
        gps = NetworkGPS(host="127.0.0.1", port=19011, protocol="tcp")
        gps.start()
        time.sleep(0.3)

        # First connection
        client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client1.connect(("127.0.0.1", 19011))
        client1.sendall((NMEA_RMC + "\n").encode())
        time.sleep(0.3)
        assert gps.get_reading() is not None
        client1.close()
        time.sleep(0.5)

        # Reconnect
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2.connect(("127.0.0.1", 19011))
        client2.sendall((NMEA_RMC + "\n").encode())
        time.sleep(0.3)
        assert gps.get_reading() is not None

        client2.close()
        gps.stop()
