"""Offline tests for the BAN geocoding adapter."""

from __future__ import annotations

import json
import unittest
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

from geopathfinder.exceptions import AddressNotFoundError, ServiceError
from geopathfinder.services.ban import BanGeocoder
from tests.test_addresses import START_ADDRESS


class FakeResponse:
    """A minimal response object returned by fake HTTP openers."""

    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def feature_collection(*features: dict[str, Any]) -> dict[str, object]:
    return {"type": "FeatureCollection", "features": list(features)}


def valid_feature() -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-0.570493, 44.841464]},
        "properties": {
            "label": "Place de la Bourse 33000 Bordeaux",
            "score": 0.9725681818181817,
        },
    }


class BanGeocoderTests(unittest.TestCase):
    def test_geocode_encodes_query_and_normalizes_feature(self) -> None:
        seen: list[Request] = []
        response = FakeResponse(feature_collection(valid_feature()))

        def opener(request: Request, *, timeout: float) -> FakeResponse:
            seen.append(request)
            self.assertEqual(timeout, 10.0)
            return response

        match = BanGeocoder(opener=opener).geocode(START_ADDRESS)

        self.assertEqual(len(seen), 1)
        parameters = parse_qs(urlsplit(seen[0].full_url).query)
        self.assertEqual(parameters["q"], [START_ADDRESS])
        self.assertEqual(parameters["limit"], ["1"])
        self.assertEqual(match.label, "Place de la Bourse 33000 Bordeaux")
        self.assertEqual(match.coordinate.latitude, 44.841464)
        self.assertEqual(match.coordinate.longitude, -0.570493)
        self.assertAlmostEqual(match.score or 0, 0.9725681818181817)
        self.assertTrue(response.closed)

    def test_geocode_raises_when_ban_returns_no_features(self) -> None:
        geocoder = BanGeocoder(opener=lambda request, *, timeout: FakeResponse(feature_collection()))

        with self.assertRaises(AddressNotFoundError):
            geocoder.geocode(START_ADDRESS)

    def test_geocode_translates_network_errors(self) -> None:
        def unavailable(request: Request, *, timeout: float) -> FakeResponse:
            raise URLError("offline")

        geocoder = BanGeocoder(opener=unavailable)

        with self.assertRaises(ServiceError) as raised:
            geocoder.geocode(START_ADDRESS)

        self.assertEqual(str(raised.exception), "Unable to reach the BAN geocoding service.")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
