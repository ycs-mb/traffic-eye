"""Reverse geocoding utility for converting GPS coordinates to street addresses."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Cache duration in seconds (1 hour)
_CACHE_TTL = 3600
# Minimum distance (meters) between cached lookups to reuse cache
_CACHE_DISTANCE_THRESHOLD = 50


@dataclass
class GeoAddress:
    """Parsed address components from reverse geocoding."""
    full_address: str
    road: str = ""
    neighbourhood: str = ""
    suburb: str = ""
    city: str = ""
    district: str = ""
    state: str = ""
    postcode: str = ""
    country: str = ""

    @property
    def short_address(self) -> str:
        """Return a concise address: road, area, city."""
        parts = []
        if self.road:
            parts.append(self.road)
        area = self.neighbourhood or self.suburb
        if area:
            parts.append(area)
        if self.city:
            parts.append(self.city)
        if not parts:
            return self.full_address
        return ", ".join(parts)

    @property
    def medium_address(self) -> str:
        """Return a medium-detail address: road, area, city, district, state."""
        parts = []
        if self.road:
            parts.append(self.road)
        area = self.neighbourhood or self.suburb
        if area:
            parts.append(area)
        if self.city:
            parts.append(self.city)
        if self.district and self.district != self.city:
            parts.append(self.district)
        if self.state:
            parts.append(self.state)
        if self.postcode:
            parts.append(self.postcode)
        if not parts:
            return self.full_address
        return ", ".join(parts)


@dataclass
class _CacheEntry:
    """Internal cache entry."""
    lat: float
    lon: float
    address: GeoAddress
    timestamp: float


class ReverseGeocoder:
    """Reverse geocoder using Nominatim (OpenStreetMap) via geopy.

    Features:
    - LRU-style in-memory cache with TTL
    - Distance-based cache hit (reuses nearby lookups)
    - Rate limiting (1 request per second for Nominatim TOS)
    - Thread-safe
    """

    def __init__(
        self,
        user_agent: str = "traffic-eye/0.1",
        cache_size: int = 100,
        cache_ttl: float = _CACHE_TTL,
        cache_distance_threshold: float = _CACHE_DISTANCE_THRESHOLD,
        timeout: float = 5.0,
    ):
        self._user_agent = user_agent
        self._cache_size = cache_size
        self._cache_ttl = cache_ttl
        self._cache_distance_threshold = cache_distance_threshold
        self._timeout = timeout
        self._cache: list[_CacheEntry] = []
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0
        self._geocoder = None

    def _get_geocoder(self):
        """Lazy-initialize the geocoder."""
        if self._geocoder is None:
            try:
                from geopy.geocoders import Nominatim
                self._geocoder = Nominatim(
                    user_agent=self._user_agent,
                    timeout=self._timeout,
                )
            except ImportError:
                logger.error("geopy not installed. Install with: pip install geopy")
                raise
        return self._geocoder

    def reverse(self, latitude: float, longitude: float) -> Optional[GeoAddress]:
        """Reverse geocode coordinates to an address.

        Args:
            latitude: GPS latitude in decimal degrees.
            longitude: GPS longitude in decimal degrees.

        Returns:
            GeoAddress with parsed address components, or None on failure.
        """
        # Check cache first
        cached = self._check_cache(latitude, longitude)
        if cached is not None:
            logger.debug("Geocoder cache hit for %.6f, %.6f", latitude, longitude)
            return cached

        # Rate limiting (Nominatim requires 1 req/sec)
        with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)

        try:
            geocoder = self._get_geocoder()
            location = geocoder.reverse(
                (latitude, longitude),
                exactly_one=True,
                language="en",
                addressdetails=True,
            )

            with self._lock:
                self._last_request_time = time.monotonic()

            if location is None:
                logger.warning(
                    "No address found for coordinates: %.6f, %.6f",
                    latitude, longitude,
                )
                return None

            raw = location.raw.get("address", {})
            address = GeoAddress(
                full_address=location.address or "",
                road=raw.get("road", raw.get("pedestrian", "")),
                neighbourhood=raw.get("neighbourhood", raw.get("hamlet", "")),
                suburb=raw.get("suburb", raw.get("village", "")),
                city=raw.get("city", raw.get("town", raw.get("municipality", ""))),
                district=raw.get("county", raw.get("state_district", "")),
                state=raw.get("state", ""),
                postcode=raw.get("postcode", ""),
                country=raw.get("country", ""),
            )

            self._add_to_cache(latitude, longitude, address)

            logger.info(
                "Geocoded %.6f, %.6f -> %s",
                latitude, longitude, address.short_address,
            )
            return address

        except ImportError:
            return None
        except Exception as e:
            logger.warning(
                "Reverse geocoding failed for %.6f, %.6f: %s",
                latitude, longitude, e,
            )
            return None

    def _check_cache(self, lat: float, lon: float) -> Optional[GeoAddress]:
        """Check if we have a recent cache entry near these coordinates."""
        with self._lock:
            now = time.monotonic()
            # Remove expired entries
            self._cache = [
                e for e in self._cache
                if (now - e.timestamp) < self._cache_ttl
            ]
            # Check for nearby cached location
            for entry in reversed(self._cache):  # Most recent first
                dist = self._haversine_meters(lat, lon, entry.lat, entry.lon)
                if dist <= self._cache_distance_threshold:
                    return entry.address
        return None

    def _add_to_cache(self, lat: float, lon: float, address: GeoAddress) -> None:
        """Add a geocoding result to the cache."""
        with self._lock:
            self._cache.append(_CacheEntry(
                lat=lat, lon=lon, address=address, timestamp=time.monotonic(),
            ))
            # Trim cache if too large
            if len(self._cache) > self._cache_size:
                self._cache = self._cache[-self._cache_size:]

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute distance between two GPS points in meters using Haversine formula."""
        import math
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
