"""DIN 33466 hiking time estimate (guidance, excludes breaks)."""

from __future__ import annotations

from hikeall.models import HikingTime

FORMULA = (
    "max(h, v) + min(h, v) / 2 with h = km / 4 and v = ascent / 300 + descent / 500 "
    "(DIN 33466, hours, no breaks)"
)


def din33466(distance_km: float, ascent_m: float, descent_m: float) -> HikingTime:
    if min(distance_km, ascent_m, descent_m) < 0:
        raise ValueError("distance, ascent and descent must be >= 0")
    horizontal = distance_km / 4.0
    vertical = ascent_m / 300.0 + descent_m / 500.0
    hours = max(horizontal, vertical) + min(horizontal, vertical) / 2
    return HikingTime(
        hours=round(hours, 2),
        horizontal_h=round(horizontal, 2),
        vertical_h=round(vertical, 2),
        formula=FORMULA,
    )

