"""Typed exceptions. Adapters raise these."""


class HikeAllError(Exception):
    """Base class for all expected Hike all about failures."""


class OverpassError(HikeAllError):
    """Overpass API request failed or returned unusable data."""


class ElevationUnavailable(HikeAllError):
    """Elevation service failed; elevation stays unknown."""


class ImageFetchError(HikeAllError):
    """Wikimedia Commons / Wikidata request for route photos failed."""


class GapError(HikeAllError):
    """Two route segments cannot be connected within the allowed gap."""

    def __init__(self, gap_m: float, at: tuple[float, float]) -> None:
        super().__init__(f"gap of {gap_m:.0f} m at {at}")
        self.gap_m = gap_m
        self.at = at
