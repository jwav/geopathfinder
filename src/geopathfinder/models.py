"""Provider-independent value objects returned by GeoPathfinder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TravelMode(StrEnum):
    """Travel modes exposed by the public CLI and package API."""

    WALKING = "walking"
    CYCLING = "cycling"
    CAR = "car"
    PUBLIC_TRANSPORT = "public-transport"


@dataclass(frozen=True, slots=True)
class Coordinate:
    """A WGS 84 coordinate expressed as latitude and longitude."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class AddressMatch:
    """A normalized address and the point returned for it."""

    label: str
    coordinate: Coordinate
    score: float | None = None


@dataclass(frozen=True, slots=True)
class Route:
    """A normalized route result from any routing provider."""

    mode: TravelMode
    duration_seconds: float
    distance_metres: float
    provider: str

