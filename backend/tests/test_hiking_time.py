import pytest

from hikesense.hiking_time import din33466


def test_din_vertical_dominates():
    t = din33466(12, 600, 600)
    assert (t.horizontal_h, t.vertical_h) == (3.0, 3.2)
    assert t.hours == pytest.approx(4.7)


def test_din_horizontal_dominates():
    assert din33466(20, 300, 300).hours == pytest.approx(5.8)


def test_din_rejects_negative():
    with pytest.raises(ValueError):
        din33466(-1, 0, 0)
