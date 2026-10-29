"""Turn a chat message into a HikeRequest: one model call, then everything is resolved in code."""

from __future__ import annotations

import difflib
import re

from hikeall.agent.request import (
    DEFAULT_RADIUS_KM,
    MAX_PREFERENCES,
    Clarify,
    Constraint,
    HikeRequest,
    Preference,
    RawRequest,
    RawWish,
    ResolvedStart,
    Understood,
)
from hikeall.llm.gateway import LLMGateway
from hikeall.tags.vocabulary import Area, NearPlace, Tag, TagVocabulary, fold

__all__ = ["Clarify", "RawRequest", "Understood", "echo", "understand"]

MAX_OPTIONS = 3
RUN_SURFACE_TAG = "surface:gut_laufbar"
_PAREN = re.compile(r"\s*\([^)]*\)")

SYSTEM_PROMPT = """\
Du liest die Nachricht einer Person, die im Schwarzwald wandern oder laufen möchte, \
und füllst daraus ein strukturiertes Formular. Erfinde nichts und lass nichts weg.

Felder:
- intent: day_hike (Tagestour suchen), multiday (mehrtägige Tour), knowledge (Wissensfrage \
zum Schwarzwald), change (Änderung einer vorherigen Suche, z. B. "kürzer bitte"), other.
- activity: hike oder run; nur setzen, wenn die Person Laufen/Joggen oder Wandern erwähnt.
- start_text: Ort oder Gegend genau so, wie die Person ihn nennt (nicht korrigieren, nicht raten).
- Bedingungen (nur setzen, wenn genannt): roundtrip (true für Rundweg, false für Streckentour), \
length_km_min/max (Länge in km), ascent_m_min/max (Anstieg in Höhenmetern), \
duration_h_min/max (Dauer in Stunden), radius_km_max (Umkreis um den Start in km).
- "unter/höchstens X" ist ein Maximum, "über/mindestens X" ein Minimum.
- pace_min_per_km: Lauftempo in Minuten pro km, nur wenn genannt.
- wishes: jeder weitere Wunsch als kurzer Begriff (z. B. "Aussicht", "Wasserfall", \
"Einkehr", "Kinderwagen"), mode prefer oder avoid, weight 1 bis 5 (3 = normal). \
Jeden Wunsch aufführen, auch wenn er ungewöhnlich ist.
- question: bei intent knowledge die Frage.
Antworte nur mit dem Formular."""

_CLARIFY_CHANGE = Clarify(
    question=(
        "Worauf bezieht sich die Änderung? Nenne bitte zuerst, welche Tour du suchst "
        "(Ort, Länge, Höhenmeter …)."
    )
)
_CLARIFY_PACE = Clarify(question="Welches Tempo läufst du ungefähr (min/km)?")


def understand(
    gw: LLMGateway, vocab: TagVocabulary, message: str, previous: HikeRequest | None
) -> Understood:
    user = message
    if previous is not None:
        user = f"Bisherige Anfrage: {echo(previous, vocab)}\nNeue Nachricht: {message}"
    raw = gw.structured(RawRequest, SYSTEM_PROMPT, user)
    is_change = raw.intent == "change"
    if is_change and previous is None:
        return _CLARIFY_CHANGE

    wants_tour = raw.intent in ("day_hike", "multiday", "change")
    start: ResolvedStart | None = None
    start_text = raw.start_text.strip() if raw.start_text else None
    if wants_tour and start_text:
        resolved = _resolve_start(vocab, start_text)
        if isinstance(resolved, Clarify):
            return resolved
        start = resolved

    preferences, unmatched = _resolve_wishes(vocab, raw.wishes)
    constraints, invalid = _constraints(raw)
    unmatched += invalid
    pace = raw.pace_min_per_km
    if pace is not None and pace <= 0:
        unmatched.append(_invalid("Tempo", pace))
        pace = None
    delta = HikeRequest(
        intent=raw.intent,
        activity=raw.activity or "hike",
        start_text=start_text,
        start=start,
        constraints=constraints,
        preferences=preferences[:MAX_PREFERENCES],
        pace_min_per_km=pace,
        unmatched=unmatched,
        question=(raw.question or message) if raw.intent == "knowledge" else raw.question,
    )
    overflow = preferences[MAX_PREFERENCES:]
    if overflow:  # never drop a wish silently
        delta.unmatched += [_text_for(vocab, p.tag_id) for p in overflow]

    req = _merge(previous, delta, raw.activity, vocab) if is_change and previous else delta
    if wants_tour:
        req = _finish(req, vocab)
        if req.activity == "run" and _needs_pace(req):
            return _CLARIFY_PACE
    return req


