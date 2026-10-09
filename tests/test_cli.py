"""Offline tests for the public command-line workflow."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, call, patch

from geopathfinder import cli
from geopathfinder.exceptions import ConfigurationError
from geopathfinder.models import AddressMatch, Coordinate, Route, TravelMode
from tests.test_addresses import DESTINATION_ADDRESS, START_ADDRESS


class CommandLineTests(unittest.TestCase):
    """Exercise argument handling and output without calling remote services."""

    def setUp(self) -> None:
        self.start_match = AddressMatch(
            label=START_ADDRESS,
            coordinate=Coordinate(latitude=44.8001, longitude=-0.5482),
            score=0.98,
        )
        self.destination_match = AddressMatch(
            label=DESTINATION_ADDRESS,
            coordinate=Coordinate(latitude=44.7959, longitude=-0.5431),
            score=0.96,
        )

    def test_parser_accepts_repeated_modes_and_json_output(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "route",
                START_ADDRESS,
                DESTINATION_ADDRESS,
                "--mode",
                "walking",
                "--mode",
                "car",
                "--ors-key-file",
                "test-key.txt",
                "--json",
            ]
        )

        self.assertEqual(args.command, "route")
        self.assertEqual(args.start, START_ADDRESS)
        self.assertEqual(args.destination, DESTINATION_ADDRESS)
        self.assertEqual(args.modes, ["walking", "car"])
        self.assertEqual(args.ors_key_file, Path("test-key.txt"))
        self.assertTrue(args.json)

    def test_route_help_lists_available_modes_and_key_file(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            cli.main(["route", "--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("walking, cycling, car", help_text)
        self.assertIn("Public transport is planned but not implemented yet", help_text)
        self.assertIn("api_keys/ORS_API_KEY.key", help_text)

    @patch("geopathfinder.cli.OpenRouteServiceRouter")
    @patch("geopathfinder.cli.BanGeocoder")
    @patch("geopathfinder.cli.load_ors_api_key", return_value="test-key")
    def test_route_json_uses_normalized_results(
        self, load_key: MagicMock, geocoder_class: MagicMock, router_class: MagicMock
    ) -> None:
        geocoder = geocoder_class.return_value
        geocoder.geocode.side_effect = [self.start_match, self.destination_match]
        router = router_class.return_value
        walking_route = Route(
            mode=TravelMode.WALKING,
            duration_seconds=123.4,
            distance_metres=789.0,
            provider="openrouteservice",
        )
        car_route = Route(
            mode=TravelMode.CAR,
            duration_seconds=45.0,
            distance_metres=1_234.5,
            provider="openrouteservice",
        )
        router.route.side_effect = [walking_route, car_route]

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "route",
                    START_ADDRESS,
                    DESTINATION_ADDRESS,
                    "--mode",
                    "walking",
                    "--mode",
                    "car",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        geocoder.geocode.assert_has_calls([call(START_ADDRESS), call(DESTINATION_ADDRESS)])
        router_class.assert_called_once_with(api_key="test-key")
        router.route.assert_has_calls(
            [
                call(
                    self.start_match.coordinate,
                    self.destination_match.coordinate,
                    TravelMode.WALKING,
                ),
                call(
                    self.start_match.coordinate,
                    self.destination_match.coordinate,
                    TravelMode.CAR,
                ),
            ]
        )
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "start": {
                    "label": START_ADDRESS,
                    "latitude": 44.8001,
                    "longitude": -0.5482,
                    "score": 0.98,
                },
                "destination": {
                    "label": DESTINATION_ADDRESS,
                    "latitude": 44.7959,
                    "longitude": -0.5431,
                    "score": 0.96,
                },
                "routes": [
                    {
                        "mode": "walking",
                        "duration_seconds": 123.4,
                        "distance_metres": 789.0,
                        "provider": "openrouteservice",
                    },
                    {
                        "mode": "car",
                        "duration_seconds": 45.0,
                        "distance_metres": 1_234.5,
                        "provider": "openrouteservice",
                    },
                ],
            },
        )

    @patch("geopathfinder.cli.OpenRouteServiceRouter")
    @patch("geopathfinder.cli.BanGeocoder")
    @patch("geopathfinder.cli.load_ors_api_key", return_value="test-key")
    def test_unimplemented_public_transport_fails_before_service_calls(
        self, load_key: MagicMock, geocoder_class: MagicMock, router_class: MagicMock
    ) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(
                [
                    "route",
                    START_ADDRESS,
                    DESTINATION_ADDRESS,
                    "--mode",
                    "public-transport",
                ]
            )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("public-transport", stderr.getvalue())
        geocoder_class.assert_not_called()
        router_class.assert_not_called()

    @patch("geopathfinder.cli.OpenRouteServiceRouter")
    @patch("geopathfinder.cli.BanGeocoder")
    @patch(
        "geopathfinder.cli.load_ors_api_key",
        side_effect=ConfigurationError("ORS API key file not found"),
    )
    def test_missing_ors_key_file_fails_before_service_calls(
        self, load_key: MagicMock, geocoder_class: MagicMock, router_class: MagicMock
    ) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(["route", START_ADDRESS, DESTINATION_ADDRESS])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("ORS API key file not found", stderr.getvalue())
        geocoder_class.assert_not_called()
        router_class.assert_not_called()

    def test_duration_formatting_is_compact_and_rounded(self) -> None:
        self.assertEqual(cli._format_duration(8.1), "8s")
        self.assertEqual(cli._format_duration(61.6), "1m 02s")
        self.assertEqual(cli._format_duration(3_661), "1h 01m")


if __name__ == "__main__":
    unittest.main()
