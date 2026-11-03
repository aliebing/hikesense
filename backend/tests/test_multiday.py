import json
from datetime import date, datetime, time, timedelta

import pytest

from hikesense.agent.multiday import (
    NO_RAIN_VARIANT,
    RAIN_NOTE,
    StationOnTrail,
    Stop,
    change_day,
    load_trail_for_multiday,
    plan_multiday,
    rain_variant,
    start_km_for,
)
from hikesense.hiking_time import din33466

FLAT = [[0.0, 500.0], [300.0, 500.0]]


def stop(i: int, along: float, dist: int = 300) -> Stop:
    return Stop(
        lodging_id=i, name=f"Haus {i}", kind="hotel", website=None, along_km=along, dist_m=dist
    )


def every(step: float, until: float, dist: int = 300, first_id: int = 1) -> list[Stop]:
    n = int(until // step)
    return [stop(first_id + k, round((k + 1) * step, 3), dist) for k in range(n)]


def test_days_end_at_lodging_within_1km():
    # Lodgings within 1 km every 3 km, plus far-off (1.5 km) ones exactly at 15/30/45.
    stops = every(3.1, 120) + [stop(900 + k, 15.0 * k, 1500) for k in (1, 2, 3)]
    p = plan_multiday(stops, FLAT, trail_len_km=120, start_km=0, days=3)
    assert len(p.days) == 3
    km = 0.0
    for d in p.days:
        assert d.stop is not None and d.stop.dist_m <= 1000
        assert d.start_km == km and d.end_km == d.stop.along_km
        assert d.access_km == 0 and d.within_band and d.gap is None
        assert 12 <= d.length_km <= 18
        km = d.end_km
    assert p.notes == []


def test_uses_2km_lodging_only_if_none_in_band_and_adds_access_twice():
    stops = [stop(1, 5.0), stop(2, 15.0, 1400), stop(3, 29.0), stop(4, 40.0)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=2)
    d1, d2 = p.days
    assert d1.stop.lodging_id == 2
    assert d1.walk_km == 15.0 and d1.access_km == 1.4 and d1.length_km == 16.4
    assert d2.start_km == 15.0 and d2.stop.lodging_id == 3
    assert d2.walk_km == 14.0 and d2.access_km == 1.4 and d2.length_km == 15.4
    assert d1.within_band and d2.within_band
    # the access walk is the straight-line distance, without its elevation: said so, not hidden
    assert (
        "Unterkunft Haus 2 liegt 1,4 km Luftlinie abseits – Zuweg als Luftlinie eingerechnet, "
        "ohne Höhenmeter des Zuwegs"
    ) in p.notes


def test_day_line_names_the_access_walk_as_straight_line():
    from hikesense.agent.graph import _day_line

    stops = [stop(1, 5.0), stop(2, 15.0, 1400), stop(3, 29.0), stop(4, 40.0)]
    d1 = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=2).days[0]
    line = _day_line(d1, None, False, None)
    assert "davon Zuweg 1,4 km Luftlinie" in line
    assert "Zuweg als Luftlinie eingerechnet, ohne Höhenmeter des Zuwegs" in line
    assert "(Zuweg eingerechnet)" not in line


def test_2km_lodging_ignored_when_1km_one_in_band():
    stops = [stop(1, 13.0), stop(2, 15.0, 1400), stop(3, 40.0)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=1)
    assert p.days[0].stop.lodging_id == 1 and p.days[0].access_km == 0


def test_gap_named_when_no_lodging():
    stops = [stop(1, 5.0), stop(2, 24.0), stop(3, 40.0)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=1)
    d = p.days[0]
    assert d.stop.lodging_id == 2 and d.stop.dist_m <= 1000
    assert not d.within_band
    assert d.gap == "Keine Unterkunft ≤ 1 km zwischen km 12 und km 18"


def test_tie_prefers_smaller_dist_then_smaller_id():
    stops = [stop(7, 15.0, 600), stop(5, 15.0, 200), stop(3, 15.0, 200), stop(9, 40.0)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=1)
    assert p.days[0].stop.lodging_id == 3


