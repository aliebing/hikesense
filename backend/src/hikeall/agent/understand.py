"""Turn a chat message into a HikeRequest: one model call, then everything is resolved in code."""

from __future__ import annotations

import difflib
import re
from datetime import date, time, timedelta
from typing import Protocol

from hikeall.agent.request import (
    DEFAULT_DAY_KM,
    DEFAULT_RADIUS_KM,
    DEFAULT_START_TIME,
    MAX_DAYS,
    MAX_PREFERENCES,
    MIN_DAYS,
    Clarify,
    Constraint,
    DayChange,
    HikeRequest,
    Preference,
    RawRequest,
    RawWish,
    ResolvedStart,
    Understood,
)
from hikeall.agent.texts import REGION_NAMES_EN
from hikeall.geo import haversine_km
from hikeall.llm.gateway import LLMGateway
from hikeall.numfmt import Lang
from hikeall.regions import REGION_NAMES, REGION_PHRASE
from hikeall.tags.vocabulary import Area, LongTrail, NearPlace, Tag, TagVocabulary, fold

__all__ = [
    "Clarify",
    "RawRequest",
    "TrailLookup",
    "Understood",
    "echo",
    "parse",
    "resolve",
    "resolve_option",
    "understand",
]

LANGS: tuple[Lang, ...] = ("de", "en")
_REGION_NAMES = {"de": REGION_NAMES, "en": REGION_NAMES_EN}
_DATE_FMT = {"de": "%d.%m.%Y", "en": "%d/%m/%Y"}

MAX_OPTIONS = 3
RUN_SURFACE_TAG = "surface:gut_laufbar"
APPROX_BAND = 0.15  # "8 km" -> 6,8–9,2 km, shown in the echo
ROUNDTRIP_TAG = "feature:rundweg"
# wish words that are the fixed roundtrip condition, never a preference (also "Laufrunde")
_ROUNDTRIP_WORDS = (
    "rundweg", "runde", "rundtour", "rundwanderung", "rundkurs",
    "round walk", "round trip", "roundtrip", "circular walk", "circular route", "loop",
)  # fmt: skip
# words that state a roundtrip ("Rundweg", "Laufrunde", "Schleife") or a point-to-point tour
# ("Strecke…", "von A nach B"); the model's roundtrip field counts only with one of them
_ROUNDTRIP_SAID = re.compile(
    r"rundweg|runde|rundtour|rundwander|rundkurs|rundgang|rundlauf|schleife|strecke"
    r"|\bvon\b.+\bnach\b"
    r"|round walk|round trip|roundtrip|circular|\bloop\b|point to point|one way|\bfrom\b.+\bto\b"
)
_PAREN = re.compile(r"\s*\([^)]*\)")

SYSTEM_PROMPT = f"""\
Du liest die Nachricht einer Person, die {REGION_PHRASE} wandern oder laufen möchte, \
und füllst daraus ein strukturiertes Formular. Erfinde nichts und lass nichts weg.

Felder:
- intent: day_hike (Tagestour suchen), multiday (mehrtägige Tour), knowledge (Wissensfrage \
zu {REGION_NAMES}), change (Änderung einer vorherigen Suche, z. B. "kürzer bitte"), other.
- intent events: Frage nach Läufen/Wanderveranstaltungen (z. B. "Halbmarathon im Juni bei \
Freiburg"); intent groups: Frage nach Lauf- oder Wandergruppen (z. B. "Lauftreff in Freiburg"). \
Bei beiden die Frage mit Ort, Monat und Distanzen in question, genau wie geschrieben.
- Mehrtagestour (intent multiday): trail_text (Fernweg wie genannt, z. B. "Westweg"), days \
(Anzahl Tage), day_km (Tagesziel in km, z. B. "18 km pro Tag"), start_date (ISO, nur wenn ein \
Datum geschrieben steht), start_time (HH:MM, nur wenn eine Uhrzeit geschrieben steht). \
Unterkunftswünsche ohne Tag (Halbpension, Sauna …) als wishes.
- "Tag 3 kürzer/länger" (Änderung eines Mehrtagesplans): intent change, day_change_day (3), \
day_change_direction (shorter oder longer).
- activity: hike oder run; nur setzen, wenn die Person Laufen/Joggen oder Wandern erwähnt.
- start_text: Ort oder Gegend genau so, wie die Person ihn nennt (nicht korrigieren, nicht raten).
- Bedingungen (nur setzen, wenn genannt): roundtrip (true für Rundweg, false für Streckentour), \
length_km_min/max (Länge in km), ascent_m_min/max (Anstieg in Höhenmetern), \
duration_h_min/max (Dauer in Stunden), radius_km_max (Umkreis um den Start in km).
- "unter/höchstens X" ist ein Maximum, "über/mindestens X" ein Minimum.
- Eine einzelne Zahl ohne unter/über/höchstens/mindestens (z. B. "8 km", "etwa 3 Stunden", \
"400 Hm") setzt length_km_approx, duration_h_approx bzw. ascent_m_approx – nicht min oder max.
- pace_min_per_km: Lauftempo in Minuten pro km, nur wenn genannt.
- wishes: jeder weitere Wunsch als kurzer Begriff (z. B. "Aussicht", "Wasserfall", \
"Einkehr", "Kinderwagen"), mode prefer oder avoid, weight 1 bis 5 (3 = normal). \
Jeden Wunsch aufführen, auch wenn er ungewöhnlich ist.
- question: bei intent knowledge die Frage.
Antworte nur mit dem Formular."""

