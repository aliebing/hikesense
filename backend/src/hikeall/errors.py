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

    def __init__(self, gap_m: float, at: tuple[float, float], context: str = "") -> None:
        msg = f"gap of {gap_m:.0f} m at {at}"
        super().__init__(f"{context}: {msg}" if context else msg)
        self.gap_m = gap_m
        self.at = at
        self.context = context


class StageOffsetError(HikeAllError):
    """A stage start/end place lies too far from the trail line."""

    def __init__(self, seq: int, name: str, offset_m: float) -> None:
        super().__init__(f"stage {seq}: '{name}' is {offset_m:.0f} m away from the trail line")
        self.seq = seq
        self.name = name
        self.offset_m = offset_m


class StageOrderError(HikeAllError):
    """Stage boundaries are not in trail order (reversed, empty or overlapping stage)."""

    def __init__(self, seq: int, name: str, reason: str) -> None:
        super().__init__(f"stage {seq}: '{name}' {reason}")
        self.seq = seq
        self.name = name


class OutsideRegionError(HikeAllError):
    """Imported geometry leaves the Black Forest import bounding box."""
