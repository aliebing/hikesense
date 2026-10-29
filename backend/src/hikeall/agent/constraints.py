"""Deterministic constraint check, honest fallback and preference score (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass, field

from hikeall.agent.request import Constraint, HikeRequest, Preference
from hikeall.hiking_time import din33466

MAX_MATCHES = 5
_LABEL = {
    "length_km": "Länge",
    "ascent_m": "Höhenmeter",
    "duration_h": "Dauer",
    "radius_km": "Entfernung",
    "roundtrip": "Rundweg",
}
_UNIT = {"length_km": "km", "ascent_m": "Hm", "duration_h": "h", "radius_km": "km"}


@dataclass
class Candidate:
    trail_id: str
    name: str
    length_km: float | None
    ascent_m: int | None
    descent_m: int | None
    roundtrip: bool | None
    distance_km: float
    tags: set[str] = field(default_factory=set)


@dataclass
class ConstraintResult:
    kind: str
    ok: bool | None
    actual: float | bool | None
    bound: str
    deviation_rel: float
    bound_value: float | None = None


@dataclass
class PreferenceMatch:
    score: float
    met: list[str]
    missing: list[str]
    avoided_hit: list[str]


@dataclass
class Scored:
    candidate: Candidate
    results: list[ConstraintResult]
    preference: PreferenceMatch
    duration_h: float | None
    violated: ConstraintResult | None = None


@dataclass
class Selection:
    matches: list[Scored]
    fallbacks: list[Scored]
    reason: str | None
    contradiction: str | None


def _num(x: float, decimals: int = 1) -> str:
    s = f"{round(x, decimals):.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").removesuffix(".")
    return s.replace(".", ",")


def _num_distinct(actual: float, bound: float | None) -> str:
    """Format with as many decimals as needed so a violation never looks equal to its bound."""
    for decimals in (1, 2, 3, 4):
        text = _num(actual, decimals)
        if bound is None or text != _num(bound, decimals):
            return text
    return _num(actual, 4)


def duration_h(c: Candidate, activity: str, pace: float | None) -> float | None:
    if c.length_km is None:
        return None
    if activity == "run":
        return None if pace is None or pace <= 0 else c.length_km * pace / 60
    if c.ascent_m is None or c.descent_m is None:
        return None
    return din33466(c.length_km, c.ascent_m, c.descent_m).hours


def _actual(c: Candidate, kind: str, activity: str, pace: float | None) -> float | bool | None:
    if kind == "roundtrip":
        return c.roundtrip
    if kind == "length_km":
        return c.length_km
    if kind == "ascent_m":
        return c.ascent_m
    if kind == "radius_km":
        return c.distance_km
    return duration_h(c, activity, pace)


def _rel(actual: float, bound: float) -> float:
    return abs(actual - bound) / (abs(bound) if bound else 1.0)


def _check_one(c: Candidate, k: Constraint, activity: str, pace: float | None) -> ConstraintResult:
    actual = _actual(c, k.kind, activity, pace)
    if k.kind == "roundtrip":
        bound = "Rundweg" if k.required else "kein Rundweg"
        if actual is None:
            return ConstraintResult(k.kind, None, None, bound, 1.0)
        ok = bool(actual) == bool(k.required)
        return ConstraintResult(k.kind, ok, bool(actual), bound, 0.0 if ok else 1.0)
    if actual is None:
        return ConstraintResult(k.kind, None, None, _range(k), 1.0)
    if k.min is not None and actual < k.min:
        return ConstraintResult(
            k.kind, False, actual, f"mindestens {_num(k.min)}", _rel(actual, k.min), k.min
        )
    if k.max is not None and actual > k.max:
        return ConstraintResult(
            k.kind, False, actual, f"höchstens {_num(k.max)}", _rel(actual, k.max), k.max
        )
    return ConstraintResult(k.kind, True, actual, _range(k), 0.0)


def _range(k: Constraint) -> str:
    parts = []
    if k.min is not None:
        parts.append(f"mindestens {_num(k.min)}")
    if k.max is not None:
        parts.append(f"höchstens {_num(k.max)}")
    return " und ".join(parts)


def check(
    c: Candidate, constraints: list[Constraint], activity: str, pace: float | None
) -> list[ConstraintResult]:
    return [_check_one(c, k, activity, pace) for k in constraints]


def contradiction(constraints: list[Constraint]) -> str | None:
    required = {k.required for k in constraints if k.kind == "roundtrip"}
    if required == {True, False}:
        return "Rundweg: Rundweg und kein Rundweg schließen sich aus"
    for kind in list(_UNIT):
        ks = [k for k in constraints if k.kind == kind]
        mins = [k.min for k in ks if k.min is not None]
        maxs = [k.max for k in ks if k.max is not None]
        if mins and maxs and max(mins) > min(maxs):
            unit = f" {_UNIT[kind]}"
            return (
                f"{_LABEL[kind]}: mindestens {_num(max(mins))}{unit} und "
                f"höchstens {_num(min(maxs))}{unit} schließen sich aus"
            )
    return None


def preference_score(c: Candidate, prefs: list[Preference]) -> PreferenceMatch:
    score, met, missing, hit = 0.0, [], [], []
    for p in prefs:
        has = p.tag_id in c.tags
        if p.mode == "prefer":
            (met if has else missing).append(p.tag_id)
            if has:
                score += p.weight
        elif has:
            hit.append(p.tag_id)
            score -= p.weight
    return PreferenceMatch(score, met, missing, hit)


def format_deviation(r: ConstraintResult) -> str:
    if r.kind == "roundtrip":
        if r.ok is None:
            return "Rundweg unbekannt"
        return "kein Rundweg" if r.bound == "Rundweg" else "Rundweg statt Streckentour"
    if r.ok is None:
        return f"{_LABEL[r.kind]} unbekannt"
    if isinstance(r.actual, bool) or not isinstance(r.actual, int | float):
        raise ValueError(f"{r.kind}: numeric actual expected")  # noqa: TRY004
    suffix = " entfernt" if r.kind == "radius_km" else ""
    return f"{_num_distinct(r.actual, r.bound_value)} {_UNIT[r.kind]}{suffix} statt {r.bound}"


def _reason(fallbacks: list[Scored], has_cands: bool, req: HikeRequest) -> str:
    head = "Keine Tour erfüllt alle Wünsche, weil "
    if fallbacks:
        real = [f.violated for f in fallbacks if f.violated and f.violated.ok is False]
        unknown = [f.violated for f in fallbacks if f.violated and f.violated.ok is None]
        parts = []
        if real:
            parts.append(
                "jede Tour mindestens eine Bedingung nicht erfüllt, am knappsten: "
                + "; ".join(format_deviation(r) for r in real)
            )
        if unknown:
            prefix = "" if real else "Angaben fehlen, "
            names = "; ".join(format_deviation(r) for r in unknown)
            parts.append(f"{prefix}nicht prüfbar: {names}")
        return head + "; ".join(parts)
    if not has_cands:
        radius = next(
            (k.max for k in req.constraints if k.kind == "radius_km" and k.max is not None), None
        )
        if req.start is not None and req.start.kind == "area":
            return head + "im Gebiet keine passende Tour liegt"
        if req.start is not None and req.start.kind == "place" and radius is not None:
            return head + f"im Umkreis von {_num(radius)} km keine passende Tour liegt"
        return head + "keine passende Tour gefunden wurde"
    return head + "jede Tour mehr als eine Bedingung verletzt"


def _fallback_key(s: Scored) -> tuple:
    v = s.violated
    return (v.ok is None, v.deviation_rel, -s.preference.score, s.candidate.trail_id)


def select(cands: list[Candidate], req: HikeRequest) -> Selection:
    contra = contradiction(req.constraints)
    if contra:
        return Selection([], [], f"Keine Tour erfüllt alle Wünsche, weil {contra}", contra)
    scored = []
    for c in cands:
        results = check(c, req.constraints, req.activity, req.pace_min_per_km)
        scored.append(
            Scored(
                c,
                results,
                preference_score(c, req.preferences),
                duration_h(c, req.activity, req.pace_min_per_km),
            )
        )
    matches = [s for s in scored if all(r.ok is True for r in s.results)]
    matches.sort(key=lambda s: (-s.preference.score, s.candidate.distance_km, s.candidate.trail_id))
    if matches:
        return Selection(matches[:MAX_MATCHES], [], None, None)
    best: dict[str, Scored] = {}
    for s in scored:
        bad = [r for r in s.results if r.ok is not True]
        if len(bad) != 1:
            continue
        s.violated = bad[0]
        cur = best.get(bad[0].kind)
        if cur is None or _fallback_key(s) < _fallback_key(cur):
            best[bad[0].kind] = s
    fallbacks = sorted(best.values(), key=_fallback_key)
    return Selection([], fallbacks, _reason(fallbacks, bool(cands), req), None)