# fixed question and note texts per reply language; the clarify OPTIONS are never translated
# (place and trail names), only the question text and the kind words around them
_T = {
    "de": {
        "change": (
            "Worauf bezieht sich die Änderung? Nenne bitte zuerst, welche Tour du suchst "
            "(Ort, Länge, Höhenmeter …)."
        ),
        "pace": "Welches Tempo läufst du ungefähr (min/km)?",
        "unsure": "{}: Angabe nicht sicher erkannt – bitte als Zahl angeben",
        "invalid": "{label}: {v} ist kein gültiger Wert",
        "change_note": "Änderung nicht erkannt – bitte z. B. „Tag 3 kürzer“ schreiben",
        "pace_word": "Tempo",
        "date_word": "Datum",
        "time_word": "Uhrzeit",
        "days_word": "Tage",
        "day_goal": "Tagesziel",
        "conflict": "{label}: bevorzugen und meiden zugleich",
        "ambiguous": "Meinst du {options}? „{text}“ ist nicht eindeutig.",
        "unknown_place": "Den Ort „{text}“ kenne ich nicht.",
        "did_you_mean": " Meinst du {options}?",
        "name_place": " Nenne bitte einen Ort oder eine Gegend ({regions}).",
        "or": " oder ",
        "start_question": "Wo soll die Mehrtagestour starten?",
        "days_question": "Wie viele Tage?",
        "plan_days": "Der Plan hat {n} Tage. Welchen Tag meinst du?",
        "unknown_trail": "Welchen Fernweg meinst du? „{text}“ kenne ich nicht.",
        "which_trail": "Auf welchem Fernweg?",
        "off_trail": "{label} liegt nicht am {trail}. Ab welchem Etappenort?",
        "days_invalid": "Tage: {n} ist kein gültiger Wert ({lo}–{hi})",
        "no_such_date": "Datum: {label} gibt es nicht",
        "past_date": "Datum: {d} liegt in der Vergangenheit",
        "bad_time": "Uhrzeit: {h}:{m:02d} ist kein gültiger Wert",
        "understood": "Verstanden: ",
        "wishes": "; Vorlieben: ",
        "weight": "{label} (Gewicht {w})",
        "without": "ohne {label}",
        "unchecked": "; nicht prüfbar: ",
        "question": "; Frage: {q}",
        "start": "Start: {label}",
        "start_unresolved": "Start: {label} (nicht aufgelöst)",
        "roundtrip": "Rundweg",
        "no_roundtrip": "kein Rundweg",
        "pace_echo": "Tempo {v} min/km",
        "walking": "Wandern",
        "running": "Laufen",
        "west": "{label} (Westvariante – Ostvariante möglich)",
        "west_only": "{label} (Westvariante)",
        "days": "{n} Tage",
        "day": "1 Tag",
        "day_goal_echo": "Tagesziel {v} km{std}",
        "default": " (Standard)",
        "on_date": "am {d}",
        "start_time": "Start {t:%H:%M} Uhr{std}",
        "shorter": "kürzer",
        "longer": "länger",
        "day_change": "Tag {n} {word}",
        "min": "mindestens {v} {unit}",
        "max": "höchstens {v} {unit}",
        "kinds": {
            "peak": "Gipfel",
            "town": "Ort",
            "village": "Ort",
            "lake": "See",
            "municipality": "Gemeinde",
            "area": "Gebiet",
        },
        "intents": {
            "day_hike": "Tagestour",
            "multiday": "Mehrtagestour",
            "knowledge": "Wissensfrage",
            "change": "Änderung",
            "events": "Veranstaltungen",
            "groups": "Gruppen",
            "other": "Sonstiges",
        },
        "labels": {
            "length_km": ("Länge ", "km"),
            "ascent_m": ("Anstieg ", "Hm"),
            "duration_h": ("Dauer ", "h"),
            "radius_km": ("Umkreis ", "km"),
        },
        "names": {
            "length_km": "Länge",
            "ascent_m": "Anstieg",
            "duration_h": "Dauer",
            "radius_km": "Umkreis",
        },
    },
    "en": {
        "change": (
            "What does the change refer to? Please first say which tour you are looking for "
            "(place, length, ascent …)."
        ),
        "pace": "Roughly what pace do you run (min/km)?",
        "unsure": "{}: value not recognised reliably – please give it as a number",
        "invalid": "{label}: {v} is not a valid value",
        "change_note": "Change not recognised – please write e.g. “day 3 shorter”",
        "pace_word": "Pace",
        "date_word": "Date",
        "time_word": "Time",
        "days_word": "Days",
        "day_goal": "Daily target",
        "conflict": "{label}: wanted and unwanted at once",
        "ambiguous": "Did you mean {options}? „{text}“ is ambiguous.",
        "unknown_place": "I don't know the place „{text}“.",
        "did_you_mean": " Did you mean {options}?",
        "name_place": " Please name a place or an area ({regions}).",
        "or": " or ",
        "start_question": "Where should the multi-day tour start?",
        "days_question": "How many days?",
        "plan_days": "The plan has {n} days. Which day do you mean?",
        "unknown_trail": "Which long-distance trail do you mean? I don't know „{text}“.",
        "which_trail": "On which long-distance trail?",
        "off_trail": "{label} is not on the {trail}. From which stage town?",
        "days_invalid": "Days: {n} is not a valid value ({lo}–{hi})",
        "no_such_date": "Date: {label} does not exist",
        "past_date": "Date: {d} is in the past",
        "bad_time": "Time: {h}:{m:02d} is not a valid value",
        "understood": "Understood: ",
        "wishes": "; wishes: ",
        "weight": "{label} (weight {w})",
        "without": "without {label}",
        "unchecked": "; cannot be checked: ",
        "question": "; question: {q}",
        "start": "start: {label}",
        "start_unresolved": "start: {label} (not resolved)",
        "roundtrip": "round walk",
        "no_roundtrip": "not a round walk",
        "pace_echo": "pace {v} min/km",
        "walking": "walking",
        "running": "running",
        "west": "{label} (western variant – eastern variant possible)",
        "west_only": "{label} (western variant)",
        "days": "{n} days",
        "day": "1 day",
        "day_goal_echo": "daily target {v} km{std}",
        "default": " (default)",
        "on_date": "on {d}",
        "start_time": "start {t:%H:%M}{std}",
        "shorter": "shorter",
        "longer": "longer",
        "day_change": "day {n} {word}",
        "min": "at least {v} {unit}",
        "max": "at most {v} {unit}",
        "kinds": {
            "peak": "peak",
            "town": "town",
            "village": "village",
            "lake": "lake",
            "municipality": "municipality",
            "area": "area",
        },
        "intents": {
            "day_hike": "day hike",
            "multiday": "multi-day tour",
            "knowledge": "knowledge question",
            "change": "change",
            "events": "events",
            "groups": "groups",
            "other": "other",
        },
        "labels": {
            "length_km": ("length ", "km"),
            "ascent_m": ("ascent ", "m"),
            "duration_h": ("duration ", "h"),
            "radius_km": ("radius ", "km"),
        },
        "names": {
            "length_km": "Length",
            "ascent_m": "Ascent",
            "duration_h": "Duration",
            "radius_km": "Radius",
        },
    },
}
DAYS_QUESTIONS = frozenset(_T[lang]["days_question"] for lang in LANGS)
DAYS_QUESTION = _T["de"]["days_question"]