def test_plan_stops_at_trail_end():
    stops = every(7.0, 300)
    profile = FLAT
    p = plan_multiday(stops, profile, trail_len_km=300, start_km=272, days=5)
    assert len(p.days) == 2 and p.days[-1].stop is None and "bleiben 28 km" in p.notes[0]
    assert p.days[-1].end_km == 300
    assert p.notes[0] == "Ab km 272 bleiben 28 km bis zum Wegende – 2 Tag(e) bei ~14 km"
    named = plan_multiday(stops, profile, 300, 272, 5, start_name="Kandern", end_name="Basel")
    assert named.notes[0] == "Ab Kandern bleiben 28 km bis Basel – 2 Tag(e) bei ~14 km"


def test_change_day_keeps_earlier_days():
    stops = every(2.5, 200)
    p = plan_multiday(
        stops, FLAT, trail_len_km=200, start_km=0, days=4, start_date=date(2027, 5, 1)
    )
    before = [d.model_dump_json() for d in p.days]
    old = p.days[1]

    s = change_day(p, 2, "shorter", stops, FLAT, 200)
    assert len(s.days) == 4
    assert [d.model_dump_json() for d in s.days[:1]] == before[:1]
    assert s.days[1].length_km <= old.length_km - 2
    assert s.days[1].length_km == 12.5  # the next earlier lodging that saves >= 2 km
    assert s.days[2].start_km == s.days[1].end_km
    assert s.days[3].date == date(2027, 5, 4)

    longer = change_day(p, 3, "longer", stops, FLAT, 200)
    assert [d.model_dump_json() for d in longer.days[:2]] == before[:2]
    assert longer.days[2].length_km >= p.days[2].length_km + 2
    assert len(longer.days) == 4


def test_change_day_runs_into_trail_end():
    stops = every(2.5, 47)
    p = plan_multiday(stops, FLAT, trail_len_km=48, start_km=0, days=3)
    assert [d.end_km for d in p.days] == [15.0, 30.0, 45.0]
    q = change_day(p, 2, "longer", stops, FLAT, 48)
    assert q.days[0].model_dump_json() == p.days[0].model_dump_json()
    assert q.days[1].end_km == 32.5
    assert len(q.days) == 3
    assert q.days[-1].stop is None and q.days[-1].end_km == 48
    assert any("bleiben 48 km" in n for n in q.notes)


def test_arrival_is_start_plus_din_time():
    profile = [[0.0, 0.0], [10.0, 500.0], [20.0, 500.0], [30.0, 0.0]]
    stops = [stop(1, 15.0), stop(2, 30.0)]
    p = plan_multiday(stops, profile, 30, 0, 1, start_date=date(2027, 6, 1), start_time=time(8, 30))
    d = p.days[0]
    assert (d.ascent_m, d.descent_m) == (500, 0)
    hours = din33466(15.0, 500, 0).hours
    assert d.duration_h == hours
    expected = datetime.combine(d.date, time(8, 30)) + timedelta(minutes=round(hours * 60))
    assert d.start_time == time(8, 30) and d.arrival == expected.time()
    assert d.date == date(2027, 6, 1)
    # Interpolated section: 5..25 km climbs 250 m and descends 250 m.
    p2 = plan_multiday([stop(3, 25.0)], profile, 30, 5, 1, target_km=20)
    assert (p2.days[0].ascent_m, p2.days[0].descent_m) == (250, 250)


def test_plan_is_json_serialisable():
    p = plan_multiday(every(3.0, 60), FLAT, 60, 0, 2, start_date=date(2027, 5, 1))
    data = json.loads(p.model_dump_json())
    assert data["days"][0]["date"] == "2027-05-01"
    assert data["days"][0]["start_time"] == "09:00:00"