def _invalid(label: str, value: float) -> str:
    return f"{label}: {_num(value)} ist kein gültiger Wert"


def _constraints(raw: RawRequest) -> tuple[list[Constraint], list[str]]:
    out: list[Constraint] = []
    invalid: list[str] = []
    if raw.roundtrip is not None:
        out.append(Constraint(kind="roundtrip", required=raw.roundtrip))
    for kind, lo, hi in (
        ("length_km", raw.length_km_min, raw.length_km_max),
        ("ascent_m", raw.ascent_m_min, raw.ascent_m_max),
        ("duration_h", raw.duration_h_min, raw.duration_h_max),
        ("radius_km", None, raw.radius_km_max),
    ):
        bounds = []
        for value in (lo, hi):
            if value is not None and value <= 0:
                invalid.append(_invalid(_LABELS[kind][0].strip(), value))
                value = None
            bounds.append(value)
        if bounds[0] is not None or bounds[1] is not None:
            out.append(Constraint(kind=kind, min=bounds[0], max=bounds[1]))
    return out, invalid


def _merge(
    previous: HikeRequest, delta: HikeRequest, activity: str | None, vocab: TagVocabulary
) -> HikeRequest:
    new_kinds = {c.kind for c in delta.constraints}
    prefs = {p.tag_id: p for p in previous.preferences}
    if any(p.tag_id.startswith("surface:") for p in delta.preferences):
        prefs.pop(RUN_SURFACE_TAG, None)  # the user's own surface wish replaces the run default
    for p in delta.preferences:
        prefs[p.tag_id] = p
    merged_prefs = list(prefs.values())
    unmatched = previous.unmatched + [u for u in delta.unmatched if u not in previous.unmatched]
    for p in merged_prefs[MAX_PREFERENCES:]:  # limit reached: report, never drop silently
        label = _text_for(vocab, p.tag_id)
        if label not in unmatched:
            unmatched.append(label)
    return HikeRequest(
        intent=previous.intent,
        activity=activity or previous.activity,
        start_text=delta.start_text if delta.start else previous.start_text,
        start=delta.start or previous.start,
        constraints=[c for c in previous.constraints if c.kind not in new_kinds]
        + delta.constraints,
        preferences=merged_prefs[:MAX_PREFERENCES],
        pace_min_per_km=(
            delta.pace_min_per_km if delta.pace_min_per_km is not None else previous.pace_min_per_km
        ),
        unmatched=unmatched,
        question=previous.question,
    )


def _finish(req: HikeRequest, vocab: TagVocabulary) -> HikeRequest:
    """Defaults that must stay visible in echo(): 15 km radius, runnable surface for runs."""
    req = req.model_copy(deep=True)
    if (
        req.start is not None
        and req.start.kind == "place"
        and not any(c.kind == "radius_km" for c in req.constraints)
    ):
        req.constraints.append(Constraint(kind="radius_km", max=DEFAULT_RADIUS_KM))
    if (
        req.activity == "run"
        and RUN_SURFACE_TAG in vocab
        and not any(p.tag_id.startswith("surface:") for p in req.preferences)
        and len(req.preferences) < MAX_PREFERENCES
    ):
        req.preferences.append(Preference(tag_id=RUN_SURFACE_TAG, mode="prefer", weight=3))
    return req