class TrailLookup(Protocol):
    """What understand needs to know about a long-distance trail (AgentTools provides it)."""

    def start_km(self, trail_id: str, lat: float, lon: float) -> float | None: ...

    def stage_places(self, trail_id: str) -> list[str]: ...


def understand(
    gw: LLMGateway,
    vocab: TagVocabulary,
    message: str,
    previous: HikeRequest | None,
    today: date | None = None,
    trails: TrailLookup | None = None,
    lang: Lang = "de",
) -> Understood:
    raw = parse(gw, vocab, message, previous)
    return resolve(vocab, raw, message, previous, today=today, trails=trails, lang=lang)


def parse(
    gw: LLMGateway, vocab: TagVocabulary, message: str, previous: HikeRequest | None
) -> RawRequest:
    """The one model call of understand(): message -> RawRequest (free-text place and wishes)."""
    user = message
    if previous is not None:
        # model input, not shown to the user: always the German echo the extraction prompt knows
        user = f"Bisherige Anfrage: {echo(previous, vocab)}\nNeue Nachricht: {message}"
    return gw.structured(RawRequest, SYSTEM_PROMPT, user)


def resolve(
    vocab: TagVocabulary,
    raw: RawRequest,
    message: str,
    previous: HikeRequest | None,
    start: ResolvedStart | None = None,
    today: date | None = None,
    trails: TrailLookup | None = None,
    lang: Lang = "de",
) -> Understood:
    """Everything after the model call, in code. `start` (already resolved, e.g. the option the
    user picked after a clarify question) skips resolving raw.start_text. `today` anchors
    relative dates; `trails` answers "is the start on the trail" and lists the stage places.
    Questions and notes come in `lang`."""
    t = _T[lang]
    is_change = raw.intent == "change"
    if is_change and previous is None:
        return Clarify(question=t["change"])

    nums, unread = _scan(message)
    day_change = None
    change_note = None
    if is_change and raw.day_change_day is not None and raw.day_change_direction is not None:
        if previous is None or previous.days is None:  # no multi-day plan to change
            return Clarify(question=t["change"])
        day_change = _day_change(raw, message, nums, previous.days, lang)
        if isinstance(day_change, Clarify):
            return day_change
        if day_change is None:  # never a silent no-op
            change_note = t["change_note"]

    is_multiday = raw.intent == "multiday"
    trail: tuple[Tag, bool] | None = None
    if is_multiday:
        found = _resolve_trail(vocab, raw.trail_text, message, lang)
        if isinstance(found, Clarify):
            return found
        trail = found

    wants_tour = raw.intent in ("day_hike", "multiday", "change")
    start_text = raw.start_text.strip() if raw.start_text else None
    if start is not None:
        start_text = start.label
    elif (wants_tour or raw.intent == "groups") and start_text:
        resolved = _resolve_start(vocab, start_text, lang)
        if isinstance(resolved, Clarify):
            return resolved
        start = resolved
    if trail is not None:
        clarify = _check_multiday_start(vocab, trail[0], start, trails, lang)
        if clarify is not None:
            return clarify

    preferences, unmatched, roundtrips = _resolve_wishes(vocab, raw.wishes, lang)
    constraints, invalid, discarded = _constraints(raw, nums, message, unread, lang)
    unmatched += invalid
    multi, problems, dropped = _multiday_fields(raw, message, nums, today or date.today(), lang)
    unmatched += problems
    if change_note:
        unmatched.append(change_note)
    discarded += dropped
    if is_multiday and multi["days"] is None:
        return Clarify(question=t["days_question"])
    for required in roundtrips:  # a contradicting pair stays and is reported as contradiction
        if not any(c.kind == "roundtrip" and c.required == required for c in constraints):
            constraints.append(Constraint(kind="roundtrip", required=required))
    pace = raw.pace_min_per_km
    if pace is not None and not _written(pace, nums):
        fixed = _pace_from_clock(message, pace)
        if fixed is None:
            discarded += 1
            if unread:
                unmatched.append(t["unsure"].format(t["pace_word"]))
        pace = fixed
    if pace is not None and pace <= 0:
        unmatched.append(_invalid(t["pace_word"], pace, lang))
        pace = None
    unmatched = list(dict.fromkeys(unmatched))
    delta = HikeRequest(
        intent=raw.intent,
        activity=raw.activity or "hike",
        start_text=start_text,
        start=start,
        constraints=constraints,
        preferences=preferences[:MAX_PREFERENCES],
        pace_min_per_km=pace,
        unmatched=unmatched,
        question=(
            (raw.question or message)
            if raw.intent in ("knowledge", "events", "groups")
            else raw.question
        ),
        trail_id=trail[0].rule.trail_id if trail and isinstance(trail[0].rule, LongTrail) else None,
        trail_assumed=bool(trail and trail[1]),
        day_change=day_change,
        discarded_model_numbers=discarded,
        **multi,
    )
    overflow = preferences[MAX_PREFERENCES:]
    if overflow:  # never drop a wish silently
        delta.unmatched += [vocab.label(p.tag_id, lang) for p in overflow]

    req = _merge(previous, delta, raw.activity, vocab, lang) if is_change and previous else delta
    if wants_tour:
        req = _finish(req, vocab)
        if req.activity == "run" and _needs_pace(req):
            return Clarify(question=t["pace"])
    return req


