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


class Zigzag:
    """Flat terrain with +-1 m DEM noise on alternating samples."""

    def elevations(self, pts):
        return [500.0 + (1.0 if i % 2 else -1.0) for i in range(len(pts))]


def test_noise_is_smoothed_away():
    s = elevation_stats(LINE, Zigzag())
    assert s.ascent_m <= 40 and s.descent_m <= 40  # 5-pt average leaves ~30 m; unsmoothed ~150


def test_uneven_vertex_spacing_equals_even_spacing():
    # same straight geometry, vertices very unevenly spaced (clustered at the start)
    lons = [8.0, 8.0001, 8.0002, 8.0003, 8.02, 8.05, 8.0999, 8.1]
    uneven = [(48.0, x) for x in lons]
    even = [(48.0, 8.0 + i * 0.0001) for i in range(1001)]  # 0.1 deg/1000, dense
    a = elevation_stats(uneven, Ramp())
    b = elevation_stats(even, Ramp())
    assert abs(a.ascent_m - b.ascent_m) <= 2
    assert len(a.profile) == len(b.profile)


def test_long_line_profile_is_thinned_but_keeps_ends():
    long_line = [(48.0, 8.0 + i * 0.01) for i in range(21)]  # ~14.9 km -> ~298 samples
    longer = [(48.0, 8.0 + i * 0.01) for i in range(41)]  # ~29.7 km -> ~595 samples
    s = elevation_stats(longer, Ramp())
    assert len(s.profile) == 300
    assert s.profile[0][0] == 0.0
    assert s.profile[-1][0] == pytest.approx(29.7, abs=0.2)
    assert s.ascent_m == pytest.approx(0.4 * 7400 * 1.0, rel=0.02)  # unaffected by thinning
    assert len(elevation_stats(long_line, Ramp()).profile) <= 300


@pytest.mark.parametrize("step", [0, -50])
def test_non_positive_step_raises(step):
    with pytest.raises(ValueError):
        elevation_stats(LINE, Ramp(), step_m=step)
