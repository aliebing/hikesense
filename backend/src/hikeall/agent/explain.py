"""Per-candidate explanation rows (why a tour was shown, offered as fallback or rejected)."""

from __future__ import annotations

from hikeall.agent.constraints import MAX_MATCHES, WORDS, Scored, Selection, format_deviation
from hikeall.numfmt import Lang


def _r1(x: float | None) -> float | None:
    return None if x is None else round(x, 1)


def _note(s: Scored, status: str, lang: Lang = "de") -> str | None:
    if status == "shown":
        return None
    if status in ("fallback", "near_miss"):
        return format_deviation(s.violated, lang) if s.violated else None
    bad = [r for r in s.results if r.ok is not True]
    if not bad:
        return WORDS[lang]["top"].format(n=MAX_MATCHES)
    return "; ".join(format_deviation(r, lang) for r in bad)


def _row(s: Scored, status: str, lang: Lang = "de") -> dict:
    c = s.candidate
    return {
        "trail_id": c.trail_id,
        "name": c.name,
        "status": status,
        "note": _note(s, status, lang),
        "distance_km": _r1(c.distance_km),
        "length_km": _r1(c.length_km),
        "ascent_m": c.ascent_m,
        "roundtrip": c.roundtrip,
        "duration_h": _r1(s.duration_h),
        "score": round(s.preference.score, 2),
        "met": list(s.preference.met),
        "missing": list(s.preference.missing),
        "avoided": list(s.preference.avoided_hit),
        "results": [
            {
                "kind": r.kind,
                "ok": r.ok,
                "actual": _r1(r.actual) if isinstance(r.actual, float) else r.actual,
                "bound": r.bound,
            }
            for r in s.results
        ],
    }


def candidate_rows(sel: Selection, lang: Lang = "de") -> list[dict]:
    rows = [_row(s, "shown", lang) for s in sel.matches]
    rows += [_row(s, "fallback", lang) for s in sel.fallbacks]
    rows += [_row(s, "near_miss", lang) for s in sel.near_misses]
    rows += [_row(s, "rejected", lang) for s in sel.rejected]
    return rows