def _invalid(label: str, value: float, lang: Lang = "de") -> str:
    return _T[lang]["invalid"].format(label=label, v=_num(value, lang))


_WORD_NUMBERS = {
    "eins": 1, "zwei": 2, "drei": 3, "vier": 4, "funf": 5, "fuenf": 5, "sechs": 6,
    "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwolf": 12, "zwoelf": 12,
    "dreizehn": 13, "vierzehn": 14, "funfzehn": 15, "fuenfzehn": 15, "sechzehn": 16,
    "siebzehn": 17, "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "dreissig": 30,
    "vierzig": 40, "funfzig": 50, "fuenfzig": 50, "sechzig": 60, "siebzig": 70,
    "achtzig": 80, "neunzig": 90, "hundert": 100,
    "halb": 0.5, "halbe": 0.5, "anderthalb": 1.5,
}  # fmt: skip
_ARTICLES = {"ein", "eine", "einen", "einem", "einer", "eines"}  # only a number inside compounds
_UNITS = {k: v for k, v in _WORD_NUMBERS.items() if v in range(1, 10) and k != "eins"} | {
    "ein": 1,
    "eine": 1,
}
_TENS = {k: v for k, v in _WORD_NUMBERS.items() if v in range(20, 100) and v % 10 == 0}
_ONE_UNIT = re.compile(
    r"\b(?:ein|eine|einen|einem)\s+(?:km|kilometer|stunde|std|h|hm|hohenmeter|minute)\b"
)
_THOUSANDS = re.compile(r"\b\d{1,3}(?:\.\d{3})+\b")
_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_HOURS_MINUTES = re.compile(r"\b(\d{1,2})\s*(?:h|std|stunden?)\s*(\d{1,2})(?!\d)")
_FRACTION = re.compile(
    r"(?<![\d/])(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)(?![\d/])(\s*(?:stunden?|std|h)\b)?"
)
_PART_HOUR = re.compile(r"\b(drei)?viertel\s*(?:stunden?|std|h)\b|\bhalbe?\s+(?:stunden?|std)\b")
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")
_WORDS = re.compile(r"[a-z]+")
# looks like a number word (compound, tens, fraction) that _word_value could not read
_NUMBERISH = re.compile(
    r"[a-z]*(?:einhalb|zig|ssig|zehn|hundert|tausend)|[a-z]*(?:viertel|drittel|achtel)"
)


def _plain(text: str) -> str:
    return text.casefold().replace("ß", "ss").replace("ä", "a").replace("ö", "o").replace("ü", "u")


def _word_value(w: str) -> float | None:
    """Value of a German number word incl. compounds ("fünfundzwanzig", "einhundert",
    "zweieinhalb", "tausend"); None if it is not one."""
    if w in _WORD_NUMBERS or w in _UNITS:
        return float(_WORD_NUMBERS.get(w, _UNITS.get(w)))  # type: ignore[arg-type]
    if w.endswith("einhalb"):
        head = _word_value(w[: -len("einhalb")]) if len(w) > len("einhalb") else None
        return None if head is None else head + 0.5
    for sep, mult in (("tausend", 1000), ("hundert", 100)):
        if sep in w:
            head, _, tail = w.partition(sep)
            tail = tail.removeprefix("und")
            h = 1.0 if head == "" else _word_value(head)
            t = 0.0 if tail == "" else _word_value(tail)
            return None if h is None or t is None else h * mult + t
    unit, _, tens = w.partition("und")
    if unit in _UNITS and tens in _TENS:
        return float(_UNITS[unit] + _TENS[tens])
    return None


def _scan(message: str) -> tuple[set[float], bool]:
    """Every number the user wrote -- digits (ranges "10–14", comma or dot decimals, "1.000",
    "5:30", "2h30", fractions "2 1/2"), German number words (compounds, "zweieinhalb", "viertel
    Stunde") and "ein/eine <Einheit>" -- and whether a number-like word was left unread."""
    text = _plain(message)
    nums: set[float] = set()
    for m in _THOUSANDS.finditer(text):
        nums.add(float(m.group().replace(".", "")))
    text = _THOUSANDS.sub(" ", text)
    for m in _CLOCK.finditer(text):
        nums.add(int(m.group(1)) + int(m.group(2)) / 60)
    for m in _HOURS_MINUTES.finditer(text):
        h, mi = int(m.group(1)), int(m.group(2))
        nums |= {h + mi / 60, h * 60 + mi}
    for m in _FRACTION.finditer(text):
        den = int(m.group(3))
        if den:
            value = int(m.group(1) or 0) + int(m.group(2)) / den
            nums.add(value)
            if m.group(4):
                nums.add(value * 60)
    for m in _PART_HOUR.finditer(text):
        hours = 0.75 if m.group(1) else 0.25 if m.group().startswith("viertel") else 0.5
        nums |= {hours, hours * 60}
    text = _PART_HOUR.sub(" ", text)
    for m in _DIGITS.finditer(text):
        nums.add(float(m.group().replace(",", ".")))
    unread = False
    for w in _WORDS.findall(text):
        value = None if w in _ARTICLES else _word_value(w)
        if value is not None:
            nums.add(value)
        elif _NUMBERISH.fullmatch(w):
            unread = True
    if _ONE_UNIT.search(text):
        nums.add(1.0)
    return nums, unread


def _user_numbers(message: str) -> set[float]:
    return _scan(message)[0]


def _pace_from_clock(message: str, model_pace: float) -> float | None:
    """ "5:30" is 5.5 min/km; a model value close to it (5.3) is a wrong conversion."""
    clocks = [int(m) + int(s) / 60 for m, s in _CLOCK.findall(message)]
    near = [c for c in clocks if abs(c - model_pace) < 0.5]
    return min(near, key=lambda c: abs(c - model_pace)) if near else None


def _written(value: float, nums: set[float], scale: float = 1.0) -> bool:
    """Did the user write this number? (sign ignored: "-5" is invalid, not invented; a duration
    may also be written in minutes.)"""
    wanted = {abs(value)} | ({abs(value) * scale} if scale != 1.0 else set())
    return any(abs(n - w) < 0.01 for n in nums for w in wanted)


