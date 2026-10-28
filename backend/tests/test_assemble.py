import pytest

from hikeall.errors import GapError, HikeAllError
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
