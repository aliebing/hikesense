"""Typed exceptions. Adapters raise these."""


class HikeAllError(Exception):
    """Base class for all expected Hike all about failures."""


class OverpassError(HikeAllError):
    """Overpass API request failed or returned unusable data."""


class ElevationUnavailable(HikeAllError):
    """Elevation service failed; elevation stays unknown."""


class ImageFetchError(HikeAllError):
    """Wikimedia Commons / Wikidata request for route photos failed."""