def _roundtrip_written(message: str) -> bool:
    """Does the message itself say roundtrip or not (either direction)? "rund 10 km" does not."""
    return bool(_ROUNDTRIP_SAID.search(_plain(message)))


def _constraints(
    raw: RawRequest, nums: set[float], message: str, unread: bool = False, lang: Lang = "de"
) -> tuple[list[Constraint], list[str], int]:
    out: list[Constraint] = []
    invalid: list[str] = []
    discarded = 0
    if raw.roundtrip is not None:
        if _roundtrip_written(message):
            out.append(Constraint(kind="roundtrip", required=raw.roundtrip))
        else:  # like R27: a condition the user never wrote is not set by the model
            discarded += 1
    for kind, lo, hi, approx in (
        ("length_km", raw.length_km_min, raw.length_km_max, raw.length_km_approx),
        ("ascent_m", raw.ascent_m_min, raw.ascent_m_max, raw.ascent_m_approx),
        ("duration_h", raw.duration_h_min, raw.duration_h_max, raw.duration_h_approx),
        ("radius_km", None, raw.radius_km_max, None),
    ):
        bounds = []
        for value in (lo, hi, approx):
            if value is not None and not _written(
                value, nums, 60.0 if kind == "duration_h" else 1.0
            ):
                value, discarded = None, discarded + 1  # R27: invented by the model
                if unread:  # ... or written in a form the parser could not read: never silent
                    invalid.append(_T[lang]["unsure"].format(_T[lang]["names"][kind]))
            if value is not None and value <= 0:
                invalid.append(_invalid(_T[lang]["names"][kind], value, lang))
                value = None
            bounds.append(value)
        lo, hi, approx = bounds
        if lo is not None and lo == hi:  # "min = max = 8" is a single value as well
            lo, hi, approx = None, None, lo
        if lo is None and hi is None and approx is not None:
            out.append(_approx(kind, approx))
        elif lo is not None or hi is not None:  # explicit bound words win over a single value
            out.append(Constraint(kind=kind, min=lo, max=hi))
    return out, invalid, discarded


def _approx(kind: str, value: float) -> Constraint:
    """A single value without a bound word: length and duration get a ±15 % band (shown in the
    echo, never loosened silently); an ascent is a maximum."""
    if kind == "ascent_m":
        return Constraint(kind=kind, max=value)
    lo = round(value * (1 - APPROX_BAND), 2)
    hi = round(value * (1 + APPROX_BAND), 2)
    return Constraint(kind=kind, min=lo, max=hi, approx=value)


