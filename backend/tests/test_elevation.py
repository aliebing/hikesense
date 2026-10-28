import pytest
from conftest import LINE, Ramp

from hikeall.ingest.elevation import elevation_stats


def test_elevation_stats_on_ramp():
    s = elevation_stats(LINE, Ramp())
    assert 700 <= s.ascent_m <= 760 and s.descent_m == 0 and len(s.profile) <= 300


def test_missing_elevation_raises():
    class Hole:
        def elevations(self, pts):
            return [None] * len(pts)

    with pytest.raises(ValueError):
        elevation_stats(LINE, Hole())