def _needs_pace(req: HikeRequest) -> bool:
    return req.pace_min_per_km is None and any(c.kind == "duration_h" for c in req.constraints)


# --- wishes -------------------------------------------------------------------------------


def _terms(tag: Tag) -> list[str]:
    return [t for t in (fold(x) for x in [tag.label, *tag.synonyms]) if t]


def _resolve_wishes(
    vocab: TagVocabulary, wishes: list[RawWish]
) -> tuple[list[Preference], list[str]]:
    """Exact or whole-word-prefix match -> tag; anything else -> unmatched (R8).

    A plain string prefix would map "Kinderwagen" to "kinderwagentauglich" (surface tag), which
    does not check what the user asked for, so the prefix must end at a word boundary.
    """
    prefs: dict[str, Preference] = {}
    conflicts: list[str] = []
    unmatched: list[str] = []
    for wish in wishes:
        needle = fold(wish.text)
        tag = next(
            (
                t
                for t in vocab.search(wish.text, limit=50)
                if t.category in ("feature", "surface")
                and any(x == needle or x.startswith(needle + " ") for x in _terms(t))
            ),
            None,
        )
        if tag is None:
            if wish.text.strip() and wish.text.strip() not in unmatched:
                unmatched.append(wish.text.strip())
            continue
        weight = min(5, max(1, wish.weight))
        if tag.id in conflicts:
            continue
        old = prefs.get(tag.id)
        if old is None:
            prefs[tag.id] = Preference(tag_id=tag.id, mode=wish.mode, weight=weight)
        elif old.mode == wish.mode:
            old.weight = max(old.weight, weight)
        else:  # prefer and avoid at once: apply neither, say so
            del prefs[tag.id]
            conflicts.append(tag.id)
            unmatched.append(f"{tag.label}: bevorzugen und meiden zugleich")
    return list(prefs.values()), unmatched


def _text_for(vocab: TagVocabulary, tag_id: str) -> str:
    tag = vocab.get(tag_id)
    return tag.label if tag else tag_id


# --- start --------------------------------------------------------------------------------


def _strip(text: str) -> str:
    return fold(_PAREN.sub("", text))


def _tier(needle: str, terms: list[str]) -> int | None:
    if needle in terms:
        return 0
    if any(t.startswith(needle) for t in terms):
        return 1
    if any(needle in t for t in terms):
        return 2
    return None


def _resolve_start(vocab: TagVocabulary, text: str) -> ResolvedStart | Clarify:
    cands = [t for t in vocab.all() if t.category in ("place", "area")]
    best: list[Tag] = []
    shown = _display_names(cands)
    if "(" in text:  # user gave the disambiguating suffix: try the full label first
        full = fold(text)
        best = [t for t in cands if full in _terms(t) or full == fold(shown[t.id])]
    if not best:
        needle = _strip(text)
        tiers: dict[int, list[Tag]] = {}
        for t in cands:
            tier = _tier(needle, [_strip(x) for x in [t.label, *t.synonyms] if _strip(x)])
            if tier is not None:
                tiers.setdefault(tier, []).append(t)
        best = tiers[min(tiers)] if tiers else []
    if len(best) == 1:
        return _to_start(best[0])
    if best:
        options = [shown[t.id] for t in best][:MAX_OPTIONS]
        return Clarify(
            question=f"Meinst du {_join_or(options)}? „{text}“ ist nicht eindeutig.",
            options=options,
        )
    labels = {t.label: t for t in cands}
    close = difflib.get_close_matches(text, list(labels), n=MAX_OPTIONS, cutoff=0.6)
    if not close:
        folded = {fold(label): label for label in labels}
        close = [
            folded[f]
            for f in difflib.get_close_matches(fold(text), list(folded), n=MAX_OPTIONS, cutoff=0.6)
        ]
    msg = f"Den Ort „{text}“ kenne ich nicht."
    if close:
        msg += f" Meinst du {_join_or(close)}?"
    else:
        msg += " Nenne bitte einen Ort oder eine Gegend im Schwarzwald."
    return Clarify(question=msg, options=close)