def _merge(
    previous: HikeRequest,
    delta: HikeRequest,
    activity: str | None,
    vocab: TagVocabulary,
    lang: Lang = "de",
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
        label = vocab.label(p.tag_id, lang)
        if label not in unmatched:
            unmatched.append(label)
    intent = previous.intent
    if delta.day_change is not None:
        intent = "change"
    elif intent == "change":  # a plan after a day change is a multi-day plan again
        intent = "multiday" if previous.trail_id else "day_hike"
    return HikeRequest(
        intent=intent,
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
        trail_id=previous.trail_id,
        trail_assumed=previous.trail_assumed,
        days=delta.days if delta.days is not None else previous.days,
        day_km=delta.day_km if delta.day_km is not None else previous.day_km,
        start_date=delta.start_date or previous.start_date,
        start_time=delta.start_time or previous.start_time,
        day_change=delta.day_change,
        discarded_model_numbers=delta.discarded_model_numbers,
    )


def _finish(req: HikeRequest, vocab: TagVocabulary) -> HikeRequest:
    """Defaults that must stay visible in echo(): 15 km radius, runnable surface for runs."""
    req = req.model_copy(deep=True)
    if (
        req.start is not None
        and req.start.kind == "place"
        and req.trail_id is None  # a multi-day plan has no search radius
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


def _is_roundtrip_wish(needle: str, tag: Tag | None) -> bool:
    return (tag is not None and tag.id == ROUNDTRIP_TAG) or needle.endswith(_ROUNDTRIP_WORDS)


def _resolve_wishes(
    vocab: TagVocabulary, wishes: list[RawWish], lang: Lang = "de"
) -> tuple[list[Preference], list[str], list[bool]]:
    """Exact or whole-word-prefix match -> tag; anything else -> unmatched (R8).

    A plain string prefix would map "Kinderwagen" to "kinderwagentauglich" (surface tag), which
    does not check what the user asked for, so the prefix must end at a word boundary.
    A roundtrip wish ("Runde", "Laufrunde", …) is the fixed roundtrip condition, returned as
    required True (prefer) or False (avoid), never a preference.
    """
    prefs: dict[str, Preference] = {}
    conflicts: list[str] = []
    unmatched: list[str] = []
    roundtrips: list[bool] = []
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
        if _is_roundtrip_wish(needle, tag):
            roundtrips.append(wish.mode == "prefer")
            continue
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
            unmatched.append(_T[lang]["conflict"].format(label=vocab.label(tag.id, lang)))
    return list(prefs.values()), unmatched, roundtrips


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


SAME_PLACE_KM = 5.0


_MERGE_RANK = {"town": 0, "village": 1, "municipality": 2, "lake": 3}  # peaks never merge


def _drop_shadowed_places(tags: list[Tag]) -> list[Tag]:
    """R25/R26: same-name (ignoring "(…)") town, village, municipality and lake within 5 km are
    one place; keep the highest-priority one (town > village > municipality > lake; cities are towns)."""
    ranked = [
        (t, _MERGE_RANK[t.rule.kind])
        for t in tags
        if isinstance(t.rule, NearPlace) and t.rule.kind in _MERGE_RANK
    ]

    def shadowed(t: Tag, rank: int) -> bool:
        return any(
            r < rank
            and _strip(t.label) == _strip(o.label)
            and haversine_km((t.rule.lat, t.rule.lon), (o.rule.lat, o.rule.lon)) <= SAME_PLACE_KM
            for o, r in ranked
        )

    dropped = {id(t) for t, r in ranked if shadowed(t, r)}
    return [t for t in tags if id(t) not in dropped]


_CITY_SUFFIX = re.compile(r" (?:im|an der|am) .*$")


def _city_for(tags: list[Tag], needle: str) -> list[Tag] | None:
    """The one town (OSM cities are stored as towns) whose name is `needle` or `needle` plus a
    suffix like " im Breisgau"; None if there is not exactly one. Only decides between
    towns and villages: a peak or lake of that name stays a clarify option."""
    if any(
        not isinstance(t.rule, NearPlace) or t.rule.kind not in ("town", "village") for t in tags
    ):
        return None
    towns = [
        t
        for t in tags
        if isinstance(t.rule, NearPlace)
        and t.rule.kind == "town"
        and needle in (_strip(t.label), _CITY_SUFFIX.sub("", _strip(t.label)))
    ]
    return towns if len(towns) == 1 else None


def _resolve_start(vocab: TagVocabulary, text: str, lang: Lang = "de") -> ResolvedStart | Clarify:
    tr = _T[lang]
    cands = [t for t in vocab.all() if t.category in ("place", "area")]
    best: list[Tag] = []
    shown = _display_names(cands, lang)
    if "(" in text or " – " in text:  # user gave the disambiguating suffix: full label first
        full = fold(text)
        shown_all = [_display_names(cands, x) for x in LANGS]  # a clicked option of either language
        best = [
            t
            for t in cands
            if full in _terms(t)
            or any(
                full in (fold(sh[t.id]), fold(_with_kind(t, x))) for sh, x in zip(shown_all, LANGS)
            )
        ]
    if not best:
        needle = _strip(text)
        tiers: dict[int, list[Tag]] = {}
        for t in cands:
            terms = [_strip(x) for x in [t.label, *t.synonyms] if _strip(x)]
            if isinstance(t.rule, NearPlace) and t.rule.kind == "town":  # "Freiburg im Breisgau"
                terms.append(_CITY_SUFFIX.sub("", _strip(t.label)))
            tier = _tier(needle, terms)
            if tier is not None:
                tiers.setdefault(tier, []).append(t)
        best = tiers[min(tiers)] if tiers else []
    best = _drop_shadowed_places(best)
    if len(best) > 1:  # "Freiburg" = the city "Freiburg im Breisgau" over a same-name village
        best = _city_for(best, _strip(text)) or best
    if len(best) == 1:
        return _to_start(best[0])
    if best:
        options = _options(best, shown, lang)[:MAX_OPTIONS]
        return Clarify(
            question=tr["ambiguous"].format(options=_join_or(options, lang), text=text),
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
    msg = tr["unknown_place"].format(text=text)
    if close:
        msg += tr["did_you_mean"].format(options=_join_or(close, lang))
    else:
        msg += tr["name_place"].format(regions=_REGION_NAMES[lang])
    return Clarify(question=msg, options=close)


def resolve_option(vocab: TagVocabulary, option: str) -> ResolvedStart | None:
    """The start behind one clarify option (exact display name or label, in either language),
    if unique."""
    cands = [t for t in vocab.all() if t.category in ("place", "area")]
    needle = fold(option)
    hits = [
        t
        for lang in LANGS
        for t, name in ((t, _display_names(cands, lang)[t.id]) for t in cands)
        if fold(name) == needle
    ]
    hits = list({t.id: t for t in hits}.values())
    if not hits:
        hits = list(
            {
                t.id: t for lang in LANGS for t in cands if fold(_with_kind(t, lang)) == needle
            }.values()
        )
    if not hits:
        hits = [t for t in cands if fold(t.label) == needle]
    return _to_start(hits[0]) if len(hits) == 1 else None


def _kind_name(t: Tag, lang: Lang = "de") -> str | None:
    kinds = _T[lang]["kinds"]
    if isinstance(t.rule, Area):
        return kinds["area"]
    kind = t.rule.kind if isinstance(t.rule, NearPlace) else None
    return kinds.get(kind or "")


def _with_kind(t: Tag, lang: Lang = "de") -> str:
    """Label with kind: "Feldberg (Gipfel)", "Feldberg (Schwarzwald) – Ort"; plain if unknown."""
    kind = _kind_name(t, lang)
    if kind is None:
        return t.label
    return f"{t.label} – {kind}" if "(" in t.label else f"{t.label} ({kind})"


def _options(tags: list[Tag], shown: dict[str, str], lang: Lang = "de") -> list[str]:
    """Clarify options: places that share a base name (without "(…)") name their kind (R6/R12),
    so "Feldberg" vs "Feldberg (Schwarzwald)" says which one is the summit."""
    bases: dict[str, int] = {}
    for t in tags:
        bases[_strip(t.label)] = bases.get(_strip(t.label), 0) + 1
    out = []
    for t in tags:
        name = shown[t.id]
        if bases[_strip(t.label)] > 1 and name == t.label:
            name = _with_kind(t, lang)
        out.append(name)
    return out


def _display_names(tags: list[Tag], lang: Lang = "de") -> dict[str, str]:
    """Label per tag id; identical labels get the kind in parentheses to stay distinct."""
    counts: dict[str, int] = {}
    for t in tags:
        counts[t.label] = counts.get(t.label, 0) + 1
    out = {}
    for t in tags:
        out[t.id] = t.label
        if counts[t.label] > 1:
            kind = t.rule.kind if isinstance(t.rule, NearPlace) else None
            out[t.id] = f"{t.label} ({_T[lang]['kinds'].get(kind or '', t.id)})"
    return out


def _to_start(tag: Tag) -> ResolvedStart:
    rule = tag.rule
    if isinstance(rule, Area):
        return ResolvedStart(kind="area", tag_id=tag.id, label=tag.label, bbox=rule.bbox)
    lat = rule.lat if isinstance(rule, NearPlace) else None
    lon = rule.lon if isinstance(rule, NearPlace) else None
    return ResolvedStart(kind="place", tag_id=tag.id, label=tag.label, lat=lat, lon=lon)


def _join_or(items: list[str], lang: Lang = "de") -> str:
    quoted = [f"„{i}“" for i in items]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + f"{_T[lang]['or']}{quoted[-1]}"


# --- echo ---------------------------------------------------------------------------------


def _num(x: float, lang: Lang = "de") -> str:
    text = f"{x:g}"
    return text.replace(".", ",") if lang == "de" else text


def _range(c: Constraint, unit: str, prefix: str = "", lang: Lang = "de") -> str:
    t = _T[lang]
    if c.min is not None and c.max is not None:
        about = f" (≈ {_num(c.approx, lang)} {unit})" if c.approx is not None else ""
        return f"{prefix}{_num(c.min, lang)}–{_num(c.max, lang)} {unit}{about}"
    if c.min is not None:
        return prefix + t["min"].format(v=_num(c.min, lang), unit=unit)
    return prefix + t["max"].format(v=_num(c.max, lang), unit=unit)  # type: ignore[arg-type]


def echo(req: HikeRequest, vocab: TagVocabulary, lang: Lang = "de") -> str:
    """ "Verstanden: …" / "Understood: …" sentence in the reply language, built from fields only."""
    t = _T[lang]
    parts = [t["intents"][req.intent]]
    if req.intent not in ("events", "groups"):
        parts.append(t["running"] if req.activity == "run" else t["walking"])
    if req.trail_id is not None:
        parts.append(_trail_echo(req, vocab, lang))
    if req.start is not None:
        parts.append(t["start"].format(label=req.start.label))
    elif req.start_text:
        parts.append(t["start_unresolved"].format(label=req.start_text))
    parts += _multiday_echo(req, lang)
    for c in req.constraints:
        if c.kind == "roundtrip":
            parts.append(t["roundtrip"] if c.required else t["no_roundtrip"])
        else:
            prefix, unit = t["labels"][c.kind]
            parts.append(_range(c, unit, prefix, lang))
    if req.pace_min_per_km is not None:
        parts.append(t["pace_echo"].format(v=_num(req.pace_min_per_km, lang)))
    text = t["understood"] + ", ".join(parts)
    wishes = []
    for p in req.preferences:
        label = vocab.label(p.tag_id, lang)
        wishes.append(
            t["weight"].format(label=label, w=p.weight)
            if p.mode == "prefer"
            else t["without"].format(label=label)
        )
    if wishes:
        text += t["wishes"] + ", ".join(wishes)
    if req.unmatched:
        text += t["unchecked"] + ", ".join(req.unmatched)
    if req.question and req.intent in ("knowledge", "events", "groups"):
        text += t["question"].format(q=req.question)
    return text + "."


def _trail_echo(req: HikeRequest, vocab: TagVocabulary, lang: Lang = "de") -> str:
    t = _T[lang]
    tag = vocab.get(f"trail:{req.trail_id}")
    label = tag.label if tag else str(req.trail_id)
    if req.trail_id == "westweg-west":
        key = "west" if req.trail_assumed else "west_only"
        return t[key].format(label=label)
    return label


def _multiday_echo(req: HikeRequest, lang: Lang = "de") -> list[str]:
    t = _T[lang]
    parts = []
    if req.days is not None:
        parts.append(t["days"].format(n=req.days) if req.days != 1 else t["day"])
    if req.trail_id is not None:  # defaults stay visible
        std = t["default"] if req.day_km is None else ""
        parts.append(t["day_goal_echo"].format(v=_num(req.day_km or DEFAULT_DAY_KM, lang), std=std))
    if req.start_date is not None:
        parts.append(t["on_date"].format(d=req.start_date.strftime(_DATE_FMT[lang])))
    if req.trail_id is not None:
        std = t["default"] if req.start_time is None else ""
        parts.append(t["start_time"].format(t=req.start_time or DEFAULT_START_TIME, std=std))
    if req.day_change is not None:
        word = t["shorter"] if req.day_change.change == "shorter" else t["longer"]
        parts.append(t["day_change"].format(n=req.day_change.day, word=word))
    return parts


# --- multi-day ----------------------------------------------------------------------------

_DIRECTION_WORDS = {
    "shorter": re.compile(r"\b(?:kurzer|weniger)\b"),
    "longer": re.compile(r"\b(?:langer|mehr)\b"),  # whole words: not "Mehrtagestour"
}
_DAYS_PHRASE = re.compile(r"\b(\d+|[a-z]+?)\s*-?\s*(?:tagen|tage|tages|tagig|tagestour|tag)\b")
_PACE_UNIT = re.compile(r"\s*min\b")
_MONTHS = {
    "januar": 1, "februar": 2, "marz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}  # fmt: skip
_DATE_NAMED = re.compile(r"\b(\d{1,2})\.?\s*(" + "|".join(_MONTHS) + r")\b(?:\s*(\d{4}))?")
_DATE_NUMERIC = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.(?:\s*(\d{4}|\d{2})\b)?")
_TIME_UHR = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*uhr\b")
_TIME_WORD_UHR = re.compile(r"\b([a-z]+)\s+uhr\b")
_TIME_AT = re.compile(r"\b(?:um|ab|gegen)\s+(\d{1,2}):(\d{2})\b")
_MONTH_WORD = re.compile(r"\b(?:" + "|".join(_MONTHS) + r")\b")


def _days_written(days: int, text: str) -> bool:
    """The count is tied to a day word: "3 Tage", "drei Tage", "dreitägig", "3-Tages-Tour"."""
    for m in _DAYS_PHRASE.finditer(text):
        word = m.group(1)
        value = float(word) if word.isdigit() else _word_value(word)
        if value is not None and value == days:
            return True
    return False


def _day_change(
    raw: RawRequest, message: str, nums: set[float], plan_days: int, lang: Lang = "de"
) -> DayChange | Clarify | None:
    """ "Tag 3 kürzer": the day number must be written, the direction word as well."""
    day, direction = raw.day_change_day, raw.day_change_direction
    if day is None or direction is None:
        return None
    text = _plain(message)
    if not _written(day, nums) or not _DIRECTION_WORDS[direction].search(text):
        return None
    if not MIN_DAYS <= day <= plan_days:
        return Clarify(question=_T[lang]["plan_days"].format(n=plan_days))
    return DayChange(day=day, change=direction)


def _resolve_trail(
    vocab: TagVocabulary, text: str | None, message: str, lang: Lang = "de"
) -> tuple[Tag, bool] | Clarify:
    """Trail tag by name (the model's wording first, then the message itself); `assumed` is True
    when only the bare name was given and another variant would also fit ("Westweg")."""
    cands = [t for t in vocab.all() if t.category == "trail"]
    for source in (text, message):
        if not source:
            continue
        haystack = f" {fold(source)} "
        hits = [(term, t) for t in cands for term in _terms(t) if f" {term} " in haystack]
        if hits:
            term, tag = max(hits, key=lambda h: len(h[0]))
            siblings = [
                o
                for o in cands
                if o is not tag and any(x.startswith(term + " ") for x in _terms(o))
            ]
            return tag, bool(siblings)
    shown = [t.label for t in cands]
    if text and text.strip():
        question = _T[lang]["unknown_trail"].format(text=text.strip())
        return Clarify(question=question, options=shown)
    return Clarify(question=_T[lang]["which_trail"], options=shown)


def _trail_name(tag: Tag) -> str:
    return tag.label.split()[0]


def _check_multiday_start(
    vocab: TagVocabulary,
    trail: Tag,
    start: ResolvedStart | None,
    trails: TrailLookup | None,
    lang: Lang = "de",
) -> Clarify | None:
    """The start must be a place on the trail (<= 2 km from the line); otherwise ask for a
    stage place of that trail (names from the stages table). Only stage places that resolve to
    one known place are offered: an option must work when the user clicks it."""
    trail_id = trail.rule.trail_id if isinstance(trail.rule, LongTrail) else ""
    places = trails.stage_places(trail_id) if trails is not None else []
    options = [p for p in places if _is_point(_resolve_start(vocab, p, lang))]
    if start is None or start.lat is None or start.lon is None:
        return Clarify(question=_T[lang]["start_question"], options=options)
    if trails is not None and trails.start_km(trail_id, start.lat, start.lon) is None:
        question = _T[lang]["off_trail"].format(label=start.label, trail=_trail_name(trail))
        return Clarify(question=question, options=options)
    return None


def _is_point(res: ResolvedStart | Clarify) -> bool:
    return isinstance(res, ResolvedStart) and res.lat is not None and res.lon is not None


def _multiday_fields(
    raw: RawRequest, message: str, nums: set[float], today: date, lang: Lang = "de"
) -> tuple[dict, list[str], int]:
    """days, day_km, start_date, start_time -- each only if the message says so (R27)."""
    text = _plain(message)
    out: dict = {"days": None, "day_km": None, "start_date": None, "start_time": None}
    problems: list[str] = []
    discarded = 0
    if raw.days is not None:
        if not _days_written(raw.days, text):
            discarded += 1
        elif not MIN_DAYS <= raw.days <= MAX_DAYS:
            problems.append(_T[lang]["days_invalid"].format(n=raw.days, lo=MIN_DAYS, hi=MAX_DAYS))
        else:
            out["days"] = raw.days
    if raw.day_km is not None:
        if not _written(raw.day_km, nums):
            discarded += 1
        elif raw.day_km <= 0:
            problems.append(_invalid(_T[lang]["day_goal"], raw.day_km, lang))
        else:
            out["day_km"] = raw.day_km
    when, problem = _parse_date(text, today, lang)
    out["start_date"] = when
    if problem:
        problems.append(problem)
    elif when is None and raw.start_date is not None:
        discarded += 1
        if _MONTH_WORD.search(text):  # a date-like wording we could not read: never silent
            problems.append(_T[lang]["unsure"].format(_T[lang]["date_word"]))
    clock, problem = _parse_time(text, lang)
    out["start_time"] = clock
    if problem:
        problems.append(problem)
    elif clock is None and raw.start_time is not None:
        discarded += 1
    return out, problems, discarded


def _parse_date(text: str, today: date, lang: Lang = "de") -> tuple[date | None, str | None]:
    """Date from the (folded) message: "12. Juni", "12.6.", "12.06.2027", heute/morgen/übermorgen.
    No year: the next such day from today on."""
    day = month = year = None
    if m := _DATE_NAMED.search(text):
        day, month, year = int(m.group(1)), _MONTHS[m.group(2)], m.group(3)
    elif m := _DATE_NUMERIC.search(text):
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
    if day is not None:
        label = f"{day}.{month}."
        if year is not None and len(year) == 2:
            year = "20" + year
        found = None
        # no year: the next year (from this one on) in which the day exists and is not past
        for y in [int(year)] if year else range(today.year, today.year + 9):
            try:
                found = date(y, month, day)
            except ValueError:
                continue
            if year or found >= today:
                break
            found = None
        if found is None:
            return None, _T[lang]["no_such_date"].format(label=label)
        if found < today:
            return None, _T[lang]["past_date"].format(d=found.strftime(_DATE_FMT[lang]))
        return found, None
    for word, offset in (("ubermorgen", 2), ("morgen", 1), ("heute", 0)):
        if re.search(rf"\b{word}\b", text):
            return today + timedelta(days=offset), None
    return None, None


def _parse_time(text: str, lang: Lang = "de") -> tuple[time | None, str | None]:
    """Start time: "8 Uhr", "8:30 Uhr", "acht Uhr", "um 8:30"."""
    hour = minute = None
    if m := _TIME_UHR.search(text):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    elif (m := _TIME_AT.search(text)) and not _PACE_UNIT.match(text, m.end()):
        hour, minute = int(m.group(1)), int(m.group(2))  # "um 5:30 min/km" is a pace
    elif m := _TIME_WORD_UHR.search(text):
        value = _word_value(m.group(1))
        if value is not None and value == int(value):
            hour, minute = int(value), 0
    if hour is None or minute is None:
        return None, None
    if hour > 23 or minute > 59:
        return None, _T[lang]["bad_time"].format(h=hour, m=minute)
    return time(hour, minute), None
