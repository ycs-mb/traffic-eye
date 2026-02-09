"""Tests for reverse geocoder utility."""

import time
from unittest.mock import MagicMock, patch

from src.utils.geocoder import GeoAddress, ReverseGeocoder


class TestGeoAddress:
    def test_short_address(self):
        addr = GeoAddress(
            full_address="123 Main St, Indiranagar, Bengaluru, Karnataka 560038, India",
            road="Main Street",
            neighbourhood="Indiranagar",
            city="Bengaluru",
            state="Karnataka",
            postcode="560038",
            country="India",
        )
        assert addr.short_address == "Main Street, Indiranagar, Bengaluru"

    def test_short_address_no_road(self):
        addr = GeoAddress(
            full_address="Indiranagar, Bengaluru",
            neighbourhood="Indiranagar",
            city="Bengaluru",
        )
        assert addr.short_address == "Indiranagar, Bengaluru"

    def test_short_address_fallback_to_suburb(self):
        addr = GeoAddress(
            full_address="Some place",
            road="MG Road",
            suburb="Shivajinagar",
            city="Bengaluru",
        )
        # neighbourhood is empty, so suburb is used
        assert addr.short_address == "MG Road, Shivajinagar, Bengaluru"

    def test_short_address_empty_falls_back_to_full(self):
        addr = GeoAddress(full_address="Just a full address")
        assert addr.short_address == "Just a full address"

    def test_medium_address(self):
        addr = GeoAddress(
            full_address="Full address here",
            road="100 Feet Road",
            neighbourhood="Indiranagar",
            city="Bengaluru",
            district="Bangalore Urban",
            state="Karnataka",
            postcode="560038",
        )
        expected = "100 Feet Road, Indiranagar, Bengaluru, Bangalore Urban, Karnataka, 560038"
        assert addr.medium_address == expected

    def test_medium_address_district_same_as_city(self):
        addr = GeoAddress(
            full_address="Full",
            road="Church Street",
            city="Bengaluru",
            district="Bengaluru",
            state="Karnataka",
        )
        # District should be omitted when same as city
        assert addr.medium_address == "Church Street, Bengaluru, Karnataka"


