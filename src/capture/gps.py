"""GPS reader abstraction with mock, NMEA file, network, and gpsd implementations."""

from __future__ import annotations

import logging
import socket
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models import GPSReading

logger = logging.getLogger(__name__)


class GPSBase(ABC):
    """Abstract base class for GPS input."""

    @abstractmethod
    def start(self) -> None:
        """Start GPS reading."""

    @abstractmethod
    def stop(self) -> None:
        """Stop GPS reading."""

    @abstractmethod
    def get_reading(self) -> Optional[GPSReading]:
        """Get the latest GPS reading. Returns None if no fix."""

    @abstractmethod
    def has_fix(self) -> bool:
        """Check if GPS has a valid fix."""


class MockGPS(GPSBase):
    """Returns configurable GPS data for testing.

    Can simulate a route by replaying a list of GPSReadings.
    """

    def __init__(
        self,
        readings: Optional[list[GPSReading]] = None,
        default_lat: float = 12.9716,
        default_lon: float = 77.5946,
        default_speed: float = 30.0,
        default_heading: float = 90.0,
    ):
        self._readings = readings or []
        self._index = 0
        self._default_lat = default_lat
        self._default_lon = default_lon
        self._default_speed = default_speed
        self._default_heading = default_heading
        self._started = False
        self._has_fix = True

    def start(self) -> None:
        self._started = True
        self._index = 0
        logger.info("Mock GPS started (lat=%.4f, lon=%.4f)",
                     self._default_lat, self._default_lon)

    def stop(self) -> None:
        self._started = False

    def get_reading(self) -> Optional[GPSReading]:
        if not self._started or not self._has_fix:
            return None

        if self._readings:
            if self._index < len(self._readings):
                reading = self._readings[self._index]
                self._index += 1
                return reading
            # Loop back
            self._index = 0
            return self._readings[0] if self._readings else None

        return GPSReading(
            latitude=self._default_lat,
            longitude=self._default_lon,
            altitude=920.0,
            speed_kmh=self._default_speed,
            heading=self._default_heading,
            timestamp=datetime.now(timezone.utc),
            fix_quality=1,
            satellites=8,
        )

    def has_fix(self) -> bool:
        return self._started and self._has_fix

    def set_fix(self, has_fix: bool) -> None:
        self._has_fix = has_fix

    def set_heading(self, heading: float) -> None:
        self._default_heading = heading

    def set_speed(self, speed_kmh: float) -> None:
        self._default_speed = speed_kmh


class NMEAFileGPS(GPSBase):
    """Replays NMEA sentences from a log file.

    Supports GGA and RMC sentences for position, speed, and heading.
    """

    def __init__(self, nmea_file_path: str, loop: bool = True):
        self._file_path = nmea_file_path
        self._loop = loop
        self._lines: list[str] = []
        self._index = 0
        self._started = False
        self._last_reading: Optional[GPSReading] = None

    def start(self) -> None:
        path = Path(self._file_path)
        if not path.exists():
            raise FileNotFoundError(f"NMEA file not found: {self._file_path}")
        self._lines = path.read_text().strip().splitlines()
        self._index = 0
        self._started = True
        logger.info("NMEA GPS started: %s (%d lines)", self._file_path, len(self._lines))

    def stop(self) -> None:
        self._started = False

    def get_reading(self) -> Optional[GPSReading]:
        if not self._started or not self._lines:
            return None

        while self._index < len(self._lines):
            line = self._lines[self._index].strip()
            self._index += 1

            reading = self._parse_rmc(line)
            if reading:
                self._last_reading = reading
                return reading

        if self._loop:
            self._index = 0
        return self._last_reading

    def has_fix(self) -> bool:
        return self._last_reading is not None

    @staticmethod
    def _parse_rmc(sentence: str) -> Optional[GPSReading]:
        """Parse a GPRMC or GNRMC sentence."""
        if not (sentence.startswith("$GPRMC") or sentence.startswith("$GNRMC")):
            return None

        parts = sentence.split("*")[0].split(",")
        if len(parts) < 12 or parts[2] != "A":
            return None

        try:
            lat = NMEAFileGPS._nmea_to_decimal(parts[3], parts[4])
            lon = NMEAFileGPS._nmea_to_decimal(parts[5], parts[6])
            speed_knots = float(parts[7]) if parts[7] else 0.0
            heading = float(parts[8]) if parts[8] else 0.0

            return GPSReading(
                latitude=lat,
                longitude=lon,
                altitude=0.0,
                speed_kmh=speed_knots * 1.852,
                heading=heading,
                timestamp=datetime.now(timezone.utc),
                fix_quality=1,
                satellites=0,
            )
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _nmea_to_decimal(value: str, direction: str) -> float:
        """Convert NMEA coordinate (ddmm.mmm) to decimal degrees."""
        if not value:
            return 0.0
        dot_pos = value.index(".")
        degrees = float(value[:dot_pos - 2])
        minutes = float(value[dot_pos - 2:])
        decimal = degrees + minutes / 60.0
        if direction in ("S", "W"):
            decimal = -decimal
        return decimal


