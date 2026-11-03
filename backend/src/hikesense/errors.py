"""Typed exceptions. Adapters raise these."""


class HikeSenseError(Exception):
    """Base class for all expected HikeSense failures."""


class OverpassError(HikeSenseError):
    """Overpass API request failed or returned unusable data."""


class ElevationUnavailable(HikeSenseError):
    """Elevation service failed; elevation stays unknown."""


class ImageFetchError(HikeSenseError):
    """Wikimedia Commons / Wikidata request for route photos failed."""


class GapError(HikeSenseError):
    """Two route segments cannot be connected within the allowed gap."""

    def __init__(self, gap_m: float, at: tuple[float, float], context: str = "") -> None:
        msg = f"gap of {gap_m:.0f} m at {at}"
        super().__init__(f"{context}: {msg}" if context else msg)
        self.gap_m = gap_m
        self.at = at
        self.context = context


class StageOffsetError(HikeSenseError):
    """A stage start/end place lies too far from the trail line."""

    def __init__(self, seq: int, name: str, offset_m: float) -> None:
        super().__init__(f"stage {seq}: '{name}' is {offset_m:.0f} m away from the trail line")
        self.seq = seq
        self.name = name
        self.offset_m = offset_m


class StageOrderError(HikeSenseError):
    """Stage boundaries are not in trail order (reversed, empty or overlapping stage)."""

    def __init__(self, seq: int, name: str, reason: str) -> None:
        super().__init__(f"stage {seq}: '{name}' {reason}")
        self.seq = seq
        self.name = name


class OutsideRegionError(HikeSenseError):
    """Imported geometry lies in no import region as a whole."""


class KnowledgeError(HikeSenseError):
    """Knowledge corpus is invalid (e.g. own text without sources) or the index is missing."""


class KnowledgeFetchError(HikeSenseError):
    """MediaWiki request for a knowledge article failed."""


class WeatherUnavailable(HikeSenseError):
    """Open-Meteo request failed or returned unusable data; weather stays unknown."""
