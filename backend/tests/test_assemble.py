import pytest

from hikeall.errors import GapError, HikeAllError
from hikeall.geo import path_length_km
from hikeall.ingest.assemble import assemble, assemble_with_report


def test_reversed_and_shuffled_segments_become_one_line():
    a = [(48.0, 8.00), (48.0, 8.01)]
    b = [(48.0, 8.02), (48.0, 8.01)]  # reversed
    c = [(48.0, 8.02), (48.0, 8.03)]
    line = assemble([c, a, b])
    assert line in (
        [(48.0, 8.00), (48.0, 8.01), (48.0, 8.02), (48.0, 8.03)],
        [(48.0, 8.03), (48.0, 8.02), (48.0, 8.01), (48.0, 8.00)],
    )


def test_gap_over_limit_raises():
    with pytest.raises(GapError) as e:
        assemble([[(48.0, 8.00), (48.0, 8.01)], [(48.0, 8.02), (48.0, 8.03)]])  # ~740 m gap
    assert e.value.gap_m > 700
    assert isinstance(e.value, HikeAllError)
    assert e.value.at == (48.0, 8.01)


def test_gap_within_limit_is_bridged():
    line = assemble([[(48.0, 8.00), (48.0, 8.01)], [(48.0, 8.02), (48.0, 8.03)]], max_gap_m=1000)
    assert len(line) == 4


def test_single_segment_returned_as_is():
    seg = [(48.0, 8.0), (48.0, 8.1)]
    assert assemble([seg]) == seg


def test_empty_input_raises_value_error():
    with pytest.raises(ValueError):
        assemble([])


def test_leftover_close_to_the_line_is_dropped_not_bridged():
    # A tiny closed outline next to the trail (a shelter mapped with an empty role) must not
    # break the import, and it must not be appended to the line either.
    a = [(48.0, 8.00), (48.0, 8.01)]
    b = [(48.0, 8.01), (48.0, 8.02)]
    hut = [(48.0005, 8.005), (48.0006, 8.005), (48.0006, 8.0051), (48.0005, 8.005)]  # ~60 m off
    line = assemble([a, hut, b])
    assert line in (
        [(48.0, 8.00), (48.0, 8.01), (48.0, 8.02)],
        [(48.0, 8.02), (48.0, 8.01), (48.0, 8.00)],
    )


def test_leftover_far_from_the_line_still_raises():
    a = [(48.0, 8.00), (48.0, 8.01)]
    far = [(48.01, 8.005), (48.011, 8.005)]  # ~1.1 km off the line
    with pytest.raises(GapError):
        assemble([a, far])


def test_small_closed_ring_is_dropped_and_reported():
    a = [(48.0, 8.00), (48.0, 8.01)]
    b = [(48.0, 8.01), (48.0, 8.02)]
    ring = [(48.0005, 8.005), (48.0006, 8.005), (48.0006, 8.0051), (48.0005, 8.005)]  # ~30 m
    res = assemble_with_report([a, ring, b])
    assert len(res.line) == 3
    assert res.dropped_count == 1
    assert 20 < res.dropped_m < 40


def test_nothing_dropped_reports_zero():
    res = assemble_with_report([[(48.0, 8.00), (48.0, 8.01)], [(48.0, 8.01), (48.0, 8.02)]])
    assert (res.dropped_count, res.dropped_m) == (0, 0.0)


def test_gap_followed_by_parallel_return_leg_still_raises():
    # Out-and-back or dual carriageway: after the chain end there is a >200 m gap, and the
    # remaining leg runs ~170 m beside the chain. It is real route (~1.5 km), not a stray
    # outline, so it must raise instead of being thrown away.
    out = [(48.0, 8.00), (48.0, 8.01), (48.0, 8.02), (48.0, 8.03)]
    back = [(48.0015, 8.025), (48.0015, 8.015), (48.0015, 8.008)]
    with pytest.raises(GapError) as e:
        assemble([out, back])
    assert e.value.gap_m > 300


def _t_junction_segments():
    # b touches a only in a's interior vertex (no shared end vertex); c is a dead-end spur;
    # d is a longer parallel variant of the stretch between two interior vertices of b.
    a = [(48.0, 8.00), (48.0, 8.01), (48.0, 8.02)]
    c = [(48.0, 8.01), (48.0008, 8.01)]
    b = [(48.0, 8.02), (48.0, 8.03), (48.0, 8.04), (48.0, 8.05)]
    d = [(48.0, 8.03), (48.002, 8.035), (48.0, 8.04)]
    return [a, c, b, d]


def test_graph_fallback_is_opt_in():
    with pytest.raises(GapError):
        assemble_with_report(_t_junction_segments())


def test_graph_fallback_walks_t_junction_and_drops_spur_and_longer_variant():
    res = assemble_with_report(_t_junction_segments(), graph_fallback=True)
    assert {(48.0, 8.00), (48.0, 8.05)} == {res.line[0], res.line[-1]}
    assert len(res.line) == 6
    assert res.dropped_count == 2 and res.dropped_m > 0


def test_graph_fallback_walks_a_lollipop_loop():
    # main line a-b-c; at b's interior vertex a stem leads to a ring (not chainable greedily)
    main1 = [(48.0, 8.00), (48.0, 8.01)]
    main2 = [(48.0, 8.01), (48.0, 8.02)]
    stem = [(48.0, 8.01), (48.003, 8.01)]
    ring1 = [(48.003, 8.01), (48.004, 8.012), (48.003, 8.014)]
    ring2 = [(48.003, 8.014), (48.002, 8.012), (48.003, 8.01)]
    res = assemble_with_report([main1, stem, ring1, ring2, main2], graph_fallback=True)
    plain = path_length_km([main1 + main2[1:]])
    stem_km, ring_km = path_length_km([stem]), path_length_km([ring1, ring2])
    assert res.dropped_count == 0
    assert path_length_km([res.line]) == pytest.approx(plain + 2 * stem_km + ring_km, rel=1e-3)


def test_graph_fallback_raises_when_more_than_1km_would_be_dropped():
    a = [(48.0, 8.00), (48.0, 8.05)]
    b = [(48.0, 8.05), (48.0, 8.10)]
    # two parallel variants of a, each ~1.2 km longer; attached at both ends -> dropped
    v1 = [(48.0, 8.01), (48.007, 8.03), (48.0, 8.04)]
    v2 = [(48.0, 8.015), (48.008, 8.03), (48.0, 8.035)]
    with pytest.raises(GapError):
        assemble_with_report([a, b, v1, v2], graph_fallback=True)