class GpsdGPS(GPSBase):
    """GPS reader using gpsd daemon via the gps3 library.

    Requires gpsd running and gps3 Python package.
    Reads GPS data in a background thread to avoid blocking.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 2947):
        self._host = host
        self._port = port
        self._last_reading: Optional[GPSReading] = None
        self._started = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._started = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        logger.info("GpsdGPS started (host=%s, port=%d)", self._host, self._port)

    def stop(self) -> None:
        self._started = False
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def get_reading(self) -> Optional[GPSReading]:
        with self._lock:
            return self._last_reading

    def has_fix(self) -> bool:
        with self._lock:
            return self._last_reading is not None and self._last_reading.fix_quality > 0

    def _reader_loop(self) -> None:
        try:
            from gps3 import gps3

            socket = gps3.GPSDSocket()
            stream = gps3.DataStream()
            socket.connect(host=self._host, port=self._port)
            socket.watch()

            for new_data in socket:
                if not self._started:
                    break
                if new_data:
                    stream.unpack(new_data)

                    lat = stream.TPV.get("lat", "n/a")
                    lon = stream.TPV.get("lon", "n/a")
                    alt = stream.TPV.get("alt", "n/a")
                    speed = stream.TPV.get("speed", "n/a")
                    track = stream.TPV.get("track", "n/a")

                    if lat == "n/a" or lon == "n/a":
                        continue

                    try:
                        reading = GPSReading(
                            latitude=float(lat),
                            longitude=float(lon),
                            altitude=float(alt) if alt != "n/a" else 0.0,
                            speed_kmh=float(speed) * 3.6 if speed != "n/a" else 0.0,
                            heading=float(track) if track != "n/a" else 0.0,
                            timestamp=datetime.now(timezone.utc),
                            fix_quality=1,
                            satellites=0,
                        )
                        with self._lock:
                            self._last_reading = reading
                    except (ValueError, TypeError):
                        continue

            socket.close()
        except ImportError:
            logger.error("gps3 package not installed. Install with: pip install gps3")
        except Exception as e:
            logger.error("GpsdGPS reader error: %s", e)


class NetworkGPS(GPSBase):
    """GPS reader that receives NMEA sentences over UDP or TCP from phone apps.

    Listens on a network socket for incoming NMEA data. Compatible with phone
    GPS apps such as GPS2IP (iOS), NMEA Tools, Share GPS, gpsdRelay (Android).

    Runs a listener in a daemon thread (same pattern as GpsdGPS).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 10110,
        protocol: str = "udp",
        timeout: float = 5.0,
        stale_threshold_seconds: float = 30.0,
    ):
        self._host = host
        self._port = port
        self._protocol = protocol.lower()
        self._timeout = timeout
        self._stale_threshold = stale_threshold_seconds
        self._last_reading: Optional[GPSReading] = None
        self._last_update_time: float = 0.0
        self._started = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._partial_data: dict[str, float | int] = {}

    def start(self) -> None:
        self._started = True
        self._thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._thread.start()
        logger.info(
            "NetworkGPS started (%s://%s:%d)", self._protocol, self._host, self._port
        )

    def stop(self) -> None:
        self._started = False
        if self._thread is not None:
            self._thread.join(timeout=self._timeout + 2)
            self._thread = None

    def get_reading(self) -> Optional[GPSReading]:
        with self._lock:
            return self._last_reading

    def has_fix(self) -> bool:
        with self._lock:
            if self._last_reading is None:
                return False
            if self._last_update_time == 0.0:
                return False
            elapsed = time.monotonic() - self._last_update_time
            if elapsed > self._stale_threshold:
                return False
            return self._last_reading.fix_quality > 0

    def _listener_loop(self) -> None:
        if self._protocol == "tcp":
            self._tcp_listener()
        else:
            self._udp_listener()

    def _udp_listener(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self._host, self._port))
            sock.settimeout(self._timeout)
            logger.info("NetworkGPS UDP listening on %s:%d", self._host, self._port)

            while self._started:
                try:
                    data, _addr = sock.recvfrom(4096)
                    self._process_data(data)
                except socket.timeout:
                    continue
                except OSError:
                    if not self._started:
                        break
                    raise
        except Exception as e:
            if self._started:
                logger.error("NetworkGPS UDP error: %s", e)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _tcp_listener(self) -> None:
        server_sock = None
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self._host, self._port))
            server_sock.listen(1)
            server_sock.settimeout(1.0)
            logger.info("NetworkGPS TCP listening on %s:%d", self._host, self._port)

            while self._started:
                try:
                    client_sock, addr = server_sock.accept()
                    logger.info("NetworkGPS TCP client connected: %s", addr)
                    self._handle_tcp_client(client_sock)
                except socket.timeout:
                    continue
                except OSError:
                    if not self._started:
                        break
                    raise
        except Exception as e:
            if self._started:
                logger.error("NetworkGPS TCP error: %s", e)
        finally:
            if server_sock:
                try:
                    server_sock.close()
                except Exception:
                    pass

    def _handle_tcp_client(self, client_sock: socket.socket) -> None:
        """Read NMEA sentences from a connected TCP client."""
        client_sock.settimeout(self._timeout)
        buf = ""
        try:
            while self._started:
                try:
                    data = client_sock.recv(4096)
                    if not data:
                        break  # Client disconnected
                    buf += data.decode("ascii", errors="ignore")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self._process_nmea_sentence(line.strip())
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            logger.info("NetworkGPS TCP client disconnected")

    def _process_data(self, data: bytes) -> None:
        """Process raw bytes received from socket (may contain multiple lines)."""
        text = data.decode("ascii", errors="ignore").strip()
        for line in text.split("\n"):
            line = line.strip()
            if line:
                self._process_nmea_sentence(line)

    def _process_nmea_sentence(self, sentence: str) -> None:
        """Parse a single NMEA sentence and update partial GPS data."""
        try:
            import pynmea2

            if not sentence.startswith("$"):
                return

            msg = pynmea2.parse(sentence)

            # RMC: position, speed, heading
            if msg.sentence_type == "RMC":
                if hasattr(msg, "status") and msg.status == "A":
                    self._partial_data["latitude"] = msg.latitude
                    self._partial_data["longitude"] = msg.longitude
                    speed_knots = msg.spd_over_grnd if msg.spd_over_grnd else 0.0
                    self._partial_data["speed_kmh"] = float(speed_knots) * 1.852
                    heading = msg.true_course if msg.true_course else 0.0
                    self._partial_data["heading"] = float(heading)
                    self._partial_data["fix_quality"] = 1
                elif hasattr(msg, "status") and msg.status == "V":
                    self._partial_data["fix_quality"] = 0

            # GGA: altitude, fix quality, satellites
            elif msg.sentence_type == "GGA":
                if msg.gps_qual and int(msg.gps_qual) > 0:
                    self._partial_data["altitude"] = (
                        float(msg.altitude) if msg.altitude else 0.0
                    )
                    self._partial_data["fix_quality"] = int(msg.gps_qual)
                    self._partial_data["satellites"] = (
                        int(msg.num_sats) if msg.num_sats else 0
                    )

            self._try_create_reading()

        except ImportError:
            logger.error("pynmea2 not installed. Install with: pip install pynmea2")
        except Exception as e:
            logger.debug("NetworkGPS parse error: %s (sentence: %s)", e, sentence[:40])

    def _try_create_reading(self) -> None:
        """Create a GPSReading if we have at least latitude and longitude."""
        if "latitude" not in self._partial_data or "longitude" not in self._partial_data:
            return

        reading = GPSReading(
            latitude=float(self._partial_data["latitude"]),
            longitude=float(self._partial_data["longitude"]),
            altitude=float(self._partial_data.get("altitude", 0.0)),
            speed_kmh=float(self._partial_data.get("speed_kmh", 0.0)),
            heading=float(self._partial_data.get("heading", 0.0)),
            timestamp=datetime.now(timezone.utc),
            fix_quality=int(self._partial_data.get("fix_quality", 1)),
            satellites=int(self._partial_data.get("satellites", 0)),
        )

        with self._lock:
            was_fix = self._last_reading is not None
            self._last_reading = reading
            self._last_update_time = time.monotonic()

            if not was_fix:
                logger.info(
                    "NetworkGPS fix acquired: %.6f, %.6f",
                    reading.latitude,
                    reading.longitude,
                )