class TestReverseGeocoder:
    def _make_mock_location(self, address_data: dict, display_name: str = "Mock Address"):
        """Create a mock geopy Location object."""
        location = MagicMock()
        location.address = display_name
        location.raw = {"address": address_data}
        return location

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_reverse_basic(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = self._make_mock_location(
            {
                "road": "100 Feet Road",
                "neighbourhood": "Indiranagar",
                "suburb": "Indiranagar",
                "city": "Bengaluru",
                "county": "Bangalore Urban",
                "state": "Karnataka",
                "postcode": "560038",
                "country": "India",
            },
            "100 Feet Road, Indiranagar, Bengaluru, Karnataka 560038, India",
        )
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder()
        result = geocoder.reverse(12.9716, 77.5946)

        assert result is not None
        assert result.road == "100 Feet Road"
        assert result.neighbourhood == "Indiranagar"
        assert result.city == "Bengaluru"
        assert result.state == "Karnataka"
        assert result.postcode == "560038"
        assert result.country == "India"
        assert "Indiranagar" in result.short_address
        assert "Bengaluru" in result.short_address

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_reverse_returns_none_on_no_result(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = None
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder()
        result = geocoder.reverse(0.0, 0.0)
        assert result is None

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_reverse_handles_exception(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.side_effect = Exception("Network error")
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder()
        result = geocoder.reverse(12.9716, 77.5946)
        assert result is None

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_cache_hit_nearby(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = self._make_mock_location(
            {"road": "Test Road", "city": "Test City"},
            "Test Road, Test City",
        )
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder(cache_distance_threshold=100)

        # First call: cache miss
        result1 = geocoder.reverse(12.97160, 77.59460)
        assert result1 is not None
        assert mock_geocoder.reverse.call_count == 1

        # Second call: very close (within 100m) -> cache hit
        result2 = geocoder.reverse(12.97165, 77.59465)
        assert result2 is not None
        assert mock_geocoder.reverse.call_count == 1  # No new call

        assert result1.road == result2.road

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_cache_miss_far_away(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        call_count = [0]

        def mock_reverse(*args, **kwargs):
            call_count[0] += 1
            return self._make_mock_location(
                {"road": f"Road {call_count[0]}", "city": "City"},
                f"Road {call_count[0]}, City",
            )

        mock_geocoder.reverse.side_effect = mock_reverse
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder(cache_distance_threshold=50)

        # First call
        geocoder.reverse(12.97, 77.59)
        # Second call: far away (~1km) -> cache miss
        geocoder.reverse(12.98, 77.60)
        assert mock_geocoder.reverse.call_count == 2

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_cache_expiry(self, mock_get_geocoder):
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = self._make_mock_location(
            {"road": "Road", "city": "City"},
        )
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder(cache_ttl=0.1)  # 100ms TTL

        geocoder.reverse(12.97, 77.59)
        assert mock_geocoder.reverse.call_count == 1

        # Wait for TTL to expire
        time.sleep(0.2)

        geocoder.reverse(12.97, 77.59)
        assert mock_geocoder.reverse.call_count == 2  # New request after expiry

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_cache_size_limit(self, mock_get_geocoder):
        call_count = [0]

        def mock_reverse(*args, **kwargs):
            call_count[0] += 1
            return self._make_mock_location(
                {"road": f"Road {call_count[0]}"},
            )

        mock_geocoder = MagicMock()
        mock_geocoder.reverse.side_effect = mock_reverse
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder(cache_size=3, cache_distance_threshold=1)

        # Fill cache with 4 entries (exceeds size=3)
        for i in range(4):
            geocoder.reverse(12.0 + i * 0.1, 77.0 + i * 0.1)

        # Cache should have been trimmed to 3
        assert len(geocoder._cache) == 3

    def test_haversine_same_point(self):
        dist = ReverseGeocoder._haversine_meters(12.97, 77.59, 12.97, 77.59)
        assert dist == 0.0

    def test_haversine_known_distance(self):
        # Bengaluru to Mumbai: ~845 km
        dist = ReverseGeocoder._haversine_meters(12.97, 77.59, 19.07, 72.87)
        assert 800_000 < dist < 900_000  # Between 800km and 900km

    def test_haversine_nearby(self):
        # ~10 meters apart (small lat change)
        dist = ReverseGeocoder._haversine_meters(12.970000, 77.590000, 12.970090, 77.590000)
        assert 5 < dist < 15

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_reverse_with_missing_fields(self, mock_get_geocoder):
        """Geocoder should handle responses with missing address fields gracefully."""
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = self._make_mock_location(
            {"city": "Bengaluru", "country": "India"},
            "Bengaluru, India",
        )
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder()
        result = geocoder.reverse(12.97, 77.59)

        assert result is not None
        assert result.road == ""
        assert result.city == "Bengaluru"
        assert result.country == "India"
        assert result.short_address == "Bengaluru"

    @patch("src.utils.geocoder.ReverseGeocoder._get_geocoder")
    def test_reverse_town_fallback(self, mock_get_geocoder):
        """When 'city' is missing, should fall back to 'town'."""
        mock_geocoder = MagicMock()
        mock_geocoder.reverse.return_value = self._make_mock_location(
            {"road": "NH-48", "town": "Nelamangala", "state": "Karnataka"},
            "NH-48, Nelamangala, Karnataka",
        )
        mock_get_geocoder.return_value = mock_geocoder

        geocoder = ReverseGeocoder()
        result = geocoder.reverse(13.09, 77.39)

        assert result is not None
        assert result.city == "Nelamangala"
        assert "NH-48" in result.short_address
