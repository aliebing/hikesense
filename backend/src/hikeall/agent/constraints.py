"""Deterministic constraint check, honest fallback and preference score (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass, field

from hikeall.agent.request import DEFAULT_RADIUS_KM, Constraint, HikeRequest, Preference
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


def _num(x: float) -> str:
    s = f"{round(x, 1):.1f}"
    s = s.removesuffix(".0")
    return s.replace(".", ",")


def duration_h(c: Candidate, activity: str, pace: float | None) -> float | None:
    if c.length_km is None:
        return None
    if activity == "run":
        return None if pace is None else c.length_km * pace / 60
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
            k.kind, False, actual, f"mindestens {_num(k.min)}", _rel(actual, k.min)
        )
    if k.max is not None and actual > k.max:
        return ConstraintResult(
            k.kind, False, actual, f"höchstens {_num(k.max)}", _rel(actual, k.max)
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
    for k in constraints:
        if k.kind != "roundtrip" and k.min is not None and k.max is not None and k.min > k.max:
            unit = f" {_UNIT[k.kind]}"
            return (
                f"{_LABEL[k.kind]}: mindestens {_num(k.min)}{unit} und "
                f"höchstens {_num(k.max)}{unit} schließen sich aus"
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
    assert isinstance(r.actual, int | float)
    suffix = " entfernt" if r.kind == "radius_km" else ""
    return f"{_num(r.actual)} {_UNIT[r.kind]}{suffix} statt {r.bound}"


def _reason(sel_fallbacks: list[Scored], has_cands: bool, req: HikeRequest) -> str:
    head = "Keine Tour erfüllt alle Wünsche, weil "
    if sel_fallbacks:
        parts = "; ".join(format_deviation(f.violated) for f in sel_fallbacks if f.violated)
        return head + f"jede Tour mindestens eine Bedingung verletzt, am knappsten: {parts}"
    if not has_cands:
        radius = next(
            (k.max for k in req.constraints if k.kind == "radius_km" and k.max is not None),
            DEFAULT_RADIUS_KM,
        )
        return head + f"im Umkreis von {_num(radius)} km keine passende Tour liegt"
    return head + "jede Tour mehr als eine Bedingung verletzt"


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
    matches.sort(key=lambda s: (-s.preference.score, s.candidate.distance_km))
    if matches:
        return Selection(matches[:MAX_MATCHES], [], None, None)
    best: dict[str, Scored] = {}
    for s in scored:
        bad = [r for r in s.results if r.ok is not True]
        if len(bad) != 1:
            continue
        s.violated = bad[0]
        cur = best.get(bad[0].kind)
        if cur is None or (bad[0].deviation_rel, -s.preference.score) < (
            cur.violated.deviation_rel,
            -cur.preference.score,
        ):
            best[bad[0].kind] = s
    fallbacks = sorted(best.values(), key=lambda s: s.violated.deviation_rel)
    return Selection([], fallbacks, _reason(fallbacks, bool(cands), req), None)