_KIND_NAMES = {"peak": "Gipfel", "town": "Ort", "village": "Ort", "lake": "See"}


def _display_names(tags: list[Tag]) -> dict[str, str]:
    """Label per tag id; identical labels get the kind in parentheses to stay distinct."""
    counts: dict[str, int] = {}
    for t in tags:
        counts[t.label] = counts.get(t.label, 0) + 1
    out = {}
    for t in tags:
        out[t.id] = t.label
        if counts[t.label] > 1:
            kind = t.rule.kind if isinstance(t.rule, NearPlace) else None
            out[t.id] = f"{t.label} ({_KIND_NAMES.get(kind or '', t.id)})"
    return out


def _to_start(tag: Tag) -> ResolvedStart:
    rule = tag.rule
    if isinstance(rule, Area):
        return ResolvedStart(kind="area", tag_id=tag.id, label=tag.label, bbox=rule.bbox)
    lat = rule.lat if isinstance(rule, NearPlace) else None
    lon = rule.lon if isinstance(rule, NearPlace) else None
    return ResolvedStart(kind="place", tag_id=tag.id, label=tag.label, lat=lat, lon=lon)


def _join_or(items: list[str]) -> str:
    quoted = [f"„{i}“" for i in items]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + f" oder {quoted[-1]}"


# --- echo ---------------------------------------------------------------------------------


def _num(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _range(c: Constraint, unit: str, prefix: str = "") -> str:
    if c.min is not None and c.max is not None:
        return f"{prefix}{_num(c.min)}–{_num(c.max)} {unit}"
    if c.min is not None:
        return f"{prefix}mindestens {_num(c.min)} {unit}"
    return f"{prefix}höchstens {_num(c.max)} {unit}"  # type: ignore[arg-type]


_LABELS = {
    "length_km": ("Länge ", "km"),
    "ascent_m": ("Anstieg ", "Hm"),
    "duration_h": ("Dauer ", "h"),
    "radius_km": ("Umkreis ", "km"),
}
_INTENTS = {
    "day_hike": "Tagestour",
    "multiday": "Mehrtagestour",
    "knowledge": "Wissensfrage",
    "change": "Änderung",
    "other": "Sonstiges",
}


def echo(req: HikeRequest, vocab: TagVocabulary) -> str:
    """German "Verstanden: …" sentence, built from fields only."""
    parts = [_INTENTS[req.intent], "Laufen" if req.activity == "run" else "Wandern"]
    if req.start is not None:
        parts.append(f"Start: {req.start.label}")
    elif req.start_text:
        parts.append(f"Start: {req.start_text} (nicht aufgelöst)")
    for c in req.constraints:
        if c.kind == "roundtrip":
            parts.append("Rundweg" if c.required else "kein Rundweg")
        else:
            prefix, unit = _LABELS[c.kind]
            parts.append(_range(c, unit, prefix))
    if req.pace_min_per_km is not None:
        parts.append(f"Tempo {_num(req.pace_min_per_km)} min/km")
    text = "Verstanden: " + ", ".join(parts)
    wishes = []
    for p in req.preferences:
        label = _text_for(vocab, p.tag_id)
        wishes.append(f"{label} (Gewicht {p.weight})" if p.mode == "prefer" else f"ohne {label}")
    if wishes:
        text += "; Vorlieben: " + ", ".join(wishes)
    if req.unmatched:
        text += "; nicht prüfbar: " + ", ".join(req.unmatched)
    if req.question and req.intent == "knowledge":
        text += f"; Frage: {req.question}"
    return text + "."