def test_rain_variant_ends_at_station_or_none():
    profile = [[0.0, 100.0], [15.0, 100.0], [27.0, 400.0], [40.0, 400.0]]
    p = plan_multiday([stop(1, 15.0), stop(2, 30.0)], profile, 40, 0, 2)
    day2 = p.days[1]
    stations = [
        StationOnTrail(poi_id=1, name="Zu früh", along_km=16.0, dist_m=50),
        StationOnTrail(poi_id=2, name="Mitte", along_km=22.0, dist_m=50),
        StationOnTrail(poi_id=3, name="Spät", along_km=27.0, dist_m=0),
        StationOnTrail(poi_id=4, name="Danach", along_km=31.0, dist_m=50),
    ]
    rv = rain_variant(day2, stations, profile)
    assert rv.station_name == "Spät"
    assert rv.walk_km == 12.0 and rv.ascent_m == 300
    assert rv.duration_h == din33466(12.0, 300, 0).hours
    assert rv.note == RAIN_NOTE
    assert rain_variant(day2, stations[:1] + stations[3:], profile) is None
    assert NO_RAIN_VARIANT == "Keine Haltestelle am Weg – Regenvariante nicht möglich"


def test_access_carry_is_exact_for_1450m_lodging():
    stops = [stop(1, 5.0), stop(2, 10.0), stop(3, 15.0, 1450), stop(4, 29.0), stop(5, 31.05)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=2)
    assert [d.stop.lodging_id for d in p.days] == [3, 4]
    assert p.days[0].access_km == 1.45 and p.days[1].access_km == 1.45

    shorter = change_day(p, 1, "shorter", stops, FLAT, 100)
    assert shorter.days[0].stop.lodging_id == 2
    assert shorter.days[0].access_km == 0 and shorter.days[0].length_km == 10.0

    longer = change_day(p, 2, "longer", stops, FLAT, 100)
    assert longer.days[0].model_dump_json() == p.days[0].model_dump_json()
    assert longer.days[1].stop.lodging_id == 5
    assert longer.days[1].access_km == 1.45 and longer.days[1].length_km == 17.5

    station = StationOnTrail(poi_id=1, name="Halt", along_km=22.04, dist_m=0)
    rv = rain_variant(p.days[1], [station], FLAT)
    assert rv.walk_km == 8.5  # 7.04 km on the trail + 1.45 km access back to it


def test_no_impossible_day_when_lodgings_run_out():
    p = plan_multiday([stop(1, 3.0, 1500)], FLAT, trail_len_km=200, start_km=0, days=3)
    assert len(p.days) == 1
    d = p.days[0]
    assert d.stop.lodging_id == 1 and not d.within_band and d.gap
    assert d.access_km == 1.5 and d.length_km == 4.5
    assert all(x.length_km < 30 for x in p.days)
    assert "Keine Unterkunft ≤ 2 km zwischen km 13,5 und km 19,5 – der Plan endet hier." in p.notes


def test_arrival_none_when_day_crosses_midnight():
    p = plan_multiday([stop(1, 100.0)], FLAT, trail_len_km=200, start_km=0, days=1)
    d = p.days[0]
    assert d.duration_h == 25.0 and d.arrival is None
    assert "Tagesstrecke zu lang für einen Tag (25 h ohne Pausen)" in d.gap
    assert "Keine Unterkunft ≤ 1 km zwischen km 12 und km 18" in d.gap


@pytest.mark.db
def test_real_westweg_hausach_3_days(conn):
    stops, stations, profile, trail_len, name, source_ids = load_trail_for_multiday(
        conn, "westweg-west"
    )
    assert name.startswith("Westweg") and trail_len > 250 and "osm" in source_ids
    assert any(s.name == "Hausach" for s in stations)
    start = start_km_for(conn, "westweg-west", 48.2836305, 8.174972)  # Hausach
    assert start is not None and 125 < start < 140
    assert start_km_for(conn, "westweg-west", 48.0, 9.5) is None  # far off the trail
    p = plan_multiday(
        stops,
        profile,
        trail_len,
        start,
        days=3,
        trail_id="westweg-west",
        trail_name=name,
        source_ids=source_ids,
    )
    assert len(p.days) == 3
    for d in p.days:
        assert d.stop is not None
        assert d.stop.dist_m <= 1000 or any(d.stop.name in n for n in p.notes)
        assert d.within_band or d.gap


