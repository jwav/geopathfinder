"""Client for the French Base Adresse Nationale (BAN) geocoding service.

The original ``api-adresse.data.gouv.fr`` endpoint was transferred to the IGN
Géoplateforme.  This module deliberately uses the current public endpoint so
that address lookups work without an API key.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from geopathfinder.exceptions import AddressNotFoundError, ConfigurationError, ServiceError
from geopathfinder.models import AddressMatch, Coordinate


DEFAULT_BASE_URL = "https://data.geopf.fr/geocodage/search"
"""Current public endpoint for the BAN-backed IGN geocoder."""

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_SEARCH_RESULTS = 50


class _Response(Protocol):
    """The small portion of an HTTP response used by :class:`BanGeocoder`."""

    def read(self) -> bytes | str: ...

    def close(self) -> None: ...


HttpOpener = Callable[..., _Response]


class BanGeocoder:
    """Geocode French address text through the free BAN/IGN service.

    ``opener`` is injectable to make unit tests independent of the network. It
    must accept a :class:`urllib.request.Request` and a ``timeout`` keyword,
    like :func:`urllib.request.urlopen`.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        opener: HttpOpener | None = None,
    ) -> None:
        configured_base_url = (
            base_url
            if base_url is not None
            else os.environ.get("GEOPATHFINDER_BAN_BASE_URL")
            or os.environ.get("BAN_BASE_URL")
            or DEFAULT_BASE_URL
        )
        self.base_url = self._validate_base_url(configured_base_url)
        self.timeout = self._validate_timeout(timeout)
        self._opener = opener or urlopen

    def geocode(self, query: str) -> AddressMatch:
        """Return the best BAN match for ``query``.

        Raises:
            AddressNotFoundError: If the query is blank or BAN has no match.
            ServiceError: If BAN cannot be reached or returns malformed data.
        """

        matches = self.search(query, limit=1)
        if not matches:
            raise AddressNotFoundError("No French address matched the supplied query.")
        return matches[0]

    def search(self, query: str, *, limit: int = 5) -> tuple[AddressMatch, ...]:
        """Return up to ``limit`` normalized BAN matches for ``query``.

        An empty result is a valid search outcome. Use :meth:`geocode` when a
        single match is required and an empty result should be an exception.
        """

        normalized_query = self._validate_query(query)
        self._validate_limit(limit)
        payload = self._request_json(normalized_query, limit)
        return self._parse_matches(payload)

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ConfigurationError("BAN base URL must be a non-empty URL.")

        parsed = urlsplit(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError("BAN base URL must be an absolute HTTP(S) URL.")
        return urlunsplit(parsed)

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ConfigurationError("BAN timeout must be a positive number of seconds.")
        normalized_timeout = float(timeout)
        if not math.isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise ConfigurationError("BAN timeout must be a positive number of seconds.")
        return normalized_timeout

    @staticmethod
    def _validate_query(query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            raise AddressNotFoundError("An address query must not be empty.")
        return query.strip()

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer.")
        if not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_SEARCH_RESULTS}.")

    def _request_json(self, query: str, limit: int) -> Mapping[str, Any]:
        request = Request(
            self._build_url(query, limit),
            headers={
                "Accept": "application/json",
                "User-Agent": "geopathfinder/0.1",
            },
        )

        try:
            response = self._opener(request, timeout=self.timeout)
        except HTTPError as error:
            if error.code == 429:
                message = "BAN rate limit reached; retry the request later."
            else:
                message = f"BAN returned HTTP {error.code}."
            raise ServiceError(message) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ServiceError("Unable to reach the BAN geocoding service.") from error

        try:
            raw_body = response.read()
        except (OSError, TimeoutError) as error:
            raise ServiceError("Unable to read BAN's response.") from error
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

        if isinstance(raw_body, bytes):
            try:
                body = raw_body.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ServiceError("BAN returned a non-UTF-8 response.") from error
        elif isinstance(raw_body, str):
            body = raw_body
        else:
            raise ServiceError("BAN returned an unreadable response body.")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ServiceError("BAN returned invalid JSON.") from error
        if not isinstance(payload, dict):
            raise ServiceError("BAN returned an invalid response structure.")
        return payload

    def _build_url(self, query: str, limit: int) -> str:
        """Build a request URL while preserving explicit base-URL parameters."""

        parsed = urlsplit(self.base_url)
        parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
        parameters.update({"q": query, "limit": str(limit)})
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(parameters), parsed.fragment)
        )

    @staticmethod
    def _parse_matches(payload: Mapping[str, Any]) -> tuple[AddressMatch, ...]:
        features = payload.get("features")
        if not isinstance(features, list):
            raise ServiceError("BAN response does not contain a features list.")

        matches: list[AddressMatch] = []
        malformed_features = 0
        for feature in features:
            try:
                matches.append(BanGeocoder._parse_feature(feature))
            except (KeyError, TypeError, ValueError):
                malformed_features += 1

        if features and not matches:
            raise ServiceError("BAN returned address candidates in an invalid format.")
        if malformed_features and not matches:
            raise ServiceError("BAN returned address candidates in an invalid format.")
        return tuple(matches)

    @staticmethod
    def _parse_feature(feature: object) -> AddressMatch:
        if not isinstance(feature, Mapping):
            raise TypeError("feature must be an object")

        properties = feature["properties"]
        geometry = feature["geometry"]
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            raise TypeError("feature properties and geometry must be objects")

        label = properties["label"]
        if not isinstance(label, str) or not label.strip():
            raise ValueError("label is invalid")

        coordinates = geometry["coordinates"]
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            raise ValueError("coordinates are invalid")
        longitude = BanGeocoder._finite_number(coordinates[0], "longitude")
        latitude = BanGeocoder._finite_number(coordinates[1], "latitude")

        raw_score = properties.get("score")
        score = None if raw_score is None else BanGeocoder._finite_number(raw_score, "score")
        return AddressMatch(
            label=label.strip(),
            coordinate=Coordinate(latitude=latitude, longitude=longitude),
            score=score,
        )

    @staticmethod
    def _finite_number(value: object, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite")
        return number


__all__ = [
    "BanGeocoder",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_SEARCH_RESULTS",
]
