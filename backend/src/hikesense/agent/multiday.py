"""Multi-day planning along a long-distance trail: pure, deterministic code.

The code decides days, lodgings, distances and times; the model only words the
result. Rules (spec §8): a day ends at a lodging <= 1000 m from the trail; only
if none lies in the +-20 % band around the daily target, a lodging <= 2000 m is
used and its access path counted on the arrival day and the next day; if there
is none either, the nearest-best lodging <= 1000 m is taken and the gap named.
Arrival = start + DIN 33466 time, without breaks. No days are invented beyond
the trail end.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Literal

import psycopg
from pydantic import BaseModel

from hikesense.geo import METRIC_SRID
from hikesense.hiking_time import din33466
from hikesense.numfmt import Lang, fmt, round_half_up

NEAR_M = 1000
FAR_M = 2000
BAND = 0.2
MIN_CHANGE_KM = 2.0
RAIN_MIN_KM = 3.0
OFF_TRAIL_KM = 2.0  # start_km_for: farther away from the line counts as "not on the trail"

# Fixed sentences of the plan in both reply languages. The German constants below keep their old
# names (RAIN_NOTE, NO_RAIN_VARIANT, ACCESS_STRAIGHT); the English ones are reached via the helpers.
_T: dict[Lang, dict[str, str]] = {
    "de": {
        "rain_note": "Weiter mit Bus/Bahn zur Unterkunft – Fahrplan bitte selbst prüfen.",
        "no_rain": "Keine Haltestelle am Weg – Regenvariante nicht möglich",
        "access": "Zuweg als Luftlinie eingerechnet, ohne Höhenmeter des Zuwegs",
        "too_long": "Tagesstrecke zu lang für einen Tag ({h} h ohne Pausen)",
        "remaining": (
            "Ab {start} bleiben {rest} km bis {end} – {n} Tag(e) bei ~{avg} km"
        ),
        "start_km": "km {km}",
        "trail_end": "zum Wegende",
        "lodging_off": "Unterkunft {name} liegt {km} km Luftlinie abseits – {access}",
        "unnamed_lodging": "ohne Namen",
        "gap": "Keine Unterkunft ≤ {within} km zwischen km {a} und km {b}",
        "dead_end": "{gap} – der Plan endet hier.",
        "cannot_change": (
            "Tag {day} lässt sich nicht {word} planen – keine Unterkunft, "
            "die die Strecke um mindestens {km} km ändert"
        ),
        "shorter": "kürzer",
        "longer": "länger",
        "unnamed_stop": "Haltestelle ohne Namen",
    },
    "en": {
        "rain_note": "Continue by bus/train to the accommodation – please check the timetable yourself.",
        "no_rain": "No stop on the trail – rain variant not possible",
        "access": "access path counted as the crow flies, without its ascent",
        "too_long": "Daily distance too long for one day ({h} h without breaks)",
        "remaining": (
            "From {start} there are {rest} km to {end} – {n} day(s) at ~{avg} km"
        ),
        "start_km": "km {km}",
        "trail_end": "the end of the trail",
        "lodging_off": "Accommodation {name} lies {km} km off the trail as the crow flies – {access}",
        "unnamed_lodging": "(unnamed)",
        "gap": "No accommodation within {within} km between km {a} and km {b}",
        "dead_end": "{gap} – the plan ends here.",
        "cannot_change": (
            "Day {day} cannot be planned {word} – no accommodation "
            "that changes the distance by at least {km} km"
        ),
        "shorter": "shorter",
        "longer": "longer",
        "unnamed_stop": "Unnamed stop",
    },
}

RAIN_NOTE = _T["de"]["rain_note"]
NO_RAIN_VARIANT = _T["de"]["no_rain"]


def rain_note(lang: Lang = "de") -> str:
    return _T[lang]["rain_note"]


def no_rain_variant(lang: Lang = "de") -> str:
    return _T[lang]["no_rain"]


def access_straight(lang: Lang = "de") -> str:
    return _T[lang]["access"]

Profile = list[list[float]]  # [[km, elevation_m], ...]

_END = -2  # candidate marker: the trail end (no lodging)
_START = -1  # state marker: the plan's start point


class Stop(BaseModel):
    lodging_id: int
    name: str | None
    kind: str | None
    website: str | None
    along_km: float
    dist_m: int


class StationOnTrail(BaseModel):
    poi_id: int
    name: str | None
    along_km: float
    dist_m: int


class DayPlan(BaseModel):
    day: int
    date: date | None
    start_km: float
    end_km: float
    walk_km: float  # on the trail
    access_km: float  # access paths to/from lodgings > 1000 m off the trail (metre precision)
    length_km: float  # walk + access
    ascent_m: int
    descent_m: int
    duration_h: float  # DIN 33466, without breaks
    start_time: time
    arrival: time | None  # None: the day would end after midnight (see gap)
    stop: Stop | None  # None = day ends at the trail end
    gap: str | None
    within_band: bool


class MultidayPlan(BaseModel):
    trail_id: str
    trail_name: str
    target_km: float
    days: list[DayPlan]
    notes: list[str]
    source_ids: list[str]
    lang: Lang = "de"  # the language of notes and gaps: a stored plan keeps it (spec decision 10)


class RainVariant(BaseModel):
    station_name: str
    walk_km: float
    ascent_m: int
    duration_h: float
    note: str = RAIN_NOTE  # rain_variant() writes it in the reply language


# The access walk is counted as the straight-line distance, without its elevation.
ACCESS_STRAIGHT = _T["de"]["access"]


# --- helpers -----------------------------------------------------------------


def _fmt(x: float, lang: Lang = "de") -> str:
    """Number in the reply language: one decimal, without a trailing ',0' (half-up, see numfmt)."""
    return fmt(x, lang, 1)


def _access(stop: Stop | None) -> float:
    """Access path one way (km) for a lodging farther than 1000 m from the trail: the straight-line
    distance (no path routing, no elevation) — the notes and the day view say so."""
    return stop.dist_m / 1000 if stop is not None and stop.dist_m > NEAR_M else 0.0


def _elevation_at(profile: Profile, km: float) -> float:
    if km <= profile[0][0]:
        return profile[0][1]
    for (k0, e0), (k1, e1) in itertools.pairwise(profile):
        if km <= k1:
            return e0 if k1 == k0 else e0 + (e1 - e0) * (km - k0) / (k1 - k0)
    return profile[-1][1]


def _up_down(profile: Profile, a: float, b: float) -> tuple[int, int]:
    """Ascent/descent between km a and b, profile linearly interpolated."""
    pts = [_elevation_at(profile, a)]
    pts += [e for k, e in profile if a < k < b]
    pts.append(_elevation_at(profile, b))
    up = sum(max(0.0, y - x) for x, y in itertools.pairwise(pts))
    down = sum(max(0.0, x - y) for x, y in itertools.pairwise(pts))
    return round(up), round(down)


def _make_day(
    n: int,
    start_date: date | None,
    start_km: float,
    end_km: float,
    carry_in: float,
    stop: Stop | None,
    target_km: float,
    gap: str | None,
    profile: Profile,
    start_time: time,
    lang: Lang = "de",
) -> DayPlan:
    walk = end_km - start_km
    access = carry_in + _access(stop)
    length = walk + access
    ascent, descent = _up_down(profile, start_km, end_km)
    hours = din33466(round(length, 1), ascent, descent).hours
    day_date = start_date + timedelta(days=n - 1) if start_date else None
    t0 = datetime.combine(day_date or date(2000, 1, 1), start_time)
    t1 = t0 + timedelta(minutes=round(hours * 60))
    arrival: time | None = t1.time()
    if t1.date() != t0.date():  # never show an arrival past midnight
        arrival = None
        too_long = _T[lang]["too_long"].format(h=_fmt(hours, lang))
        gap = f"{gap}; {too_long}" if gap else too_long
    lo, hi = target_km * (1 - BAND), target_km * (1 + BAND)
    return DayPlan(
        day=n,
        date=day_date,
        start_km=round(start_km, 3),
        end_km=round(end_km, 3),
        walk_km=round(walk, 1),
        access_km=round(access, 3),
        length_km=round(length, 1),
        ascent_m=ascent,
        descent_m=descent,
        duration_h=hours,
        start_time=start_time,
        arrival=arrival,
        stop=stop,
        gap=gap,
        within_band=lo - 1e-9 <= length <= hi + 1e-9,
    )


def _notes(
    days: list[DayPlan],
    trail_len_km: float,
    start_name: str | None,
    end_name: str | None,
    dead_end: str | None = None,
    lang: Lang = "de",
) -> list[str]:
    t = _T[lang]
    notes: list[str] = []
    if days and days[-1].stop is None:
        start = days[0].start_km
        rest = trail_len_km - start
        n = len(days)
        notes.append(
            t["remaining"].format(
                start=start_name or t["start_km"].format(km=_fmt(start, lang)),
                rest=_fmt(rest, lang),
                end=end_name or t["trail_end"],
                n=n,
                avg=fmt(round_half_up(rest / n), lang, 0),
            )
        )
    for d in days:
        if d.stop is not None and d.stop.dist_m > NEAR_M:
            notes.append(
                t["lodging_off"].format(
                    name=d.stop.name or t["unnamed_lodging"],
                    km=_fmt(d.stop.dist_m / 1000, lang),
                    access=t["access"],
                )
            )
    if dead_end:
        notes.append(dead_end)
    return notes


class _Planner:
    """Dynamic programme over (position, days left); positions = start or a lodging."""

    def __init__(
        self,
        stops: list[Stop],
        trail_len_km: float,
        target_km: float,
        start_km: float,
        start_carry: float,
        lang: Lang = "de",
    ) -> None:
        self.lang = lang
        self.stops = sorted(stops, key=lambda s: (s.along_km, s.dist_m, s.lodging_id))
        self.trail_len = trail_len_km
        self.target = target_km
        self.lo = target_km * (1 - BAND)
        self.hi = target_km * (1 + BAND)
        self.start_km = start_km
        self.start_carry = start_carry
        self.best = lru_cache(maxsize=None)(self._best)

    def pos(self, state: int) -> tuple[float, float]:
        """(km on the trail, access km carried into the next day)."""
        if state == _START:
            return self.start_km, self.start_carry
        s = self.stops[state]
        return s.along_km, _access(s)

    def length(self, state: int, cand: int) -> float:
        km, carry = self.pos(state)
        if cand == _END:
            return self.trail_len - km + carry
        s = self.stops[cand]
        return s.along_km - km + carry + _access(s)

    def candidates(self, state: int) -> tuple[list[int], str | None]:
        """Candidate day ends from a state, and the gap text if none is in the band."""
        km, _ = self.pos(state)
        ahead = [i for i, s in enumerate(self.stops) if s.along_km > km + 1e-9]

        def in_band(i: int) -> bool:
            return self.lo - 1e-9 <= self.length(state, i) <= self.hi + 1e-9

        end_ok = self.length(state, _END) <= self.hi + 1e-9
        ends = [_END] if end_ok else []
        near = [i for i in ahead if self.stops[i].dist_m <= NEAR_M]
        tier1 = [i for i in near if in_band(i)]
        if tier1:
            return tier1 + ends, None
        tier2 = [i for i in ahead if self.stops[i].dist_m <= FAR_M and in_band(i)]
        if tier2:
            return tier2 + ends, None
        if end_ok:
            return ends, None
        # Last resort, out of the band: nearest-to-target lodging <= 1000 m, else <= 2000 m.
        # No lodging <= 2000 m left and the trail end out of reach: no candidate, plan ends.
        far = [i for i in ahead if self.stops[i].dist_m <= FAR_M]
        return near or far, self.gap_text(state, 1)

    def gap_text(self, state: int, within_km: int) -> str:
        km, carry = self.pos(state)
        return _T[self.lang]["gap"].format(
            within=within_km,
            a=_fmt(km + self.lo - carry, self.lang),
            b=_fmt(km + self.hi - carry, self.lang),
        )

    def key(self, cand: int) -> tuple[int, int]:
        if cand == _END:
            return (0, -1)
        s = self.stops[cand]
        return (s.dist_m, s.lodging_id)

    def _best(self, state: int, left: int) -> tuple[int, float, tuple, tuple[int, ...]]:
        """Best (days lost to a dead end, sum of squared deviations, tie keys, path).

        A dead end (no lodging <= 2000 m ahead, trail end out of reach) loses the
        remaining days; plans that lose fewer days always win.
        """
        cands, _ = self.candidates(state)
        best: tuple[int, float, tuple, tuple[int, ...]] = (left, 0.0, (), ())
        for c in cands:
            cost = (self.length(state, c) - self.target) ** 2
            if c == _END or left == 1:
                total = (0, round(cost, 6), (self.key(c),), (c,))
            else:
                lost, sub_cost, sub_keys, sub_path = self.best(c, left - 1)
                total = (lost, round(cost + sub_cost, 6), (self.key(c), *sub_keys), (c, *sub_path))
            if not best[3] or total[:3] < best[:3]:
                best = total
        return best

    def days(
        self,
        state: int,
        left: int,
        first_day: int,
        start_date: date | None,
        start_time: time,
        profile: Profile,
    ) -> tuple[list[DayPlan], str | None]:
        """Day plans for the best path, plus a note if the plan ends at a dead end."""
        out: list[DayPlan] = []
        lost, _, _, path = self.best(state, left)
        for n, c in enumerate(path, start=first_day):
            km, carry = self.pos(state)
            _, gap = self.candidates(state)
            stop = None if c == _END else self.stops[c]
            end_km = self.trail_len if stop is None else stop.along_km
            out.append(
                _make_day(
                    n, start_date, km, end_km, carry, stop, self.target, gap, profile, start_time,
                    self.lang,
                )
            )
            state = c
        dead_end = (
            _T[self.lang]["dead_end"].format(gap=self.gap_text(state, 2)) if lost else None
        )
        return out, dead_end


# --- public API --------------------------------------------------------------


def plan_multiday(
    stops: list[Stop],
    profile: Profile,
    trail_len_km: float,
    start_km: float,
    days: int,
    target_km: float = 15.0,
    start_date: date | None = None,
    start_time: time = time(9),
    *,
    trail_id: str = "",
    trail_name: str = "",
    source_ids: list[str] | None = None,
    start_name: str | None = None,
    end_name: str | None = None,
    lang: Lang = "de",
) -> MultidayPlan:
    if days < 1:
        raise ValueError("days must be >= 1")
    if target_km <= 0:
        raise ValueError("target_km must be > 0")
    if not 0 <= start_km < trail_len_km:
        raise ValueError("start_km must lie on the trail")
    planner = _Planner(stops, trail_len_km, target_km, start_km, 0.0, lang)
    day_plans, dead_end = planner.days(_START, days, 1, start_date, start_time, profile)
    return MultidayPlan(
        trail_id=trail_id,
        trail_name=trail_name,
        target_km=target_km,
        days=day_plans,
        notes=_notes(day_plans, trail_len_km, start_name, end_name, dead_end, lang),
        source_ids=list(source_ids or []),
        lang=lang,
    )


def change_day(
    plan: MultidayPlan,
    day: int,
    change: Literal["shorter", "longer"],
    stops: list[Stop],
    profile: Profile,
    trail_len_km: float,
    *,
    start_name: str | None = None,
    end_name: str | None = None,
) -> MultidayPlan:
    """Make day `day` end at the next earlier/later lodging that changes it by >= 2 km.

    Days before `day` are kept as they are (same objects); the following days are
    planned again with the same target, keeping the number of days unless the
    trail ends first. If no lodging qualifies, the plan is returned unchanged with
    a note saying so. Texts are written in the language of the stored plan (`plan.lang`).
    """
    lang = plan.lang
    if not 1 <= day <= len(plan.days):
        raise ValueError("day out of range")
    old = plan.days[day - 1]
    carry_in = _access(plan.days[day - 2].stop) if day > 1 else 0.0
    # Planner whose start state is this day's start; it scores candidates for us.
    planner = _Planner(stops, trail_len_km, plan.target_km, old.start_km, carry_in, lang)
    old_len = old.end_km - old.start_km + old.access_km
    near: list[tuple[float, tuple[int, int], int]] = []
    far: list[tuple[float, tuple[int, int], int]] = []
    for i, s in enumerate(planner.stops):
        if s.along_km <= old.start_km + 1e-9:
            continue
        ln = planner.length(_START, i)
        if change == "shorter" and ln > old_len - MIN_CHANGE_KM + 1e-9:
            continue
        if change == "longer" and ln < old_len + MIN_CHANGE_KM - 1e-9:
            continue
        (near if s.dist_m <= NEAR_M else far if s.dist_m <= FAR_M else []).append(
            (ln, planner.key(i), i)
        )
    end_len = planner.length(_START, _END)
    if change == "longer" and old.stop is not None and end_len >= old_len + MIN_CHANGE_KM - 1e-9:
        near.append((end_len, planner.key(_END), _END))
    pool = near or far
    if not pool:
        msg = _T[lang]["cannot_change"].format(
            day=day, word=_T[lang][change], km=_fmt(MIN_CHANGE_KM, lang)
        )
        return plan.model_copy(update={"notes": [*plan.notes, msg]})
    if change == "shorter":  # closest below: the longest remaining day
        _, _, pick = min(pool, key=lambda t: (-t[0], t[1]))
    else:  # closest above: the shortest longer day
        _, _, pick = min(pool, key=lambda t: (t[0], t[1]))

    first_date = plan.days[0].date
    stop = None if pick == _END else planner.stops[pick]
    end_km = trail_len_km if stop is None else stop.along_km
    changed = _make_day(
        day,
        first_date,
        old.start_km,
        end_km,
        carry_in,
        stop,
        plan.target_km,
        None,
        profile,
        old.start_time,
        lang,
    )
    days = [*plan.days[: day - 1], changed]
    left = len(plan.days) - day
    dead_end = None
    if stop is not None and left > 0:
        more, dead_end = planner.days(pick, left, day + 1, first_date, old.start_time, profile)
        days += more
    notes = _notes(days, trail_len_km, start_name, end_name, dead_end, lang)
    return plan.model_copy(update={"days": days, "notes": notes})


def rain_variant(
    day_plan: DayPlan, stations: list[StationOnTrail], profile: Profile, lang: Lang = "de"
) -> RainVariant | None:
    """Shorter day ending at the last station on the trail >= 3 km after the day's start.

    None means NO_RAIN_VARIANT ("Keine Haltestelle am Weg – Regenvariante nicht möglich").
    """
    # access_km has metre precision, so this recovers the morning access walk exactly.
    carry_in = round(day_plan.access_km - _access(day_plan.stop), 3)
    lo = day_plan.start_km + RAIN_MIN_KM
    hits = [s for s in stations if lo - 1e-9 <= s.along_km < day_plan.end_km - 1e-9]
    if not hits:
        return None
    st = max(hits, key=lambda s: (s.along_km, -s.dist_m, -s.poi_id))
    walk = st.along_km - day_plan.start_km + carry_in + st.dist_m / 1000
    ascent, descent = _up_down(profile, day_plan.start_km, st.along_km)
    walk = round(walk, 1)
    return RainVariant(
        station_name=st.name or _T[lang]["unnamed_stop"],
        walk_km=walk,
        ascent_m=ascent,
        duration_h=din33466(walk, ascent, descent).hours,
        note=rain_note(lang),
    )


# --- DB loaders --------------------------------------------------------------


def load_trail_for_multiday(
    conn: psycopg.Connection, trail_id: str
) -> tuple[list[Stop], list[StationOnTrail], Profile, float, str, list[str]]:
    """Lodgings (<= 2000 m), stations, profile, length, name and source ids of a trail."""
    row = conn.execute(
        "select name, length_km, profile, source_id from trails where id = %s", (trail_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"unknown trail {trail_id!r}")
    name, length_km, profile, trail_source = row
    rows = conn.execute(
        """
        select l.id, l.name, l.kind, l.website, tl.along_km, tl.dist_m, l.source_id
        from trail_lodgings tl join lodgings l on l.id = tl.lodging_id
        where tl.trail_id = %s and tl.along_km is not null and tl.dist_m <= %s
        order by tl.along_km, tl.dist_m, l.id
        """,
        (trail_id, FAR_M),
    ).fetchall()
    stops = [
        Stop(lodging_id=r[0], name=r[1], kind=r[2], website=r[3], along_km=float(r[4]), dist_m=r[5])
        for r in rows
    ]
    srows = conn.execute(
        """
        select p.id, p.name, tp.along_km, tp.dist_m, p.source_id
        from trail_pois tp join pois p on p.id = tp.poi_id
        where tp.trail_id = %s and p.kind = 'station' and tp.along_km is not null
        order by tp.along_km
        """,
        (trail_id,),
    ).fetchall()
    stations = [
        StationOnTrail(poi_id=r[0], name=r[1], along_km=float(r[2]), dist_m=r[3]) for r in srows
    ]
    sources = {trail_source} | {r[6] for r in rows} | {r[4] for r in srows}
    return (
        stops,
        stations,
        [[float(k), float(e)] for k, e in profile or []],
        float(length_km),
        name,
        sorted(s for s in sources if s),
    )


def start_km_for(conn: psycopg.Connection, trail_id: str, lat: float, lon: float) -> float | None:
    """Foot of the perpendicular on the trail line (km); None if > 2 km from the trail."""
    row = conn.execute(
        f"""
        with p as (select st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326) as g)
        select st_linelocatepoint(st_transform(t.geom, {METRIC_SRID}),
                                  st_transform(p.g, {METRIC_SRID})) * t.length_km,
               st_distance(t.geom::geography, p.g::geography)
        from trails t, p where t.id = %(id)s and t.geom is not null
        """,
        {"lat": lat, "lon": lon, "id": trail_id},
    ).fetchone()
    if row is None or row[1] > OFF_TRAIL_KM * 1000:
        return None
    return round(float(row[0]), 3)
