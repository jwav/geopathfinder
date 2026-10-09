"""Command-line interface for GeoPathfinder."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from geopathfinder.configuration import load_ors_api_key
from geopathfinder.exceptions import ConfigurationError, GeoPathfinderError
from geopathfinder.models import AddressMatch, Route, TravelMode
from geopathfinder.services.ban import BanGeocoder
from geopathfinder.services.openrouteservice import OpenRouteServiceRouter


AVAILABLE_MODES = (
    TravelMode.WALKING,
    TravelMode.CYCLING,
    TravelMode.CAR,
)
IMPLEMENTED_MODES = frozenset(AVAILABLE_MODES)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="geopathfinder",
        description=(
            "Find travel durations between French addresses. "
            "Available modes: walking, cycling, car."
        ),
        epilog=(
            "Example:\n"
            '  geopathfinder route "10 rue Denfert Rochereau, 33130 Bègles" '
            '"2 rue Marc Sangnier, 33130 Bègles" --mode cycling\n\n'
            "ORS authentication is read from api_keys/ORS_API_KEY.key by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    route = subparsers.add_parser(
        "route",
        help="Find travel durations between two addresses.",
        description=(
            "Calculate one or more travel durations. Available modes: walking, "
            "cycling, car. Public transport is planned but not implemented yet."
        ),
        epilog=(
            "Examples:\n"
            '  geopathfinder route "10 rue Denfert Rochereau, 33130 Bègles" '
            '"2 rue Marc Sangnier, 33130 Bègles"\n'
            '  geopathfinder route "10 rue Denfert Rochereau, 33130 Bègles" '
            '"2 rue Marc Sangnier, 33130 Bègles" --mode walking --json'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    route.add_argument("start", help="Origin address, preferably a complete French address.")
    route.add_argument("destination", help="Destination address, preferably a complete French address.")
    route.add_argument(
        "--mode",
        choices=[mode.value for mode in AVAILABLE_MODES],
        action="append",
        dest="modes",
        help="Mode to calculate; repeat it for several modes. Defaults to walking, cycling, and car.",
    )
    route.add_argument(
        "--ors-key-file",
        type=Path,
        help=(
            "Path to an ORS key file. Defaults to api_keys/ORS_API_KEY.key "
            "in the current project."
        ),
    )
    route.add_argument(
        "--ban-base-url",
        help="Override the public BAN geocoding endpoint.",
    )
    route.add_argument(
        "--ors-base-url",
        help="Override the current HeiGIT ORS directions endpoint.",
    )
    route.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a human-readable summary.",
    )
    return parser


def _address_as_dict(address: AddressMatch) -> dict[str, Any]:
    return {
        "label": address.label,
        "latitude": address.coordinate.latitude,
        "longitude": address.coordinate.longitude,
        "score": address.score,
    }


def _route_as_dict(route: Route) -> dict[str, Any]:
    return {
        "mode": route.mode.value,
        "duration_seconds": route.duration_seconds,
        "distance_metres": route.distance_metres,
        "provider": route.provider,
    }


def _format_duration(seconds: float) -> str:
    total_seconds = round(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _print_human_result(start: AddressMatch, destination: AddressMatch, routes: list[Route]) -> None:
    print(f"From: {start.label}")
    print(f"To:   {destination.label}")
    for route in routes:
        distance_km = route.distance_metres / 1_000
        print(
            f"{route.mode.value}: {_format_duration(route.duration_seconds)} "
            f"({distance_km:.1f} km; {route.provider})"
        )


def _resolve_modes(values: list[str] | None) -> list[TravelMode]:
    modes = [TravelMode(value) for value in values] if values else list(AVAILABLE_MODES)
    unavailable = [mode for mode in modes if mode not in IMPLEMENTED_MODES]
    if unavailable:
        names = ", ".join(mode.value for mode in unavailable)
        raise ConfigurationError(f"The following modes are not implemented yet: {names}")
    return modes


def run_route(args: argparse.Namespace) -> int:
    """Geocode addresses, request routes, and print the result."""

    modes = _resolve_modes(args.modes)
    ors_api_key = load_ors_api_key(args.ors_key_file)

    geocoder_options: dict[str, str] = {}
    if args.ban_base_url:
        geocoder_options["base_url"] = args.ban_base_url
    geocoder = BanGeocoder(**geocoder_options)
    start = geocoder.geocode(args.start)
    destination = geocoder.geocode(args.destination)
    router_options: dict[str, str] = {"api_key": ors_api_key}
    if args.ors_base_url:
        router_options["base_url"] = args.ors_base_url
    router = OpenRouteServiceRouter(**router_options)
    routes = [router.route(start.coordinate, destination.coordinate, mode) for mode in modes]

    if args.json:
        print(
            json.dumps(
                {
                    "start": _address_as_dict(start),
                    "destination": _address_as_dict(destination),
                    "routes": [_route_as_dict(route) for route in routes],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_human_result(start, destination, routes)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GeoPathfinder command-line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "route":
            return run_route(args)
    except GeoPathfinderError as error:
        parser.exit(2, f"error: {error}\n")
    parser.error(f"Unsupported command: {args.command}")
    return 2

