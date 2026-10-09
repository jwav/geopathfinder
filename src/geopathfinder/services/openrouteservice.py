"""Routing adapter for the openrouteservice directions API.

The public ORS API accepts longitude/latitude coordinate pairs, while the
package's :class:`~geopathfinder.models.Coordinate` stores latitude first.
Keeping that conversion here prevents provider-specific coordinate ordering
from leaking into the CLI or other callers.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from typing import Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from geopathfinder.exceptions import (
    ConfigurationError,
    RouteNotFoundError,
    ServiceError,
)
from geopathfinder.models import Coordinate, Route, TravelMode


DEFAULT_BASE_URL: Final = "https://api.heigit.org/openrouteservice/v2/directions"
DEFAULT_TIMEOUT_SECONDS: Final = 15.0
_ROUTE_NOT_FOUND_ERROR_CODES: Final = frozenset({2009, 2010})

# ``urlopen`` is deliberately injected through the constructor so tests can
# exercise response normalization without making real network requests.
HttpOpener = Callable[..., Any]


class OpenRouteServiceRouter:
    """Fetch walking, cycling, and car routes from openrouteservice.

    ``base_url`` is the directions endpoint prefix of an ORS-compatible API,
    such as ``https://api.heigit.org/openrouteservice/v2/directions`` or the
    corresponding path on a self-hosted instance. The API key is never
    included in an error message or URL; it is sent only in the
    ``Authorization`` request header.
    """

    _PROFILES: Final[Mapping[TravelMode, str]] = {
        TravelMode.WALKING: "foot-walking",
        TravelMode.CYCLING: "cycling-regular",
        TravelMode.CAR: "driving-car",
    }

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        opener: HttpOpener = urlopen,
    ) -> None:
        """Create a router with explicit provider configuration.

        Args:
            api_key: An ORS API key.
            base_url: The ORS directions endpoint prefix. A trailing slash is
                accepted.
            timeout_seconds: Maximum time for one HTTP request.
            opener: HTTP callable compatible with :func:`urllib.request.urlopen`.
        """
        if not isinstance(api_key, str) or not api_key.strip():
            raise ConfigurationError("An openrouteservice API key is required.")

        self._base_url = self._validate_base_url(base_url)
        self._timeout_seconds = self._validate_timeout(timeout_seconds)
        self._api_key = api_key.strip()
        self._opener = opener

    @property
    def base_url(self) -> str:
        """Return the configured ORS directions prefix without a trailing slash."""
        return self._base_url

    def route(
        self,
        start: Coordinate,
        destination: Coordinate,
        mode: TravelMode,
    ) -> Route:
        """Return the duration and distance for one supported travel mode.

        The public ORS directions endpoint does not provide public-transport
        routing, so requesting :attr:`TravelMode.PUBLIC_TRANSPORT` raises a
        :class:`ServiceError` rather than silently returning a different mode.
        """
        profile = self._profile_for(mode)
        payload = {
            "coordinates": [
                [start.longitude, start.latitude],
                [destination.longitude, destination.latitude],
            ],
            "instructions": False,
            "geometry": False,
        }
        response = self._post_directions(profile, payload)
        return self._route_from_response(response, mode)

    def _post_directions(
        self,
        profile: str,
        payload: Mapping[str, object],
    ) -> object:
        request = Request(
            f"{self._base_url}/{profile}/json",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Authorization": self._api_key,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            http_response = self._opener(request, timeout=self._timeout_seconds)
            try:
                raw_response = http_response.read()
            finally:
                close = getattr(http_response, "close", None)
                if callable(close):
                    close()
        except HTTPError as error:
            self._raise_http_error(error)
        except (TimeoutError, URLError, OSError) as error:
            raise ServiceError("OpenRouteService request failed.") from error

        if isinstance(raw_response, bytearray):
            raw_response = bytes(raw_response)
        if not isinstance(raw_response, bytes):
            raise ServiceError("OpenRouteService returned an invalid response body.")

        try:
            return json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ServiceError("OpenRouteService returned invalid JSON.") from error

    @classmethod
    def _raise_http_error(cls, error: HTTPError) -> None:
        """Translate a provider HTTP failure to a stable domain exception."""
        is_no_route = error.code == 404 or cls._http_error_has_no_route_code(error)
        error.close()
        if is_no_route:
            raise RouteNotFoundError("OpenRouteService could not find a route.") from error
        if error.code == 429:
            raise ServiceError("OpenRouteService rate limit exceeded.") from error
        raise ServiceError(f"OpenRouteService returned HTTP {error.code}.") from error

    @staticmethod
    def _http_error_has_no_route_code(error: HTTPError) -> bool:
        """Recognize ORS's documented no-route payloads without exposing them."""
        try:
            body = error.read()
            if not isinstance(body, bytes):
                return False
            payload = json.loads(body.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False

        if not isinstance(payload, Mapping):
            return False
        error_payload = payload.get("error")
        if not isinstance(error_payload, Mapping):
            return False
        code = error_payload.get("code")
        return isinstance(code, int) and not isinstance(code, bool) and code in _ROUTE_NOT_FOUND_ERROR_CODES

    @classmethod
    def _route_from_response(cls, payload: object, mode: TravelMode) -> Route:
        if not isinstance(payload, Mapping):
            raise ServiceError("OpenRouteService returned an unexpected response schema.")

        routes = payload.get("routes")
        if not isinstance(routes, list):
            raise ServiceError("OpenRouteService returned an unexpected response schema.")
        if not routes:
            raise RouteNotFoundError("OpenRouteService could not find a route.")

        first_route = routes[0]
        if not isinstance(first_route, Mapping):
            raise ServiceError("OpenRouteService returned an unexpected response schema.")
        summary = first_route.get("summary")
        if not isinstance(summary, Mapping):
            raise ServiceError("OpenRouteService returned an unexpected response schema.")

        return Route(
            mode=mode,
            duration_seconds=cls._summary_number(summary, "duration"),
            distance_metres=cls._summary_number(summary, "distance"),
            provider="openrouteservice",
        )

    @staticmethod
    def _summary_number(summary: Mapping[object, object], name: str) -> float:
        value = summary.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ServiceError("OpenRouteService returned an invalid route summary.")
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ServiceError("OpenRouteService returned an invalid route summary.")
        return result

    @classmethod
    def _profile_for(cls, mode: TravelMode) -> str:
        if not isinstance(mode, TravelMode):
            raise ServiceError("A valid travel mode is required for OpenRouteService routing.")
        try:
            return cls._PROFILES[mode]
        except KeyError as error:
            raise ServiceError(
                f"OpenRouteService does not support the {mode.value!r} travel mode."
            ) from error

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        if not isinstance(base_url, str):
            raise ConfigurationError("ORS_BASE_URL must be an HTTP(S) URL.")
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            not normalized
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError("ORS_BASE_URL must be an HTTP(S) URL.")
        return normalized

    @staticmethod
    def _validate_timeout(timeout_seconds: float) -> float:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ConfigurationError("ORS timeout must be a positive number of seconds.")
        timeout = float(timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ConfigurationError("ORS timeout must be a positive number of seconds.")
        return timeout
