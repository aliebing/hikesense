import pytest

from hikeall.errors import GapError, HikeAllError
from hikeall.ingest.assemble import assemble


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
