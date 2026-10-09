"""Tests for provider-independent domain value objects."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from geopathfinder.models import AddressMatch, Coordinate, Route, TravelMode


class CoordinateTests(unittest.TestCase):
    def test_coordinate_accepts_wgs84_boundaries(self) -> None:
        coordinate = Coordinate(latitude=90, longitude=-180)

        self.assertEqual(coordinate.latitude, 90)
        self.assertEqual(coordinate.longitude, -180)

    def test_coordinate_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            Coordinate(latitude=90.0001, longitude=0)
        with self.assertRaises(ValueError):
            Coordinate(latitude=0, longitude=-180.0001)

    def test_coordinate_is_immutable(self) -> None:
        coordinate = Coordinate(latitude=44.8, longitude=-0.5)

        with self.assertRaises(FrozenInstanceError):
            coordinate.latitude = 0  # type: ignore[misc]


class ResultModelTests(unittest.TestCase):
    def test_result_models_preserve_normalized_provider_data(self) -> None:
        coordinate = Coordinate(latitude=44.8, longitude=-0.5)
        address = AddressMatch("10 rue Example, Bordeaux", coordinate, score=0.9)
        route = Route(
            mode=TravelMode.CYCLING,
            duration_seconds=420,
            distance_metres=1_500,
            provider="example-router",
        )

        self.assertEqual(address.coordinate, coordinate)
        self.assertEqual(address.score, 0.9)
        self.assertEqual(route.mode, TravelMode.CYCLING)
        self.assertEqual(route.duration_seconds, 420)
        self.assertEqual(route.distance_metres, 1_500)
        self.assertEqual(route.provider, "example-router")
        self.assertEqual(TravelMode.CYCLING.value, "cycling")


if __name__ == "__main__":
    unittest.main()
