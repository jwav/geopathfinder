"""Domain exceptions raised by GeoPathfinder providers."""


class GeoPathfinderError(Exception):
    """Base class for expected GeoPathfinder errors."""


class ConfigurationError(GeoPathfinderError):
    """Raised when required provider configuration is missing or invalid."""


class ServiceError(GeoPathfinderError):
    """Raised when an upstream service cannot complete a request."""


class AddressNotFoundError(ServiceError):
    """Raised when an address cannot be geocoded."""


class RouteNotFoundError(ServiceError):
    """Raised when a provider cannot find a route between two locations."""

