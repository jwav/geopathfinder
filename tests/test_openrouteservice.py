"""Offline tests for the openrouteservice routing adapter."""

from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError, URLError

from geopathfinder.exceptions import ConfigurationError, RouteNotFoundError, ServiceError
from geopathfinder.models import Coordinate, TravelMode
from geopathfinder.services.openrouteservice import OpenRouteServiceRouter


class FakeResponse:
    """Small urlopen-compatible response for deterministic provider tests."""

    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


class OpenRouteServiceRouterTests(unittest.TestCase):
    """Verify request formation and translation of ORS responses/errors."""

    def setUp(self) -> None:
        self.start = Coordinate(latitude=44.8001, longitude=-0.5482)
        self.destination = Coordinate(latitude=44.7959, longitude=-0.5431)

    def test_walking_request_uses_profile_and_longitude_latitude_coordinates(self) -> None:
        captured: dict[str, object] = {}

        def opener(request: object, *, timeout: float) -> FakeResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"routes": [{"summary": {"duration": 381.2, "distance": 492.8}}]})

        route = OpenRouteServiceRouter("test-key", opener=opener).route(
            self.start,
            self.destination,
            TravelMode.WALKING,
        )

        request = captured["request"]
        self.assertEqual(
            request.full_url,
            "https://api.heigit.org/openrouteservice/v2/directions/foot-walking/json",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "test-key")
        self.assertEqual(captured["timeout"], 15.0)
        self.assertEqual(
            json.loads(request.data),
            {
                "coordinates": [[-0.5482, 44.8001], [-0.5431, 44.7959]],
                "instructions": False,
                "geometry": False,
            },
        )
        self.assertEqual(route.mode, TravelMode.WALKING)
        self.assertEqual(route.duration_seconds, 381.2)
        self.assertEqual(route.distance_metres, 492.8)
        self.assertEqual(route.provider, "openrouteservice")

    def test_parses_a_car_route_from_a_custom_directions_endpoint(self) -> None:
        response = FakeResponse({"routes": [{"summary": {"duration": 1_265, "distance": 12_345.6}}]})

        def opener(_: object, *, timeout: float) -> FakeResponse:
            self.assertEqual(timeout, 8.5)
            return response

        router = OpenRouteServiceRouter(
            "test-key",
            base_url="https://ors.example.test/ors/v2/directions/",
            timeout_seconds=8.5,
            opener=opener,
        )
        route = router.route(self.start, self.destination, TravelMode.CAR)

        self.assertEqual(router.base_url, "https://ors.example.test/ors/v2/directions")
        self.assertEqual(route.mode, TravelMode.CAR)
        self.assertEqual(route.duration_seconds, 1_265.0)
        self.assertEqual(route.distance_metres, 12_345.6)
        self.assertTrue(response.closed)

    def test_missing_api_key_is_configuration_error(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "API key"):
            OpenRouteServiceRouter("   ")

    def test_empty_routes_and_ors_no_route_error_raise_route_not_found(self) -> None:
        no_routes = OpenRouteServiceRouter(
            "test-key",
            opener=lambda _request, *, timeout: FakeResponse({"routes": []}),
        )
        with self.assertRaises(RouteNotFoundError):
            no_routes.route(self.start, self.destination, TravelMode.CYCLING)

        error = HTTPError(
            url="https://ors.example.test/v2/directions/cycling-regular/json",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error": {"code": 2009}}'),
        )
        upstream_no_route = OpenRouteServiceRouter(
            "test-key",
            opener=lambda _request, *, timeout: self._raise(error),
        )
        with self.assertRaises(RouteNotFoundError):
            upstream_no_route.route(self.start, self.destination, TravelMode.CYCLING)

    def test_network_failure_is_service_error(self) -> None:
        router = OpenRouteServiceRouter(
            "test-key",
            opener=lambda _request, *, timeout: self._raise(URLError("offline")),
        )

        with self.assertRaisesRegex(ServiceError, "request failed"):
            router.route(self.start, self.destination, TravelMode.CAR)

    @staticmethod
    def _raise(error: BaseException) -> None:
        raise error


if __name__ == "__main__":
    unittest.main()