# --- English texts (Zweisprachig Teil B, Task 5) ---------------------------------------------


def test_english_plan_notes_gaps_and_numbers():
    stops = [stop(1, 5.0), stop(2, 24.0), stop(3, 40.0)]
    p = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=1, lang="en")
    assert p.lang == "en"
    assert p.days[0].gap == "No accommodation within 1 km between km 12 and km 18"
    far = plan_multiday(
        [stop(1, 5.0), stop(2, 15.0, 1400), stop(3, 29.0), stop(4, 40.0)],
        FLAT, trail_len_km=100, start_km=0, days=2, lang="en",
    )  # fmt: skip
    assert (
        "Accommodation Haus 2 lies 1.4 km off the trail as the crow flies – "
        "access path counted as the crow flies, without its ascent"
    ) in far.notes
    end = plan_multiday([stop(1, 10.0)], FLAT, trail_len_km=20, start_km=0, days=2, lang="en")
    assert end.notes == ["From km 0 there are 20 km to the end of the trail – 2 day(s) at ~10 km"]
    assert plan_multiday([stop(1, 10.0)], FLAT, 20, 0, 2).notes == [
        "Ab km 0 bleiben 20 km bis zum Wegende – 2 Tag(e) bei ~10 km"
    ]


def test_english_too_long_day_and_dead_end():
    p = plan_multiday([stop(1, 100.0)], FLAT, trail_len_km=200, start_km=0, days=1, lang="en")
    assert "Daily distance too long for one day (25 h without breaks)" in p.days[0].gap
    assert "No accommodation within 1 km between km 12 and km 18" in p.days[0].gap
    stops = [stop(1, 3.0, 1500)]
    dead = plan_multiday(stops, FLAT, trail_len_km=100, start_km=0, days=3, lang="en")
    assert any(n.endswith("– the plan ends here.") for n in dead.notes)
    assert not any("Keine" in n or "Plan endet" in n for n in dead.notes)


def test_english_change_day_unchanged_message_uses_the_plans_language():
    p = plan_multiday([stop(1, 15.0)], FLAT, trail_len_km=15, start_km=0, days=1, lang="en")
    out = change_day(p, 1, "shorter", [stop(1, 15.0)], FLAT, 15)
    assert out.notes[-1] == (
        "Day 1 cannot be planned shorter – no accommodation that changes the distance "
        "by at least 2 km"
    )
    de = plan_multiday([stop(1, 15.0)], FLAT, trail_len_km=15, start_km=0, days=1)
    assert change_day(de, 1, "longer", [stop(1, 15.0)], FLAT, 15).notes[-1].startswith(
        "Tag 1 lässt sich nicht länger planen"
    )
    # a plan stored before `lang` existed has none: it is German
    old = json.loads(de.model_dump_json())
    old.pop("lang")
    from hikesense.agent.multiday import MultidayPlan

    assert MultidayPlan.model_validate(old).lang == "de"


def test_english_rain_variant_texts():
    profile = [[0.0, 100.0], [15.0, 100.0], [27.0, 400.0], [40.0, 400.0]]
    p = plan_multiday([stop(1, 15.0), stop(2, 30.0)], profile, 40, 0, 2)
    st = [StationOnTrail(poi_id=3, name=None, along_km=27.0, dist_m=0)]
    rv = rain_variant(p.days[1], st, profile, "en")
    assert rv.station_name == "Unnamed stop"
    assert rv.note == (
        "Continue by bus/train to the accommodation – please check the timetable yourself."
    )
    assert rain_variant(p.days[1], st, profile).station_name == "Haltestelle ohne Namen"
