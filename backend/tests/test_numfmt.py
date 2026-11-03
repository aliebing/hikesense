"""One half-up German number formatter for every number the code shows the model or the user
(plan 3, task 13 fix round 1): float rounding (round(4.35, 1) == 4.3) disagreed with the
grounding check, which rounds the evidence 4,35 half-up to 4,4."""

import pytest

from hikesense.agent import multiday as md
from hikesense.agent.constraints import _num
from hikesense.agent.graph import _de
from hikesense.agent.grounding import Evidence, grounding_check
from hikesense.numfmt import de, round_half_up

HALVES = [(4.35, "4,4"), (2.25, "2,3"), (15.05, "15,1"), (-4.35, "-4,4"), (0.05, "0,1"), (3.0, "3")]


@pytest.mark.parametrize(("x", "text"), HALVES)
def test_de_rounds_half_up(x, text):
    assert de(x) == text


def test_de_decimals_and_integers():
    assert de(1.005, 2) == "1,01"
    assert de(2.5, 0) == "3"
    assert de(12.0, 2) == "12"
    assert round_half_up(2.5) == 3 and round_half_up(3.5) == 4 and round_half_up(-2.5) == -3


@pytest.mark.parametrize("caller", [_de, md._fmt, _num])
@pytest.mark.parametrize(("x", "text"), HALVES)
def test_every_caller_rounds_half_up(caller, x, text):
    assert caller(x) == text


@pytest.mark.parametrize("caller", [_de, md._fmt, _num])
@pytest.mark.parametrize("x", [4.35, 2.25, 15.05, 0.45, 4.3499999, 7.0500004])
def test_shown_numbers_pass_the_grounding_check(caller, x):
    ev = Evidence()
    ev.add(x, "h")
    assert grounding_check(f"Es sind {caller(x)} h.", ev).unsupported == []


def test_too_long_gap_text_is_grounded():
    """The gap „Tagesstrecke zu lang … (X h ohne Pausen)“ formats hours with _fmt."""
    assert md._fmt(4.35) == "4,4"


def test_trail_end_note_rounds_days_half_up():
    days = [
        md.DayPlan(
            day=n, date=None, start_km=0, end_km=0, walk_km=0, access_km=0, length_km=0,
            ascent_m=0, descent_m=0, duration_h=0, start_time=md.time(9), arrival=None,
            stop=None, gap=None, within_band=True,
        )
        for n in (1, 2)
    ]  # fmt: skip
    # 5 km left over 2 days: ~2,5 -> "~3 km" (half-up), not banker's "~2 km"
    (note,) = md._notes(days, 5.0, "Kandern", "Basel")
    assert "bei ~3 km" in note


def test_fmt_english_and_german():
    from hikesense.numfmt import fmt

    assert fmt(11.6, "en") == "11.6"
    assert fmt(1200, "en", 0) == "1,200"
    assert fmt(11.6, "de") == "11,6"
    assert fmt(3.0, "en") == "3"
    assert fmt(4.35, "en") == "4.4"


def test_small_negative_values_never_show_minus_zero():
    from hikesense.numfmt import de, fmt

    assert de(-0.2, 0) == "0" and fmt(-0.2, "de", 0) == "0" and fmt(-0.04, "en", 1) == "0"
    assert fmt(-1.4, "en", 0) == "-1"
