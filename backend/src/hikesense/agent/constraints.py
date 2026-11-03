"""Deterministic constraint check, honest fallback and preference score (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass, field

from hikesense.agent.request import Constraint, HikeRequest, Preference
from hikesense.hiking_time import din33466
from hikesense.numfmt import Lang, fmt

MAX_MATCHES = 5
MAX_REJECTED = 20
NEAR_MISS_MAX_REL = 0.25  # a near miss misses one hard condition by at most this much
NEAR_MISS_FILL_TO = 3  # 1-2 matches are filled up with near misses to this many cards
_LABEL = {
    "de": {
        "length_km": "Länge",
        "ascent_m": "Höhenmeter",
        "duration_h": "Dauer",
        "radius_km": "Entfernung",
        "roundtrip": "Rundweg",
    },
    "en": {
        "length_km": "Length",
        "ascent_m": "Ascent",
        "duration_h": "Duration",
        "radius_km": "Distance",
        "roundtrip": "Round walk",
    },
}
_UNIT = {
    "de": {"length_km": "km", "ascent_m": "Hm", "duration_h": "h", "radius_km": "km"},
    "en": {"length_km": "km", "ascent_m": "m", "duration_h": "h", "radius_km": "km"},
}
# fixed words of the bound, deviation and fallback texts, per reply language
WORDS = {
    "de": {
        "min": "mindestens {v}",
        "max": "höchstens {v}",
        "and": " und ",
        "rt_yes": "Rundweg",
        "rt_no": "kein Rundweg",
        "rt_contra": "Rundweg: Rundweg und kein Rundweg schließen sich aus",
        "contra": "{label}: mindestens {lo}{unit} und höchstens {hi}{unit} schließen sich aus",
        "rt_unknown": "Rundweg unbekannt",
        "rt_not": "kein Rundweg",
        "rt_instead": "Rundweg statt Streckentour",
        "unknown": "{label} unbekannt",
        "away": " entfernt",
        "dev": "{actual} {unit}{away} statt {bound}",
        "head": "Keine Tour erfüllt alle Wünsche, weil ",
        "every": "jede Tour mindestens eine Bedingung nicht erfüllt, am knappsten: ",
        "missing": "Angaben fehlen, ",
        "unchecked": "{prefix}nicht prüfbar: {names}",
        "area": "im Gebiet keine passende Tour liegt",
        "radius": "im Umkreis von {r} km keine passende Tour liegt",
        "none": "keine passende Tour gefunden wurde",
        "several": "jede Tour mehr als eine Bedingung verletzt",
        "top": "nur die besten {n} gezeigt",
    },
    "en": {
        "min": "at least {v}",
        "max": "at most {v}",
        "and": " and ",
        "rt_yes": "round walk",
        "rt_no": "not a round walk",
        "rt_contra": "Round walk: a round walk and not a round walk are mutually exclusive",
        "contra": "{label}: at least {lo}{unit} and at most {hi}{unit} are mutually exclusive",
        "rt_unknown": "Round walk unknown",
        "rt_not": "not a round walk",
        "rt_instead": "round walk instead of a point-to-point tour",
        "unknown": "{label} unknown",
        "away": " away",
        "dev": "{actual} {unit}{away} instead of {bound}",
        "head": "No tour meets all your wishes, because ",
        "every": "every tour fails at least one condition, closest: ",
        "missing": "information is missing, ",
        "unchecked": "{prefix}cannot be checked: {names}",
        "area": "there is no suitable tour in the area",
        "radius": "there is no suitable tour within {r} km",
        "none": "no suitable tour was found",
        "several": "every tour fails more than one condition",
        "top": "only the best {n} shown",
    },
}


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
    cover_thumb_url: str | None = None
    cover_author: str | None = None
    cover_license: str | None = None
    cover_license_url: str | None = None
    cover_page_url: str | None = None


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
    rejected: list[Scored] = field(default_factory=list)
    near_misses: list[Scored] = field(default_factory=list)


def _num(x: float, lang: Lang = "de", decimals: int = 1) -> str:
    return fmt(x, lang, decimals)  # half-up, like the grounding check


def _num_distinct(actual: float, bound: float | None, lang: Lang = "de") -> str:
    """Format with as many decimals as needed so a violation never looks equal to its bound."""
    for decimals in (1, 2, 3, 4):
        text = _num(actual, lang, decimals)
        if bound is None or text != _num(bound, lang, decimals):
            return text
    return _num(actual, lang, 4)


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


def _check_one(
    c: Candidate, k: Constraint, activity: str, pace: float | None, lang: Lang = "de"
) -> ConstraintResult:
    t = WORDS[lang]
    actual = _actual(c, k.kind, activity, pace)
    if k.kind == "roundtrip":
        bound = t["rt_yes"] if k.required else t["rt_no"]
        if actual is None:
            return ConstraintResult(k.kind, None, None, bound, 1.0)
        ok = bool(actual) == bool(k.required)
        return ConstraintResult(k.kind, ok, bool(actual), bound, 0.0 if ok else 1.0)
    if actual is None:
        return ConstraintResult(k.kind, None, None, _range(k, lang), 1.0)
    if k.min is not None and actual < k.min:
        return ConstraintResult(
            k.kind, False, actual, t["min"].format(v=_num(k.min, lang)), _rel(actual, k.min), k.min
        )
    if k.max is not None and actual > k.max:
        return ConstraintResult(
            k.kind, False, actual, t["max"].format(v=_num(k.max, lang)), _rel(actual, k.max), k.max
        )
    return ConstraintResult(k.kind, True, actual, _range(k, lang), 0.0)


def _range(k: Constraint, lang: Lang = "de") -> str:
    t = WORDS[lang]
    parts = []
    if k.min is not None:
        parts.append(t["min"].format(v=_num(k.min, lang)))
    if k.max is not None:
        parts.append(t["max"].format(v=_num(k.max, lang)))
    return t["and"].join(parts)


def check(
    c: Candidate,
    constraints: list[Constraint],
    activity: str,
    pace: float | None,
    lang: Lang = "de",
) -> list[ConstraintResult]:
    return [_check_one(c, k, activity, pace, lang) for k in constraints]


def contradiction(constraints: list[Constraint], lang: Lang = "de") -> str | None:
    t = WORDS[lang]
    required = {k.required for k in constraints if k.kind == "roundtrip"}
    if required == {True, False}:
        return t["rt_contra"]
    for kind in ("length_km", "ascent_m", "duration_h", "radius_km"):
        ks = [k for k in constraints if k.kind == kind]
        mins = [k.min for k in ks if k.min is not None]
        maxs = [k.max for k in ks if k.max is not None]
        if mins and maxs and max(mins) > min(maxs):
            return t["contra"].format(
                label=_LABEL[lang][kind],
                lo=_num(max(mins), lang),
                hi=_num(min(maxs), lang),
                unit=f" {_UNIT[lang][kind]}",
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


def format_deviation(r: ConstraintResult, lang: Lang = "de") -> str:
    t = WORDS[lang]
    if r.kind == "roundtrip":
        if r.ok is None:
            return t["rt_unknown"]
        # the bound is the requirement's text in the language it was built in
        required = r.bound in (WORDS["de"]["rt_yes"], WORDS["en"]["rt_yes"])
        return t["rt_not"] if required else t["rt_instead"]
    if r.ok is None:
        return t["unknown"].format(label=_LABEL[lang][r.kind])
    if isinstance(r.actual, bool) or not isinstance(r.actual, int | float):
        raise ValueError(f"{r.kind}: numeric actual expected")  # noqa: TRY004
    bound = r.bound  # normally rebuilt from the value, so the result's own language never leaks
    if r.bound_value is not None:
        side = "min" if r.actual < r.bound_value else "max"
        bound = t[side].format(v=_num(r.bound_value, lang))
    return t["dev"].format(
        actual=_num_distinct(r.actual, r.bound_value, lang),
        unit=_UNIT[lang][r.kind],
        away=t["away"] if r.kind == "radius_km" else "",
        bound=bound,
    )


def _reason(fallbacks: list[Scored], has_cands: bool, req: HikeRequest, lang: Lang = "de") -> str:
    t = WORDS[lang]
    head = t["head"]
    if fallbacks:
        real = [f.violated for f in fallbacks if f.violated and f.violated.ok is False]
        unknown = [f.violated for f in fallbacks if f.violated and f.violated.ok is None]
        parts = []
        if real:
            parts.append(t["every"] + "; ".join(format_deviation(r, lang) for r in real))
        if unknown:
            prefix = "" if real else t["missing"]
            names = "; ".join(format_deviation(r, lang) for r in unknown)
            parts.append(t["unchecked"].format(prefix=prefix, names=names))
        return head + "; ".join(parts)
    if not has_cands:
        radius = next(
            (k.max for k in req.constraints if k.kind == "radius_km" and k.max is not None), None
        )
        if req.start is not None and req.start.kind == "area":
            return head + t["area"]
        if req.start is not None and req.start.kind == "place" and radius is not None:
            return head + t["radius"].format(r=_num(radius, lang))
        return head + t["none"]
    return head + t["several"]


def _fallback_key(s: Scored) -> tuple:
    v = s.violated
    return (v.ok is None, v.deviation_rel, -s.preference.score, s.candidate.trail_id)


def _rejected_key(s: Scored) -> tuple:
    bad = [r for r in s.results if r.ok is not True]
    return (
        len(bad),
        sum(r.deviation_rel for r in bad if r.ok is False),
        -s.preference.score,
        s.candidate.distance_km,
        s.candidate.trail_id,
    )


def _rejected(scored: list[Scored], shown: list[Scored]) -> list[Scored]:
    taken = {id(s) for s in shown}
    rest = [s for s in scored if id(s) not in taken]
    return sorted(rest, key=_rejected_key)[:MAX_REJECTED]


def _near_misses(scored: list[Scored], n_matches: int) -> list[Scored]:
    """Fill 1-2 matches up with tours that miss exactly one known, non-roundtrip condition by
    at most NEAR_MISS_MAX_REL. Sets `violated` on the picked ones."""
    if not 0 < n_matches < NEAR_MISS_FILL_TO:
        return []
    found = []
    for s in scored:
        bad = [r for r in s.results if r.ok is not True]
        if len(bad) != 1:
            continue
        r = bad[0]
        if r.ok is False and r.kind != "roundtrip" and r.deviation_rel <= NEAR_MISS_MAX_REL:
            found.append((r, s))
    found.sort(
        key=lambda x: (
            x[0].deviation_rel,
            -x[1].preference.score,
            x[1].candidate.distance_km,
            x[1].candidate.trail_id,
        )
    )
    picked = []
    for r, s in found[: NEAR_MISS_FILL_TO - n_matches]:
        s.violated = r
        picked.append(s)
    return picked


def select(cands: list[Candidate], req: HikeRequest, lang: Lang = "de") -> Selection:
    contra = contradiction(req.constraints, lang)
    if contra:
        return Selection([], [], WORDS[lang]["head"] + contra, contra)
    scored = []
    for c in cands:
        results = check(c, req.constraints, req.activity, req.pace_min_per_km, lang)
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
        shown = matches[:MAX_MATCHES]
        near = _near_misses(scored, len(shown))
        return Selection(shown, [], None, None, _rejected(scored, shown + near), near)
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
    return Selection(
        [],
        fallbacks,
        _reason(fallbacks, bool(cands), req, lang),
        None,
        _rejected(scored, fallbacks),
    )
