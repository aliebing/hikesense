import pytest

from hikesense.geo import (
    bbox_of,
    distance_point_to_path_km,
    elevation_stats,
    haversine_km,
    path_length_km,
    sample_points,
    simplify_segments,
)


def test_haversine_one_degree_latitude():
    assert haversine_km((48.0, 8.0), (49.0, 8.0)) == pytest.approx(111.2, abs=0.2)


def test_path_length_sums_segments():
    seg = [(48.0, 8.0), (48.01, 8.0), (48.02, 8.0)]
    assert path_length_km([seg]) == pytest.approx(2.224, abs=0.01)
    assert path_length_km([seg, seg]) == pytest.approx(4.448, abs=0.02)


def test_bbox_of_pads_single_point():
    box = bbox_of([[(48.0, 8.0), (48.0, 8.0)]])
    assert box.south < 48.0 < box.north


def test_distance_point_to_path():
    line = [[(48.0, 8.0), (48.0, 8.1)]]
    assert distance_point_to_path_km((48.001, 8.05), line) == pytest.approx(0.111, abs=0.005)
    assert distance_point_to_path_km((48.0, 8.2), line) == pytest.approx(7.44, abs=0.05)


def test_sample_points_keeps_ends_and_caps():
    seg = [(48.0 + i * 0.0005, 8.0) for i in range(2001)]
    pts = sample_points([seg], step_km=0.2, max_points=300)
    assert pts[0] == seg[0]
    assert pts[-1] == seg[-1]
    assert len(pts) == 300


def test_elevation_stats_ignores_noise():
    stats = elevation_stats([100, 101, 102, 110, 105, 90], threshold_m=3.0)
    assert (stats.ascent_m, stats.descent_m) == (10, 20)
    assert (stats.min_ele_m, stats.max_ele_m) == (90, 110)


def test_elevation_stats_requires_values():
    with pytest.raises(ValueError):
        elevation_stats([])


def _north(lat0, lon, metres):  # a point `metres` north of (lat0, lon)
    return (lat0 + metres / 111_195, lon)


def test_straight_line_collapses_to_its_endpoints():
    line = [(47.9, 8.0 + i * 0.001) for i in range(20)]
    assert simplify_segments([line]) == [[line[0], line[-1]]]


def test_small_wiggles_go_and_real_bends_stay():
    a, b = (47.9, 8.0), (47.9, 8.01)
    wiggle = _north(47.9, 8.005, 5)  # 5 m off the line: removed
    bend = _north(47.9, 8.005, 50)  # 50 m off the line: kept
    assert simplify_segments([[a, wiggle, b]]) == [[a, b]]
    assert simplify_segments([[a, bend, b]]) == [[a, bend, b]]


def test_every_original_point_stays_within_the_tolerance():
    zigzag = [(47.9 + (0.00008 if i % 2 else 0), 8.0 + i * 0.0005) for i in range(200)]
    simple = simplify_segments([zigzag], tolerance_m=10)[0]
    assert simple[0] == zigzag[0] and simple[-1] == zigzag[-1]
    assert len(simple) < len(zigzag)
    assert max(distance_point_to_path_km(p, [simple]) for p in zigzag) <= 0.010 + 1e-9


def test_segments_are_simplified_independently_and_short_ones_kept():
    one = [(47.9, 8.0)]
    two = [(47.9, 8.0), (47.9, 8.1)]
    assert simplify_segments([one, two]) == [one, two]


def test_locate_returns_nearest_vertex_and_distance_m():
    from hikesense.geo import locate

    line = [(48.0, 8.0), (48.0, 8.01), (48.0, 8.02)]
    idx, dist_m = locate(line, (48.0005, 8.0101))
    assert idx == 1
    assert 50 < dist_m < 60


def test_locate_start_index_searches_only_forward():
    from hikesense.geo import locate

    line = [(48.0, 8.0), (48.0, 8.01), (48.0, 8.02), (48.0, 8.01), (48.0, 8.0)]
    assert locate(line, (48.0, 8.01))[0] == 1
    assert locate(line, (48.0, 8.01), start=2)[0] == 3  # absolute index
