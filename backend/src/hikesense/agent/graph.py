"""Agent flow (LangGraph):
guard → understand → search | multiday | react | groups | events | fixed reply → answer → ground
→ log.

Every number shown comes from a tool result of the round: the model only words the answer, the
grounding check replaces unsupported numbers, and the code prefixes the honest fallback sentence.
A multi-day plan comes from the deterministic planner (multiday.py); the model only words it.
Groups and running events get a code-written answer; their items carry the sources.
Events are streamed with LangGraph's custom stream writer; the conversation state (last request,
open clarify question, last multi-day plan) lives in a MemorySaver keyed by user hash + thread_id
and holds only plain JSON data.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from functools import cached_property
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from hikesense import chatlog
from hikesense.adapters.open_meteo import SOURCE_ID as SOURCE_WEATHER
from hikesense.adapters.open_meteo import DayWeather, weather_source
from hikesense.agent.constraints import (
    ConstraintResult,
    PreferenceMatch,
    Scored,
    contradiction,
    format_deviation,
)
from hikesense.agent.events import CalendarLink, EventsResult, VerifiedRace, skip_reason
from hikesense.agent.explain import candidate_rows
from hikesense.agent.grounding import (
    Evidence,
    grounding_check,
    has_number,
    strip_unsat_claims,
    strip_weather_claims,
)
from hikesense.agent.multiday import (
    NEAR_M,
    DayPlan,
    MultidayPlan,
    RainVariant,
    access_straight,
    no_rain_variant,
)
from hikesense.agent.prompts import (
    ANSWER_SYSTEM,
    ANSWER_SYSTEM_EN,
    PLAN_SYSTEM,
    PLAN_SYSTEM_EN,
    REACT_SYSTEM,
    REACT_SYSTEM_EN,
    answer_system,
    plan_system,
    react_system,
)
from hikesense.agent.reply_lang import reply_lang
from hikesense.agent.request import (
    MAX_DAYS,
    Clarify,
    Constraint,
    HikeRequest,
    RawRequest,
    ResolvedStart,
)
from hikesense.agent.texts import Lang, Texts, texts
from hikesense.agent.tools import (
    DEFAULT_GROUP_RADIUS_KM,
    TOOL_SPECS,
    AgentTools,
    GroupBrief,
    KnowledgeHit,
    LodgingBrief,
    SourceBrief,
    StartNotOnTrail,
    TrailDetails,
)
from hikesense.agent.understand import (
    DAY_ROUNDS_OPTIONS,
    DAYS_QUESTIONS,
    echo,
    has_weather_word,
    parse,
    resolve,
    resolve_option,
    start_of,
)
from hikesense.agent.understand import SYSTEM_PROMPT as UNDERSTAND_SYSTEM
from hikesense.agent.weather import (
    NoForecast,
    WeatherWish,
    Window,
    best_windows,
    is_rain_day,
    localize,
    matches,
    no_forecast,
    reason_text,
    score,
)
from hikesense.chatlog import ChatLogEntry
from hikesense.config import Settings
from hikesense.guard import leaks_system_prompt, looks_like_injection, sanitize_text
from hikesense.llm.gateway import LLMGateway
from hikesense.llm.usage import BudgetExceeded, LLMError, LLMUsage, metered
from hikesense.numfmt import de, fmt
from hikesense.preferences import with_saved
from hikesense.tags.vocabulary import TagVocabulary, fold
from hikesense.trace import Trace, TracedTools, traced

log = logging.getLogger(__name__)

HISTORY_KEEP = 6  # current message plus up to 5 earlier ones, for the log

__all__ = [
    "AgentDeps",
    "ChatEvent",
    "ClarifyEvent",
    "DoneEvent",
    "ErrorEvent",
    "EventsEvent",
    "GroupsEvent",
    "PlanEvent",
    "ResultsEvent",
    "SourcesEvent",
    "TokenEvent",
    "TourCard",
    "UnderstoodEvent",
    "build_graph",
    "run_chat",
]

TOUR_INTENTS = ("day_hike", "change")
_PROMPTS = (
    ANSWER_SYSTEM,
    PLAN_SYSTEM,
    REACT_SYSTEM,
    ANSWER_SYSTEM_EN,
    PLAN_SYSTEM_EN,
    REACT_SYSTEM_EN,
    UNDERSTAND_SYSTEM,
)
_CHUNK = re.compile(r"\S+\s*|\s+")
_RAIN_ASK = re.compile(r"regen\s?variante", re.IGNORECASE)
_RAIN_DAYS = re.compile(
    r"\btag(?:e|en)?\s*(\d{1,2}(?:\s*(?:,|und|&|bis|–|-)\s*\d{1,2})*)", re.IGNORECASE
)
_DAY_NUMS = re.compile(r"(\d{1,2})(?:\s*(bis|–|-)\s*(\d{1,2}))?")
# a fresh request, not a follow-up on the stored plan: "3 Tage", "ab Hinterzarten", "Westweg"
_DAYS_PHRASE = re.compile(
    r"\b(?:\d+|ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|dreizehn|vierzehn)"
    r"\s*-?\s*(?:tage|tagen|tägig|tagig|tagestour)\b",
    re.IGNORECASE,
)
_NEW_START = re.compile(r"\b(?:ab|von|in|nach|bei|[Ss]tart(?:ort)?)\s+[A-ZÄÖÜ]")
_GROUP_KINDS = (  # words in the message -> kind filter (first hit wins)
    (re.compile(r"lauftreff|laufgruppe|laufverein", re.IGNORECASE), "lauftreff"),
    (re.compile(r"alpenverein|\bdav\b", re.IGNORECASE), "alpenverein"),
    (re.compile(r"schwarzwaldverein|wanderverein|wandergruppe", re.IGNORECASE), "wanderverein"),
)
_WEEKDAY = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}
_DATE_FMT = {"de": "%d.%m.%Y", "en": "%d/%m/%Y"}
_LABEL = {
    "de": {
        "length_km": "Länge",
        "ascent_m": "Höhenmeter",
        "duration_h": "Dauer",
        "radius_km": "Entfernung",
        "roundtrip": "Rundweg",
    },
    "en": {
        "length_km": "length",
        "ascent_m": "ascent",
        "duration_h": "duration",
        "radius_km": "distance",
        "roundtrip": "round walk",
    },
}
# labels of the facts the model gets (_search_data, _plan_data), in the language of the answer
_D = {
    "de": {
        "fallback_head": "Ausweichtouren (je genau eine Bedingung verletzt):",
        "match_head": "Passende Touren (nach Vorlieben sortiert):",
        "time_run": "Laufzeit",
        "time_walk": "Gehzeit",
        "length": "Länge {v} km",
        "length_unknown": "Länge unbekannt",
        "ascent": "Anstieg {v} Hm",
        "ascent_unknown": "Anstieg unbekannt",
        "time": "{word} {v} h",
        "time_none": "Zeit: keine Angabe",
        "distance": "Entfernung zum Start {v} km",
        "conditions": "Bedingungen",
        "met": "Vorlieben erfüllt",
        "missing": "Vorlieben fehlen",
        "avoided": "enthält Gemiedenes",
        "unmatched": "Nicht prüfbar",
        "ok": "{label} erfüllt",
        "unknown": "{label} unbekannt (nicht prüfbar)",
        "fail": "{label} nicht erfüllt: {dev}",
        "no_coords_place": "diesem Ort",
        "no_contra": "Keine Tour erfüllt alle Wünsche, weil {contra}",
        "near": "Knapp daneben",
        "day": "Tag",
        "days_one": "Tag {a}",
        "days_range": "Tag {a}–{b}",
        "days_list": "Tag {head} und {last}",
        "weather": "Wetter",
        "weather_nodate": "ohne Datum keine Vorhersage",
        "all_times": "Alle Zeiten ohne Pausen (Gehzeit nach DIN 33466)",
        "no_forecast_asked": "Für {days} keine Vorhersage abgefragt",
        "no_rain_calc": "Für {days} keine Regenvariante berechnet",
        "clock": "{t:%H:%M} Uhr",
        "no_forecast": "keine Vorhersage",
        "weather_unknown": "Wetterlage unbekannt",
        "temp": "{a} bis {b} °C",
        "precip": "Niederschlag {v} mm",
        "precip_unknown": "Niederschlag unbekannt",
        "rain_prob": "Regenwahrscheinlichkeit {v} %",
        "access": " (davon Zuweg {v} km Luftlinie)",
        "d_ascent": "Anstieg {v} Hm",
        "d_descent": "Abstieg {v} Hm",
        "d_time": "Gehzeit {v} h",
        "d_start": "Start {c}",
        "d_arrival": "Ankunft {c}",
        "d_arrival_none": "Ankunft: keine (siehe Hinweis)",
        "stop": "; Ziel: {name}, {dist} m vom Weg",
        "stop_noname": "Unterkunft ohne Namen",
        "stop_end": "; Ziel: Wegende",
        "gap": "; Lücke (steht schon im Hinweis): {gap}",
        "rain_variant": (
            "; Regenvariante: bis {station}, {km} km, {asc} Hm, Gehzeit {h} h – {note}"
        ),
        "rain_none": "; Regenvariante: {note}",
        "plan_head": "Mehrtagesplan {trail}",
        "plan_from": " ab {start}",
        "plan_tail": ", {n} Tag(e), Tagesziel {km} km:",
        "plan_notes": "Hinweise (schreibt das Programm schon davor, nicht wiederholen):",
        "question": "Frage: {q}\nWerkzeug-Ergebnisse:\n",
        "as_of": "Stand: {d}",
        "unit_hm": "Hm",
    },
    "en": {
        "fallback_head": "Fallback tours (each violates exactly one condition):",
        "match_head": "Matching tours (sorted by preferences):",
        "time_run": "running time",
        "time_walk": "walking time",
        "length": "length {v} km",
        "length_unknown": "length unknown",
        "ascent": "ascent {v} m",
        "ascent_unknown": "ascent unknown",
        "time": "{word} {v} h",
        "time_none": "time: not stated",
        "distance": "distance to the start {v} km",
        "conditions": "conditions",
        "met": "preferences met",
        "missing": "preferences missing",
        "avoided": "contains avoided features",
        "unmatched": "Cannot be checked",
        "ok": "{label} met",
        "unknown": "{label} unknown (cannot be checked)",
        "fail": "{label} not met: {dev}",
        "no_coords_place": "this place",
        "no_contra": "No tour meets all your wishes, because {contra}",
        "near": "Near miss",
        "day": "Day",
        "days_one": "Day {a}",
        "days_range": "Day {a}–{b}",
        "days_list": "Day {head} and {last}",
        "weather": "Weather",
        "weather_nodate": "no forecast without a date",
        "all_times": "All times without breaks (walking time per DIN 33466)",
        "no_forecast_asked": "No forecast requested for {days}",
        "no_rain_calc": "No rain variant calculated for {days}",
        "clock": "{t:%H:%M}",
        "no_forecast": "no forecast",
        "weather_unknown": "weather unknown",
        "temp": "{a} to {b} °C",
        "precip": "precipitation {v} mm",
        "precip_unknown": "precipitation unknown",
        "rain_prob": "chance of rain {v} %",
        "access": " (of which access path {v} km as the crow flies)",
        "d_ascent": "ascent {v} m",
        "d_descent": "descent {v} m",
        "d_time": "walking time {v} h",
        "d_start": "start {c}",
        "d_arrival": "arrival {c}",
        "d_arrival_none": "arrival: none (see note)",
        "stop": "; destination: {name}, {dist} m from the trail",
        "stop_noname": "unnamed accommodation",
        "stop_end": "; destination: end of the trail",
        "gap": "; gap (already in the note): {gap}",
        "rain_variant": (
            "; rain variant: to {station}, {km} km, {asc} m ascent, walking time {h} h – {note}"
        ),
        "rain_none": "; rain variant: {note}",
        "plan_head": "Multi-day plan {trail}",
        "plan_from": " from {start}",
        "plan_tail": ", {n} day(s), daily target {km} km:",
        "plan_notes": "Notes (the program already writes these before your answer, do not repeat them):",
        "question": "Question: {q}\nTool results:\n",
        "as_of": "As of {d}",
        "unit_hm": "m",
    },
}


# --- events -------------------------------------------------------------------------------


class TourCard(BaseModel):
    trail_id: str
    name: str
    length_km: float | None
    ascent_m: int | None
    duration_h: float | None  # None: unknown, or a run without pace
    distance_km: float | None  # None: area start (the tour lies in the area, no distance)
    cover_thumb_url: str | None = None
    cover_author: str | None = None
    cover_license: str | None = None
    cover_license_url: str | None = None
    cover_page_url: str | None = None
    cover_url: str | None = None  # large version of the cover (page backdrop)
    cover_nearby: bool = False  # cover from the nearest photographed trail (shown as such)
    results: list[ConstraintResult]
    deviation_text: str | None = None
    near_miss: bool = False  # misses one hard condition by a little; deviation_text says which
    preference: PreferenceMatch


class ChatEvent(BaseModel):
    """One streamed event; `type` names it (understood, clarify, results, token, sources, done,
    error). Each kind is a subclass; all are pydantic and JSON-serialisable for the SSE API."""

    type: str


class UnderstoodEvent(ChatEvent):
    type: Literal["understood"] = "understood"
    text: str
    request: HikeRequest
    labels: dict[str, str] = {}  # tag_id -> vocabulary label, for every tag the request names


class ClarifyEvent(ChatEvent):
    type: Literal["clarify"] = "clarify"
    question: str
    options: list[str]


class ResultsEvent(ChatEvent):
    type: Literal["results"] = "results"
    cards: list[TourCard]
    fallback_reason: str | None
    labels: dict[str, str] = {}  # tag_id -> vocabulary label, for every tag the cards name


class WeatherDay(BaseModel):
    date: date
    match: bool | None  # None: a value needed for the decision is missing
    weather: DayWeather  # words in the reply language


class WeatherDaysEvent(ChatEvent):
    """Days that fit a weather wish at the start place (day hikes). `best_only`: no day fits,
    `days` are the closest ones. `note`: why the forecast is missing or partial."""

    type: Literal["weather_days"] = "weather_days"
    wish: WeatherWish
    place: str
    days: list[WeatherDay]
    best_only: bool
    note: str | None = None


class PlanEvent(ChatEvent):
    """A multi-day plan with the forecast per day (only days with a date) and the rain variant
    per day (rain days, or the day asked for; None = no station on the trail). Keys: day number."""

    type: Literal["plan"] = "plan"
    plan: MultidayPlan
    weather: dict[int, DayWeather | NoForecast] = {}
    rain: dict[int, RainVariant | None] = {}
    labels: dict[str, str] = {}  # tag_id -> vocabulary label (the trail)
    start_name: str | None = None  # the plan's start place (day 1, saved title); None: none named


class GroupsEvent(ChatEvent):
    """Groups of the curated list near the place, nearest first; `checked_note` names the
    oldest check date ("Stand: 01.03.2026"). No persons, no dates of events."""

    type: Literal["groups"] = "groups"
    groups: list[GroupBrief]
    checked_note: str


class EventsEvent(ChatEvent):
    """Official running events found live: every field with a value is quoted verbatim on the
    race's `source_url` (None: „nicht angegeben“); `fallback` are calendar links when no race is
    shown. Nothing of it is stored."""

    type: Literal["events"] = "events"
    events: list[VerifiedRace]
    fallback: list[CalendarLink]
    note: str


class TokenEvent(ChatEvent):
    type: Literal["token"] = "token"
    text: str


class SourcesEvent(ChatEvent):
    type: Literal["sources"] = "sources"
    sources: list[SourceBrief]


class DoneEvent(ChatEvent):
    type: Literal["done"] = "done"
    usage: LLMUsage
    unsupported: int  # numbers only
    unsupported_names: list[str] = []
    unsat_claims_removed: int = 0  # "Keine Tour erfüllt alle Wünsche" written without a fallback


class ErrorEvent(ChatEvent):
    type: Literal["error"] = "error"
    message: str
    code: str | None = None  # machine-readable reason for the web app, e.g. "guest_limit"


# --- deps and state -----------------------------------------------------------------------


@dataclass
class AgentDeps:
    tools: AgentTools
    gateway: LLMGateway
    vocab: TagVocabulary
    settings: Settings
    checkpointer: MemorySaver = field(default_factory=MemorySaver)
    trail_names: list[str] = field(default_factory=list)  # all tour names, for grounding (R21)
    today: Callable[[], date] = date.today  # anchors relative dates ("morgen") in requests

    @cached_property
    def graph(self) -> Any:
        return build_graph(self)


class State(TypedDict, total=False):
    message: str
    lang: Lang  # reply language of this turn (set per turn, never read from the checkpoint)
    request: dict | None  # last tour request (for "change"), persists per thread
    pending: dict | None  # open clarify question with the partial request, persists per thread
    last_tours: list[dict] | None  # trail_id + name of the last result cards, persists per thread
    plan: dict | None  # last multi-day plan (MultidayPlan JSON), persists per thread
    # per message:
    route: str
    intent: str | None
    activity: str | None
    current: dict | None
    clarify: dict | None
    reply: str | None
    reason: str | None
    prefix: str | None  # code-written lines put before the answer verbatim (multi-day notes)
    near_sentence: (
        str | None
    )  # code-written "Knapp daneben: ..." sentence, appended after the answer
    weather_sentence: str | None  # code-written weather day finder sentence, after the answer
    weather_days: dict | None  # the finder's result, for the log
    weather_guard: str | None  # the wish whose words the draft must not use (not met / unknown)
    plan_request: dict | None  # the request behind `plan` (its start), persists per thread
    rain_days: list[int] | None  # "Regenvariante für Tag 2 und 3" on the stored plan
    data: str | None
    system: str | None  # answer prompt for `data` (None: ANSWER_SYSTEM)
    draft: str | None
    fixed: str | None
    evidence: dict
    sources: list[dict]
    tool_calls: int
    guard: str | None
    unsupported: int
    unsupported_names: list[str]
    unsat_claims_removed: int
    discarded_numbers: int
    history: list[str]  # the last messages of the thread (sanitised), persists per thread
    final_text: str | None  # the text the user saw (not "answer": that is a node name)
    candidates: list[dict]  # candidate_rows of the search, for the log


def _turn(message: str, lang: Lang = "de") -> State:
    return State(
        message=message,
        lang=lang,
        route="",
        intent=None,
        activity=None,
        current=None,
        clarify=None,
        reply=None,
        reason=None,
        near_sentence=None,
        weather_sentence=None,
        weather_days=None,
        weather_guard=None,
        prefix=None,
        rain_days=None,
        data=None,
        system=None,
        draft=None,
        fixed=None,
        evidence={"numbers": [], "names": []},
        sources=[],
        tool_calls=0,
        guard=None,
        unsupported=0,
        unsupported_names=[],
        unsat_claims_removed=0,
        discarded_numbers=0,
        final_text=None,
        candidates=[],
    )


def _emit(event: ChatEvent) -> None:
    get_stream_writer()(event)


def _de(x: float, decimals: int = 1) -> str:
    return de(x, decimals)  # half-up, like the grounding check


# --- search: cards, facts for the model, evidence -----------------------------------------


def _card(s: Scored, area: bool, near_miss: bool = False, lang: Lang = "de") -> TourCard:
    c = s.candidate
    return TourCard(
        trail_id=c.trail_id,
        name=c.name,
        length_km=c.length_km,
        ascent_m=c.ascent_m,
        duration_h=s.duration_h,
        distance_km=None if area else c.distance_km,
        cover_thumb_url=c.cover_thumb_url,
        cover_author=c.cover_author,
        cover_license=c.cover_license,
        cover_license_url=c.cover_license_url,
        cover_page_url=c.cover_page_url,
        cover_url=c.cover_url,
        cover_nearby=c.cover_nearby,
        results=[_as_float(r) for r in s.results],
        deviation_text=format_deviation(s.violated, lang) if s.violated else None,
        near_miss=near_miss,
        preference=s.preference,
    )


def _near_sentence(near: list[TourCard], lang: Lang = "de") -> str | None:
    """Code-written sentence for the near misses; never given to the model."""
    if not near:
        return None
    head = _D[lang]["near"]
    return f"{head}: " + "; ".join(f"{c.name} ({c.deviation_text})" for c in near) + "."


def _labels(vocab: TagVocabulary, tag_ids: list[str], lang: Lang = "de") -> dict[str, str]:
    return {t: vocab.label(t, lang) for t in tag_ids}


def _card_tags(cards: list[TourCard]) -> list[str]:
    return [
        t
        for c in cards
        for t in (*c.preference.met, *c.preference.missing, *c.preference.avoided_hit)
    ]


def _as_float(r: ConstraintResult) -> ConstraintResult:
    """ascent_m is an int; the card field is float | bool | None (keeps JSON serialisation clean)."""
    if isinstance(r.actual, int) and not isinstance(r.actual, bool):
        return replace(r, actual=float(r.actual))
    return r


def _result_text(r: ConstraintResult, lang: Lang = "de") -> str:
    d = _D[lang]
    label = _LABEL[lang][r.kind]
    if r.ok is True:
        return d["ok"].format(label=label)
    if r.ok is None:
        return d["unknown"].format(label=label)
    return d["fail"].format(label=label, dev=format_deviation(r, lang))


def _search_data(
    req: HikeRequest,
    cards: list[TourCard],
    fallback: bool,
    vocab: TagVocabulary,
    lang: Lang = "de",
) -> str:
    d = _D[lang]

    def label(tag_id: str) -> str:
        return vocab.label(tag_id, lang)

    lines = [echo(req, vocab, lang)]
    lines.append(d["fallback_head"] if fallback else d["match_head"])
    time_word = d["time_run"] if req.activity == "run" else d["time_walk"]
    for i, card in enumerate(cards, start=1):
        facts = [
            d["length"].format(v=fmt(card.length_km, lang))
            if card.length_km is not None
            else d["length_unknown"],
            d["ascent"].format(v=fmt(card.ascent_m, lang, 0))
            if card.ascent_m is not None
            else d["ascent_unknown"],
            d["time"].format(word=time_word, v=fmt(card.duration_h, lang))
            if card.duration_h is not None
            else d["time_none"],
        ]
        if card.distance_km is not None:  # area start: the tour lies in the area
            facts.append(d["distance"].format(v=fmt(card.distance_km, lang)))
        line = f"{i}. {card.name} – {', '.join(facts)}; {d['conditions']}: " + "; ".join(
            _result_text(r, lang) for r in card.results
        )
        p = card.preference
        if p.met:
            line += f"; {d['met']}: " + ", ".join(label(t) for t in p.met)
        if p.missing:
            line += f"; {d['missing']}: " + ", ".join(label(t) for t in p.missing)
        if p.avoided_hit:
            line += f"; {d['avoided']}: " + ", ".join(label(t) for t in p.avoided_hit)
        lines.append(line)
    if req.unmatched:
        lines.append(f"{d['unmatched']}: " + ", ".join(req.unmatched))
    return "\n".join(lines)


def _card_evidence(ev: Evidence, scored: list[Scored], area: bool, lang: Lang = "de") -> None:
    for s in scored:
        c = s.candidate
        ev.add_name(c.name)
        ev.add(c.length_km, "km")
        ev.add(c.ascent_m, "Hm")
        ev.add(c.descent_m, "Hm")
        if not area:
            ev.add(c.distance_km, "km")
        ev.add(s.duration_h, "h")
        for r in s.results:
            if r.ok is not True:
                ev.numbers.append(format_deviation(r, lang))


_BOUND_UNIT = {"length_km": "km", "ascent_m": "Hm", "duration_h": "h", "radius_km": "km"}


def _bound_evidence(ev: Evidence, constraints: list[Constraint]) -> None:
    """The user's own bounds (structured), never the free echo text: an unmatched wish such as
    "max. 3 km Asphalt" must not make "3 km" a supported number."""
    for c in constraints:
        unit = _BOUND_UNIT.get(c.kind)
        if unit:
            for value in (c.min, c.max, c.approx):
                ev.add(value, unit)


# --- weather day finder (day hikes) ---------------------------------------------------------

_MONTH_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MAX_FIT_DAYS = 7  # days listed without a date
MAX_OTHER_DAYS = 5  # further days listed next to the day asked for
MAX_BEST_DAYS = 3  # closest days when none fits


def _short_date(d: date, lang: Lang = "de") -> str:
    """ "Mi 5.11." / "Wed 5 Nov"."""
    wd = _WEEKDAY[lang][d.weekday()]
    return f"{wd} {d.day}.{d.month}." if lang == "de" else f"{wd} {d.day} {_MONTH_EN[d.month - 1]}"


def _wish_point(start: ResolvedStart | None) -> tuple[float, float] | None:
    """The forecast point: the start place, or the middle of the area's box."""
    if start is None:
        return None
    if start.kind == "area" and start.bbox is not None:
        b = start.bbox
        return ((b.south + b.north) / 2, (b.west + b.east) / 2)
    if start.lat is not None and start.lon is not None:
        return (start.lat, start.lon)
    return None


def _wish_text(wish: WeatherWish, lang: Lang = "de") -> str:
    t = texts(lang)
    return {"fine": t.wish_fine, "dry": t.wish_dry, "snow": t.wish_snow}[wish]


def _weather_detail(w: DayWeather, lang: Lang = "de") -> str:
    """ "Klar, 2–11 °C, 0 mm" (only what is known)."""
    parts = [w.text] if w.text else []
    if w.t_min_c is not None and w.t_max_c is not None:
        parts.append(f"{fmt(w.t_min_c, lang, 0)}–{fmt(w.t_max_c, lang, 0)} °C")
    if w.precip_mm is not None:
        parts.append(f"{fmt(w.precip_mm, lang)} mm")
    return ", ".join(parts) or _D[lang]["weather_unknown"]


def _weather_days_text(days: list[WeatherDay], lang: Lang = "de") -> str:
    return ", ".join(
        f"{_short_date(d.date, lang)} ({_weather_detail(d.weather, lang)})" for d in days
    )


def _find_weather_days(
    series: list[DayWeather],
    wish: WeatherWish,
    place: str,
    target: date | None,
    today: date,
    lang: Lang = "de",
) -> tuple[WeatherDaysEvent, str]:
    """Event and code-written sentence for one point's forecast (today..today+14)."""
    t = texts(lang)
    wish_text = _wish_text(wish, lang)
    full_place, place = place, place.split(" (")[0]  # sentences use the short name

    def day(w: DayWeather) -> WeatherDay:
        loc = localize(w, lang)
        assert isinstance(loc, DayWeather)
        return WeatherDay(date=w.date, match=matches(w, wish), weather=loc)

    def event(days: list[WeatherDay], best_only: bool, note: str | None) -> WeatherDaysEvent:
        return WeatherDaysEvent(
            wish=wish, place=full_place, days=days, best_only=best_only, note=note
        )

    if not series:
        note = t.weather_unavailable
        return event([], False, note), note
    fits = [w for w in series if matches(w, wish) is True]
    lead: str | None = None
    asked = next((w for w in series if w.date == target), None) if target else None
    if target is not None and asked is not None:
        first = day(asked)
        others = [day(w) for w in fits if w.date != target][:MAX_OTHER_DAYS]
        key = {True: t.weather_day_fits, False: t.weather_day_misses, None: t.weather_day_unknown}
        sentence = key[first.match].format(
            day=_short_date(target, lang),
            wish=wish_text,
            place=place,
            detail=_weather_detail(first.weather, lang),
        )
        sentence += (
            t.weather_others.format(days=_weather_days_text(others, lang))
            if others
            else t.weather_no_others
        )
        return event([first, *others], False, None), sentence
    if target is not None:  # outside the forecast: the usual reason, then the days that fit
        code = "past" if target < today else "not_yet" if target > today else "missing"
        lead = _sentence(reason_text(code, lang))
    if fits:
        days, best_only = [day(w) for w in fits[:MAX_FIT_DAYS]], False
        body = t.weather_found
    else:
        ranked = sorted(series, key=lambda w: score(w, wish), reverse=True)
        days, best_only = [day(w) for w in ranked[:MAX_BEST_DAYS]], True
        body = t.weather_none
    sentence = body.format(wish=wish_text, place=place, days=_weather_days_text(days, lang))
    note = lead.rstrip(".") if lead else None
    return event(days, best_only, note), f"{lead} {sentence}" if lead else sentence


MAX_START_DAYS = 3  # start dates named when the whole tour fits


def _weather_period(
    plan: MultidayPlan,
    per_day: list[list[DayWeather]],
    wish: WeatherWish,
    start_date: date | None,
    lang: Lang = "de",
) -> tuple[WeatherDaysEvent, str, date | None] | None:
    """Weather period for a multi-day plan from the forecast at each day's destination
    (`per_day[i]`: today..today+14). Without a start date: event and sentence, and the start date
    to give the plan if one window fits all days. With one: does it fit? None: nothing to say."""
    t = texts(lang)
    wish_text, n = _wish_text(wish, lang), len(plan.days)
    by_date = [{w.date: w for w in series} for series in per_day]

    def window_days(start: date) -> list[WeatherDay]:
        out = []
        for i, known in enumerate(by_date):
            w = known.get(start + timedelta(days=i))
            if w is not None:
                loc = localize(w, lang)
                assert isinstance(loc, DayWeather)
                out.append(WeatherDay(date=w.date, match=matches(w, wish), weather=loc))
        return out

    def event(days: list[WeatherDay], best_only: bool) -> WeatherDaysEvent:
        return WeatherDaysEvent(
            wish=wish, place=plan.trail_name, days=days, best_only=best_only
        )

    if start_date is not None:
        days = window_days(start_date)
        if not days:  # the plan's own prefix says there is no forecast
            return None
        fits = sum(d.match is True for d in days)
        if fits == n:
            return event(days, False), t.weather_window_all.format(n=n, wish=wish_text), None
        known = {d.date for d in days if d.match is True}
        misses = [
            i + 1 for i in range(n) if start_date + timedelta(days=i) not in known
        ]
        sentence = t.weather_window_part.format(
            fits=fits, n=n, wish=wish_text, days=_days_text(misses, lang)
        )
        return event(days, False), sentence, None
    windows: list[Window] = best_windows(per_day, n, wish)
    if not windows:
        return None
    full = [w for w in windows if w.fits == n]
    if full:
        starts = ", ".join(_short_date(w.start, lang) for w in full[:MAX_START_DAYS])
        body = t.weather_window_found.format(
            n=n, wish=wish_text, starts=starts, first=_short_date(full[0].start, lang)
        )
        return event(window_days(full[0].start), False), _sentence(body), full[0].start
    best = windows[0]
    body = t.weather_window_none.format(
        n=n, wish=wish_text, fits=best.fits, start=_short_date(best.start, lang)
    )
    return event(window_days(best.start), True), _sentence(body), None


def _weather_facts(
    found: WeatherDaysEvent, target: date | None, lang: Lang
) -> tuple[list[str], list[WeatherDay], bool]:
    """Forecast line(s) for the model, the fitting days it may name, and whether the draft must
    not talk about the wish (no day fits, the asked day does not, or the service is down)."""
    t = texts(lang)
    wish_text = _wish_text(found.wish, lang)
    place = found.place.split(" (")[0]
    if not found.days and not found.best_only:
        return [t.weather_fact_down], [], True
    fits = [d for d in found.days if d.match is True]
    asked = found.days[0] if target and found.days and found.days[0].date == target else None
    lines: list[str] = []
    guard = False
    if asked is not None and asked.match is not True:
        key = t.weather_fact_misses if asked.match is False else t.weather_fact_unknown
        lines.append(
            key.format(day=_short_date(target, lang), wish=wish_text, place=place)
        )
        guard = True
    elif found.best_only:
        lines.append(t.weather_fact_none.format(wish=wish_text, place=place))
        guard = True
    if fits:
        lines.append(
            t.weather_data.format(wish=wish_text, place=place, days=_weather_days_text(fits, lang))
        )
    return lines, fits, guard


def _nopoint_sentence(place: str | None, lang: Lang) -> str:
    """Honest sentence when a weather wish has no usable forecast point."""
    t = texts(lang)
    if not place:
        return _sentence(reason_text("no_place", lang))
    return t.weather_nopoint.format(place=place.split(" (")[0])


def _weather_log(ev: WeatherDaysEvent) -> dict:
    return {
        "wish": ev.wish,
        "place": ev.place,
        "days": [
            {
                "date": d.date.isoformat(),
                "match": d.match,
                "code": d.weather.code,
                "t_min_c": d.weather.t_min_c,
                "t_max_c": d.weather.t_max_c,
                "precip_mm": d.weather.precip_mm,
                "precip_prob_pct": d.weather.precip_prob_pct,
                "snowfall_cm": d.weather.snowfall_cm,
            }
            for d in ev.days
        ],
        "best_only": ev.best_only,
        "note": ev.note,
    }


# --- multi-day: code sentences, facts for the model, evidence ------------------------------


def _sentence(text: str) -> str:
    return text if text.endswith(".") else f"{text}."


def _plan_prefix(
    plan: MultidayPlan,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
    lead: list[str] | None = None,
    lang: Lang = "de",
) -> str:
    """What the code says before the model: gaps, access paths, trail end, missing forecasts,
    missing rain variants and that times are without breaks (spec §8)."""
    d = _D[lang]
    lines = list(lead or [])
    lines += [f"{d['day']} {p.day}: {p.gap}" for p in plan.days if p.gap]
    lines += plan.notes
    if plan.days and plan.days[0].date is None:
        lines.append(f"{d['weather']}: {d['weather_nodate']}")
    missing = {n: w.reason for n, w in weather.items() if isinstance(w, NoForecast)}
    if missing and len(missing) == len(weather) and len(set(missing.values())) == 1:
        lines.append(f"{d['weather']}: {next(iter(missing.values()))}")
    else:
        lines += [f"{d['day']} {n}: {reason}" for n, reason in missing.items()]
    lines += [f"{d['day']} {n}: {no_rain_variant(lang)}" for n, v in rain.items() if v is None]
    if plan.days:
        lines.append(d["all_times"])
    return "\n".join(dict.fromkeys(_sentence(x) for x in lines))


def _days_text(days: list[int], lang: Lang = "de") -> str:
    """ "Tag 3", "Tag 1–4" (consecutive), "Tag 1, 3 und 5"."""
    d = _D[lang]
    if len(days) == 1:
        return d["days_one"].format(a=days[0])
    if days == list(range(days[0], days[-1] + 1)):
        return d["days_range"].format(a=days[0], b=days[-1])
    return d["days_list"].format(head=", ".join(map(str, days[:-1])), last=days[-1])


def _clock(t: Any, lang: Lang = "de") -> str:
    return _D[lang]["clock"].format(t=t)


def _weather_text(w: DayWeather | NoForecast | None, lang: Lang = "de") -> str | None:
    d = _D[lang]
    if w is None:
        return None
    if isinstance(w, NoForecast):
        return d["no_forecast"]
    parts = [w.text or d["weather_unknown"]]
    if w.t_min_c is not None and w.t_max_c is not None:
        parts.append(d["temp"].format(a=fmt(w.t_min_c, lang), b=fmt(w.t_max_c, lang)))
    parts.append(
        d["precip"].format(v=fmt(w.precip_mm, lang))
        if w.precip_mm is not None
        else d["precip_unknown"]
    )
    if w.precip_prob_pct is not None:
        parts.append(d["rain_prob"].format(v=fmt(w.precip_prob_pct, lang, 0)))
    return ", ".join(parts)


def _day_line(
    day: DayPlan,
    w: DayWeather | NoForecast | None,
    has_rain: bool,
    v: RainVariant | None,
    lang: Lang = "de",
) -> str:
    d = _D[lang]
    when = (
        f" ({_WEEKDAY[lang][day.date.weekday()]}, {day.date.strftime(_DATE_FMT[lang])})"
        if day.date
        else ""
    )
    facts = [
        f"{fmt(day.length_km, lang)} km"
        + (d["access"].format(v=fmt(day.access_km, lang, 2)) if day.access_km else ""),
        d["d_ascent"].format(v=fmt(day.ascent_m, lang, 0)),
        d["d_descent"].format(v=fmt(day.descent_m, lang, 0)),
        d["d_time"].format(v=fmt(day.duration_h, lang)),
        d["d_start"].format(c=_clock(day.start_time, lang)),
        d["d_arrival"].format(c=_clock(day.arrival, lang)) if day.arrival else d["d_arrival_none"],
    ]
    line = f"{d['day']} {day.day}{when}: " + ", ".join(facts)
    if day.stop is not None:
        line += d["stop"].format(
            name=day.stop.name or d["stop_noname"], dist=fmt(day.stop.dist_m, lang, 0)
        )
        if day.stop.dist_m > NEAR_M:
            line += f" ({access_straight(lang)})"
    else:
        line += d["stop_end"]
    if day.gap:
        line += d["gap"].format(gap=day.gap)
    weather = _weather_text(w, lang)
    line += (
        f"; {d['weather']}: {weather}" if weather else f"; {d['weather']}: {d['weather_nodate']}"
    )
    if has_rain and v is not None:
        line += d["rain_variant"].format(
            station=v.station_name,
            km=fmt(v.walk_km, lang),
            asc=fmt(v.ascent_m, lang, 0),
            h=fmt(v.duration_h, lang),
            note=v.note,
        )
    elif has_rain:
        line += d["rain_none"].format(note=no_rain_variant(lang))
    return line


def _plan_data(
    plan: MultidayPlan,
    start: str | None,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
    prefix: str,
    lang: Lang = "de",
) -> str:
    d = _D[lang]
    head = d["plan_head"].format(trail=plan.trail_name)
    if start:
        head += d["plan_from"].format(start=start)
    head += d["plan_tail"].format(n=len(plan.days), km=fmt(plan.target_km, lang))
    lines = [head]
    lines += [
        _day_line(p, weather.get(p.day), p.day in rain, rain.get(p.day), lang) for p in plan.days
    ]
    lines.append(d["plan_notes"])
    lines.append(prefix)
    return "\n".join(lines)


def _plan_evidence(
    ev: Evidence,
    plan: MultidayPlan,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
    lang: Lang = "de",
) -> None:
    ev.add_name(plan.trail_name)
    ev.add(plan.target_km, "km")
    for d in plan.days:
        for km in (d.start_km, d.end_km, d.walk_km, d.access_km, d.length_km):
            ev.add(km, "km")
        ev.add(d.ascent_m, "Hm")
        ev.add(d.descent_m, "Hm")
        ev.add(d.duration_h, "h")
        ev.numbers.append(_clock(d.start_time, lang))
        if d.arrival is not None:
            ev.numbers.append(_clock(d.arrival, lang))
        if d.stop is not None:
            ev.add_name(d.stop.name)
            ev.add(d.stop.dist_m, "m")
        if d.gap:
            ev.numbers.append(d.gap)
    for w in weather.values():
        if isinstance(w, DayWeather):
            ev.add(w.t_min_c, "°C")
            ev.add(w.t_max_c, "°C")
            ev.add(w.precip_mm, "mm")
            ev.add(w.precip_prob_pct, "%")
    for v in rain.values():
        if v is not None:
            ev.add_name(v.station_name)
            ev.add(v.walk_km, "km")
            ev.add(v.ascent_m, "Hm")
            ev.add(v.duration_h, "h")
            ev.numbers.append(v.note)
    ev.numbers += plan.notes


# --- react: tools for knowledge questions --------------------------------------------------


def _call_tool(tools: AgentTools, name: str, args: dict) -> Any:
    if name == "get_trail_details":
        return tools.get_trail_details(str(args["trail_id"]))
    if name == "find_accommodation":
        near = args.get("near_km")
        return tools.find_accommodation(
            str(args["trail_id"]),
            None if near is None else float(near),
            int(args.get("max_dist_m", 1000)),
        )
    if name == "hiking_time":
        return tools.hiking_time(
            float(args["length_km"]), float(args["ascent_m"]), float(args["descent_m"])
        )
    if name == "search_knowledge":
        return tools.search_knowledge(str(args["query"]), max(1, min(10, int(args.get("k", 5)))))
    raise _UnknownTool(name)


class _UnknownTool(Exception):
    pass


_HIKING_TIME_UNITS = {"length_km": "km", "ascent_m": "Hm", "descent_m": "Hm"}


def _inputs_in_evidence(args: dict, ev: Evidence) -> bool:
    try:
        return all(has_number(ev, float(args[k]), u) for k, u in _HIKING_TIME_UNITS.items())
    except (KeyError, TypeError, ValueError):
        return False


def _dump(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [_dump(x) for x in result]
    return result


def _unit(key: str) -> str | None:
    if key in ("ascent_m", "descent_m"):
        return "Hm"
    if key.endswith("_km"):
        return "km"
    if key.endswith("_m"):
        return "m"
    if key.endswith("_h") or key == "hours":
        return "h"
    return None


_NAME_KEYS = {"name", "title", "start_name", "end_name"}


def _walk(data: Any, ev: Evidence, key: str = "") -> None:
    """Numbers (with a unit from the field name) and names from a dumped tool result."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k.endswith("_shares") and isinstance(v, dict):
                for share in v.values():
                    if isinstance(share, int | float):
                        ev.add(share * 100, "%")
            else:
                _walk(v, ev, k)
    elif isinstance(data, list):
        for x in data:
            _walk(x, ev, key)
    elif isinstance(data, int | float) and not isinstance(data, bool):
        unit = _unit(key)
        if unit:
            ev.add(data, unit)
    elif isinstance(data, str):
        if key in _NAME_KEYS:
            ev.add_name(data)
        elif key == "text":  # knowledge passages: numbers with units inside the text
            ev.numbers.append(data)


def _sources_of(result: Any) -> list[SourceBrief]:
    items = result if isinstance(result, list) else [result]
    out: list[SourceBrief] = []
    for x in items:
        if isinstance(x, KnowledgeHit):
            for url in x.source_urls or ([x.url] if x.url else []):
                out.append(
                    SourceBrief(
                        id=x.source_id or url,
                        name=x.title,
                        url=url,
                        license=x.license,
                        status=x.status,
                    )
                )
        elif isinstance(x, TrailDetails):
            out += x.sources
        elif isinstance(x, LodgingBrief) and x.source_id:
            out.append(SourceBrief(id=x.source_id, name=None, url=None, license=None))
    return out


def _add_sources(have: list[dict], new: list[SourceBrief]) -> list[dict]:
    """One entry per URL (several chunks of one article are one source); without URL per id."""

    def key(url: str | None, id_: str) -> str:
        return url or f"id:{id_}"

    seen = {key(s.get("url"), s["id"]) for s in have}
    out = list(have)
    for s in new:
        if key(s.url, s.id) not in seen:
            seen.add(key(s.url, s.id))
            out.append(s.model_dump(mode="json"))
    return out


def _text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
    return "".join(parts).strip()


def _events_text(found: EventsResult, lang: Lang = "de") -> str:
    t = texts(lang)

    def pages(n: int) -> str:
        return t.word_page if n == 1 else t.word_pages

    n, read = len(found.events), len(found.pages)
    if found.search_failed:
        text = t.events_search_down
    elif n:
        noun = t.word_run if n == 1 else t.word_runs
        text = t.events_found.format(n=n, noun=noun, pages=read, page_noun=pages(read))
    else:
        text = t.events_none.format(pages=read, page_noun=pages(read))
    if found.skipped:
        reasons = "; ".join(dict.fromkeys(skip_reason(s.reason, lang) for s in found.skipped))
        k = len(found.skipped)
        text += t.events_skipped.format(n=k, page_noun=pages(k), reasons=reasons)
    return text


# --- graph --------------------------------------------------------------------------------


def build_graph(deps: AgentDeps) -> Any:
    tools = TracedTools(deps.tools)
    known_tags = {t.id for t in deps.vocab.all() if t.category in ("feature", "surface")}
    gw, vocab, settings = deps.gateway, deps.vocab, deps.settings

    def guard(state: State) -> State:
        text = sanitize_text(state["message"])
        history = [*state.get("history", []), text][-HISTORY_KEEP:]
        if looks_like_injection(text):
            return {
                "message": text,
                "history": history,
                "guard": "injection",
                "reply": texts(state.get("lang", "de")).injection_reply,
                "route": "reply",
            }
        return {"message": text, "history": history, "route": "understand"}

    def _resolve(
        raw: RawRequest, message: str, previous: HikeRequest | None, lang: Lang, **kw: Any
    ):
        return resolve(
            vocab, raw, message, previous, today=deps.today(), trails=tools, lang=lang, **kw
        )

    def _continue_pending(pending: dict, message: str, previous: HikeRequest | None, lang: Lang):
        """Answer to an open clarify question: a place answer continues the partial request
        without a model call; anything else goes to the model with the earlier message."""
        days_answer = pending["question"] in DAYS_QUESTIONS and re.fullmatch(
            r"\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*", message
        )
        if days_answer:  # "3" or "2-3" answers "Wie viele Tage?" (a range: its upper bound)
            message = f"{max(int(n) for n in days_answer.groups() if n)} Tage"
        if pending.get("raw") and message.strip() in DAY_ROUNDS_OPTIONS:
            # "Tages-Rundwege" under the multi-day round-walk question: the same request as a
            # day-hike search (start and wishes stay, the multi-day fields go)
            raw = RawRequest.model_validate(pending["raw"])
            probe = raw.model_copy(
                update={"intent": "day_hike", "trail_text": None, "days": None, "day_km": None}
            )
            return probe, _resolve(probe, pending["message"], previous, lang), pending["message"]
        if pending.get("raw"):
            raw = RawRequest.model_validate(pending["raw"])
            if days_answer and raw.intent == "multiday":
                # the count goes into the partial request, its place answers stay
                base = f"{pending['message']}\n{message}"
                probe = raw.model_copy(update={"days": int(message.split()[0])})
                res = _resolve(probe, base, previous, lang)
                if isinstance(res, HikeRequest):
                    return probe, res, base
            elif raw.intent in (*TOUR_INTENTS, "multiday"):
                start = resolve_option(vocab, message)
                probe = raw.model_copy(update={"start_text": message})
                if start is not None:
                    res = _resolve(raw, pending["message"], previous, lang, start=start)
                else:
                    res = _resolve(probe, pending["message"], previous, lang)
                if isinstance(res, HikeRequest) and res.start is not None:
                    return raw, res, pending["message"]
                accepted = start is not None or start_of(vocab, message, lang) is not None
                if accepted and isinstance(res, Clarify) and res.question != pending["question"]:
                    # the answer worked and the next question follows (e.g. the days): keep it
                    # in the partial request -- the model would re-read the first message's place
                    return probe, res, pending["message"]
        combined = f"{pending['message']}\nRückfrage: {pending['question']}\nAntwort: {message}"
        return None, None, combined

    trail_terms = [
        fold(x) for t in vocab.all() if t.category == "trail" for x in (t.label, *t.synonyms)
    ]

    def _rain_request(state: State) -> list[int] | None:
        """ "Regenvariante für Tag 2 (und 3)" as a short follow-up on the thread's last plan:
        answered without the model. Anything that names a trail, a day count or a start place
        is a new request and goes through parse."""
        message = state["message"]
        if not state.get("plan") or not state.get("plan_request") or not _RAIN_ASK.search(message):
            return None
        folded = f" {fold(message)} "
        if (
            "fernweg" in folded
            or any(term in folded for term in trail_terms)
            or _DAYS_PHRASE.search(message)
            or _NEW_START.search(message)
        ):
            return None
        m = _RAIN_DAYS.search(message)
        if not m:
            return None
        days: list[int] = []
        for a, dash, b in _DAY_NUMS.findall(m.group(1)):
            days += list(range(int(a), int(b) + 1)) if dash else [int(a)]
        return list(dict.fromkeys(days))[:MAX_DAYS]

    def understand(state: State, config: RunnableConfig) -> State:
        message = state["message"]
        lang = state.get("lang", "de")
        previous = HikeRequest.model_validate(state["request"]) if state.get("request") else None
        rain_days = None if state.get("pending") else _rain_request(state)
        if rain_days:
            plan_req = state["plan_request"]
            return {
                "intent": "multiday",
                "activity": (plan_req or {}).get("activity"),
                "current": plan_req,
                "rain_days": rain_days,
                "route": "multiday",
            }
        raw, res, base = None, None, message
        if state.get("pending"):
            raw, res, base = _continue_pending(state["pending"], message, previous, lang)
        if res is None:
            raw = parse(gw, vocab, base, previous)
            res = _resolve(raw, base, previous, lang)
        out: State = {"pending": None, "intent": raw.intent, "activity": raw.activity}
        if isinstance(res, HikeRequest):
            out.update(intent=res.intent, activity=res.activity)
            out["discarded_numbers"] = res.discarded_model_numbers
            if res.intent in (*TOUR_INTENTS, "groups") and res.start is None:
                res = Clarify(question=texts(lang).clarify_start)
        if isinstance(res, Clarify):
            pending = {
                "raw": raw.model_dump(mode="json"),
                "message": base,
                "question": res.question,
            }
            return out | {"pending": pending, "clarify": res.model_dump(), "route": "clarify"}
        req = res
        user_id = config["configurable"]["user_id"].value
        if user_id and req.intent in TOUR_INTENTS and not (req.trail_id and req.intent == "change"):
            req = _with_saved_preferences(req, user_id)
        if req.intent != "other":
            _emit(
                UnderstoodEvent(
                    text=echo(req, vocab, lang),
                    request=req,
                    labels=_labels(vocab, [p.tag_id for p in req.preferences], lang),
                )
            )
        out["current"] = req.model_dump(mode="json")
        if req.trail_id is not None and req.intent in ("multiday", "change"):
            return out | {"request": out["current"], "route": "multiday"}
        if req.intent in TOUR_INTENTS:
            # a day-hike search ends the multi-day conversation: no follow-ups on the old plan
            return out | {
                "request": out["current"],
                "plan": None,
                "plan_request": None,
                "route": "search",
            }
        if req.intent == "knowledge":
            return out | {"route": "react"}
        if req.intent == "groups":
            return out | {"route": "groups"}
        if req.intent == "events":
            return out | {"route": "events"}
        return out | {"reply": texts(lang).other_reply, "route": "reply"}

    def _with_saved_preferences(req: HikeRequest, user_id: str) -> HikeRequest:
        """The user's standing preferences on top of the chat's wishes; a failing lookup costs
        only the personal sorting, never the search."""
        try:
            saved = tools.saved_preferences(user_id)
        except Exception:  # optional sorting: the search goes on without it
            logging.getLogger(__name__).warning("saved preferences not loaded", exc_info=True)
            return req
        return with_saved(req, saved, known_tags)

    def clarify(state: State) -> State:
        c = state["clarify"] or {}
        question = c.get("question", "")
        _emit(ClarifyEvent(question=question, options=c.get("options", [])))
        return {"final_text": question}

    def reply(state: State) -> State:
        for chunk in _CHUNK.findall(state["reply"] or ""):
            _emit(TokenEvent(text=chunk))
        return {"final_text": state["reply"]}

    def search(state: State) -> State:
        lang = state.get("lang", "de")
        t = texts(lang)
        req = HikeRequest.model_validate(state["current"])
        ev = Evidence()
        _bound_evidence(ev, req.constraints)
        contra = contradiction(req.constraints, lang)
        if contra:  # no search, no fallback tours
            reason = _D[lang]["no_contra"].format(contra=contra)
            _emit(ResultsEvent(cards=[], fallback_reason=reason))
            return {"reason": reason, "fixed": t.contradiction_hint}
        result = tools.search_day_hikes(req, lang)
        sel = result.selection
        scored = sel.matches or sel.fallbacks
        area = req.start is not None and req.start.kind == "area"
        cards = [_card(s, area, lang=lang) for s in scored]
        near_cards = [_card(s, area, near_miss=True, lang=lang) for s in sel.near_misses]
        shown = cards + near_cards
        reason = None if sel.matches else sel.reason
        _emit(
            ResultsEvent(
                cards=shown, fallback_reason=reason, labels=_labels(vocab, _card_tags(shown), lang)
            )
        )
        briefs = {s.id: s for s in result.sources}
        sources = [
            briefs.get(i) or SourceBrief(id=i, name=None, url=None, license=None)
            for i in result.source_ids
        ] + [s for s in result.sources if s.id not in result.source_ids]
        out: State = {
            "tool_calls": 1,
            "reason": reason,
            "sources": _add_sources([], sources),
            "last_tours": [{"trail_id": c.trail_id, "name": c.name} for c in shown],
            "near_sentence": _near_sentence(near_cards, lang),
            "candidates": candidate_rows(sel, lang),
        }
        fit_days: list[WeatherDay] = []
        facts: list[str] = []
        point = _wish_point(req.start) if req.weather_wish else None
        if req.weather_wish and point and req.start:  # on both paths: with and without tours
            wish, place = req.weather_wish, req.start.label
            got = tools.forecast_range([point], deps.today())
            if isinstance(got, NoForecast):
                found = WeatherDaysEvent(
                    wish=wish, place=place, days=[], best_only=False, note=t.weather_unavailable
                )
                sentence = t.weather_unavailable
            else:
                found, sentence = _find_weather_days(
                    got[0], wish, place, req.start_date, deps.today(), lang
                )
            _emit(found)
            facts, fit_days, guard = _weather_facts(found, req.start_date, lang)
            out |= {
                "tool_calls": out["tool_calls"] + 1,
                "weather_sentence": sentence,
                "weather_days": _weather_log(found),
                "weather_guard": wish if guard else None,
            }
        elif req.weather_wish:  # no usable forecast point: say so, never leave it silent
            sentence = _nopoint_sentence(req.start.label if req.start else None, lang)
            facts = [f"{t.weather_label}: {sentence}"]
            out |= {"weather_sentence": sentence, "weather_guard": req.weather_wish}
        if not cards:
            return out | {"fixed": t.no_tours_hint}
        data = _search_data(req, cards, not sel.matches, vocab, lang)
        _card_evidence(ev, scored, area, lang)
        if facts:
            data += "\n" + "\n".join(facts)
            ev.numbers += facts
            # the model may name the fitting days, so their numbers are evidence
            for d in fit_days:
                ev.add(d.weather.t_min_c, "°C")
                ev.add(d.weather.t_max_c, "°C")
                ev.add(d.weather.precip_mm, "mm")
                ev.add(d.weather.precip_prob_pct, "%")
                ev.add(d.weather.snowfall_cm, "cm")
        ev.add(result.searched_radius_km, "km")
        ev.numbers.append(reason or "")
        if req.start is not None:
            ev.add_name(req.start.label)
        return out | {"data": data, "evidence": vars(ev)}

    def groups(state: State) -> State:
        lang = state.get("lang", "de")
        t = texts(lang)
        req = HikeRequest.model_validate(state["current"])
        start = req.start
        if start is not None and start.lat is not None and start.lon is not None:
            lat, lon = start.lat, start.lon
        elif start is not None and start.bbox is not None:  # an area: its centre
            lat, lon = (
                (start.bbox.south + start.bbox.north) / 2,
                (start.bbox.west + start.bbox.east) / 2,
            )
        else:
            place = start.label if start else _D[lang]["no_coords_place"]
            return {"fixed": t.groups_no_coords.format(place=place)}
        place = start.label
        text = f"{req.question or ''} {state['message']}"
        kind = next((k for rx, k in _GROUP_KINDS if rx.search(text)), None)
        found = tools.find_groups(lat, lon, DEFAULT_GROUP_RADIUS_KM, kind, deps.today())
        radius = fmt(DEFAULT_GROUP_RADIUS_KM, lang)
        if not found:
            kind_word = {
                "lauftreff": t.kind_lauftreff,
                "alpenverein": t.kind_alpenverein,
                "wanderverein": t.kind_wanderverein,
            }.get(kind or "", "")
            body = t.groups_none.format(kind=kind_word, radius=radius, place=place)
            return {"tool_calls": 1, "fixed": body}
        note = _D[lang]["as_of"].format(
            d=min(g.checked_at for g in found).strftime(_DATE_FMT[lang])
        )
        _emit(GroupsEvent(groups=found, checked_note=note))
        stale = sum(g.stale for g in found)
        hand = sum(g.status == "geprüft" for g in found)
        if hand == len(found):
            check = t.groups_check_all.format(label=t.group_hand)
        elif hand == 0:
            check = t.groups_check_all.format(label=t.group_auto)
        else:
            check = t.groups_check_mixed.format(hand=hand, auto=len(found) - hand)
        body = t.groups_found.format(
            n=len(found), noun=t.word_group if len(found) == 1 else t.word_groups,
            radius=radius, place=place, note=note, check=check,
        )  # fmt: skip
        if stale:
            body += t.groups_stale.format(n=stale, verb=t.word_is if stale == 1 else t.word_are)
        return {"tool_calls": 1, "fixed": body}

    def events(state: State) -> State:
        """Code-written answer (no model wording): the cards carry every value with its source."""
        lang = state.get("lang", "de")
        req = HikeRequest.model_validate(state["current"])
        today = deps.today()
        found = tools.find_events(req.question or state["message"], today, settings.max_tool_calls)
        note = texts(lang).events_note.format(date=today.strftime(_DATE_FMT[lang]))
        _emit(EventsEvent(events=found.events, fallback=found.fallback, note=note))
        return {"tool_calls": found.calls, "fixed": _events_text(found, lang)}

    def multiday(state: State) -> State:
        lang = state.get("lang", "de")
        t = texts(lang)
        req = HikeRequest.model_validate(state["current"])
        stored = MultidayPlan.model_validate(state["plan"]) if state.get("plan") else None
        plan_req = state.get("plan_request")
        rain_days = state.get("rain_days") or []
        start = req.start.label if req.start else None  # a new plan names its own start
        follow_up = bool(rain_days) or req.day_change is not None
        if follow_up and stored is not None and plan_req and plan_req.get("start"):
            start = plan_req["start"]["label"]  # the stored plan's start, not a later request's
        budget = settings.max_tool_calls
        calls = 0
        lead: list[str] = []
        out: State = {}
        period: tuple[WeatherDaysEvent, str, date | None] | None = None
        points: dict[int, tuple[float, float] | None] = {}
        nopoint: str | None = None  # a weather wish without a usable forecast point
        if rain_days and stored is not None:
            plan = stored
            unknown = [n for n in rain_days if not 1 <= n <= len(plan.days)]
            rain_days = [n for n in rain_days if n not in unknown]
            lead = [t.day_unknown.format(n=len(plan.days), day=n) for n in unknown]
            if not rain_days:
                return {"fixed": " ".join(lead)}
        elif req.day_change is not None:
            if stored is None:
                return {"fixed": t.no_plan_to_change}
            if not 1 <= req.day_change.day <= len(stored.days):
                # the plan can be shorter than asked for (trail end, dead end)
                return {"fixed": t.day_unknown.format(n=len(stored.days), day=req.day_change.day)}
            plan, calls = tools.change_day(stored, req.day_change, start_name=start), 1
        else:
            try:
                plan, calls = tools.plan_multiday(req, lang), 1
            except StartNotOnTrail:
                tag = vocab.get(f"trail:{req.trail_id}")
                trail = tag.label if tag else str(req.trail_id)
                text = t.no_plan_at_start.format(
                    start=start or _D[lang]["no_coords_place"], trail=trail
                )
                return {"tool_calls": 1, "plan": None, "plan_request": None, "fixed": text}
            out["plan_request"] = state["current"]
            if req.weather_wish and plan.days and calls + 2 > budget:
                nopoint = _nopoint_sentence(plan.trail_name, lang)
            if req.weather_wish and plan.days and calls + 2 <= budget:
                # the forecast at every day's destination decides the period; the lookup of
                # the destinations is reused for the per-day weather below
                points = tools.day_end_points(plan.trail_id, plan.days)
                calls += 1
                if not all(points.get(d.day) for d in plan.days):
                    nopoint = _nopoint_sentence(plan.trail_name, lang)
                else:
                    got = tools.forecast_range([points[d.day] for d in plan.days], deps.today())
                    calls += 1
                    if isinstance(got, NoForecast):
                        period = (
                            WeatherDaysEvent(
                                wish=req.weather_wish,
                                place=plan.trail_name,
                                days=[],
                                best_only=False,
                                note=t.weather_unavailable,
                            ),
                            t.weather_unavailable,
                            None,
                        )
                    else:
                        period = _weather_period(plan, got, req.weather_wish, req.start_date, lang)
                if period is not None and period[2] is not None:
                    # dates only: every other value of the plan is independent of the date
                    first = period[2]
                    plan = plan.model_copy(
                        update={
                            "days": [
                                d.model_copy(update={"date": first + timedelta(days=i)})
                                for i, d in enumerate(plan.days)
                            ]
                        }
                    )
        known_points = bool(points)
        weather: dict[int, DayWeather | NoForecast] = {}
        dated = [d for d in plan.days if d.date is not None]  # no date: said once in the prefix
        if dated and calls + (1 if known_points else 2) <= budget:  # destinations, one forecast request
            points = points or tools.day_end_points(plan.trail_id, dated)
            located = [d for d in dated if points.get(d.day)]
            wanted_points = [(*points[d.day], d.date) for d in located]
            got = tools.weather_days(wanted_points, deps.today())
            weather = {d.day: no_forecast("no_place", lang) for d in dated}
            weather |= {d.day: localize(w, lang) for d, w in zip(located, got, strict=True)}
            calls += 1 if known_points else 2
        elif dated:
            lead.append(
                _D[lang]["no_forecast_asked"].format(days=_days_text([d.day for d in dated], lang))
            )
        wanted = [n for n, w in weather.items() if isinstance(w, DayWeather) and is_rain_day(w)]
        wanted = sorted({*wanted, *rain_days})
        rain: dict[int, RainVariant | None] = {}
        if wanted and calls + 1 <= budget:
            rain = tools.rain_variants(plan, wanted, lang)
            calls += 1
        elif wanted:
            lead.append(_D[lang]["no_rain_calc"].format(days=_days_text(wanted, lang)))
        _emit(
            PlanEvent(
                plan=plan,
                weather=weather,
                rain=rain,
                labels=_labels(vocab, [t for t in [f"trail:{plan.trail_id}"] if t in vocab], lang),
                start_name=start,
            )
        )
        weather_fact: str | None = None
        if period is not None:
            _emit(period[0])
            out |= {"weather_sentence": period[1], "weather_days": _weather_log(period[0])}
            weather_fact = f"{t.weather_label}: {period[1]}"
            full_fit = (
                not period[0].best_only
                and len(period[0].days) == len(plan.days)
                and all(d.match is True for d in period[0].days)
            )
            out["weather_guard"] = None if full_fit else req.weather_wish
        elif nopoint is not None and req.weather_wish:
            out |= {"weather_sentence": nopoint, "weather_guard": req.weather_wish}
            weather_fact = f"{t.weather_label}: {nopoint}"
        sources = tools.sources([i for i in plan.source_ids if i != SOURCE_WEATHER])
        if any(isinstance(w, DayWeather) for w in weather.values()):
            meteo = weather_source()
            sources.append(
                SourceBrief(id=meteo.id, name=meteo.name, url=meteo.url, license=meteo.license)
            )
        prefix = _plan_prefix(plan, weather, rain, lead, lang)
        out |= {
            "plan": plan.model_dump(mode="json"),
            "tool_calls": calls,
            "sources": _add_sources([], sources),
            "prefix": prefix,
        }
        if not plan.days:  # only the dead-end note: nothing for the model to word
            return out
        ev = Evidence()
        _plan_evidence(ev, plan, weather, rain, lang)
        ev.numbers.append(prefix)
        if start:
            ev.add_name(start)
        data = _plan_data(plan, start, weather, rain, prefix, lang)
        if weather_fact:
            data += "\n" + weather_fact
            ev.numbers.append(weather_fact)
        return out | {"data": data, "system": plan_system(lang), "evidence": vars(ev)}

    def react(state: State) -> State:
        lang = state.get("lang", "de")
        t = texts(lang)
        req = HikeRequest.model_validate(state["current"])
        question = req.question or state["message"]
        last_tours = state.get("last_tours") or []
        messages: list[BaseMessage] = [SystemMessage(react_system(lang))]
        ev = Evidence()
        if last_tours:  # follow-up questions about suggested tours need their ids (I-8)
            lines = [f"- {x['trail_id']}: {x['name']}" for x in last_tours]
            messages.append(SystemMessage(t.react_tours + "\n" + "\n".join(lines)))
            for x in last_tours:
                ev.add_name(x["name"])
        messages.append(HumanMessage(question))
        sources: list[dict] = []
        results: list[str] = []
        # the knowledge index is searched in code first, so an answer can rest on a source (I-3)
        pre = {"name": "search_knowledge", "args": {"query": question, "k": 5}, "id": "vorab"}
        content = _run_tool(pre, ev, results, t)
        if content[1] is not None:
            sources = _add_sources(sources, _sources_of(content[1]))
        executed = 1
        if not sources and not last_tours:  # nothing to stand on: no model free-answer
            return {"tool_calls": executed, "fixed": t.no_source_reply}
        messages += [
            AIMessage(content="", tool_calls=[pre | {"type": "tool_call"}]),
            ToolMessage(content[0], tool_call_id=pre["id"]),
        ]
        limit_hit = False
        draft = ""
        for _ in range(settings.max_tool_calls + 2):
            ai = gw.tool_round(messages, TOOL_SPECS)
            messages.append(ai)
            if not ai.tool_calls:
                draft = _text(ai)
                break
            if limit_hit:  # the model was told to answer but asked for tools again
                break
            for call in ai.tool_calls:
                if executed >= settings.max_tool_calls:
                    limit_hit = True
                    messages.append(ToolMessage(t.tool_limit, tool_call_id=call["id"]))
                    continue
                executed += 1
                content = _run_tool(call, ev, results, t)
                if content[1] is not None:
                    sources = _add_sources(sources, _sources_of(content[1]))
                messages.append(ToolMessage(content[0], tool_call_id=call["id"]))
        out: State = {"tool_calls": executed, "evidence": vars(ev), "sources": sources}
        if not sources:  # the model answered without any sourced tool result
            return {"tool_calls": executed, "fixed": t.no_source_reply}
        if draft:
            return out | {"draft": draft}
        data = _D[lang]["question"].format(q=question) + "\n".join(results)
        return out | {"data": data}

    def _run_tool(call: dict, ev: Evidence, results: list[str], t: Texts) -> tuple[str, Any]:
        name = call["name"]
        args = call.get("args") or {}
        # a walking time counts as evidence only if its inputs are evidence themselves (I-8)
        trusted = name != "hiking_time" or _inputs_in_evidence(args, ev)
        try:
            result = _call_tool(tools, name, args)
        except LLMError:
            raise
        except _UnknownTool:
            return t.tool_unknown.format(name=name), None
        except Exception as exc:  # noqa: BLE001 - tool errors go back to the model, never abort
            return t.tool_error.format(name=name, kind=type(exc).__name__), None
        if result is None:
            return t.trail_not_found, None
        dumped = _dump(result)
        if trusted:
            _walk(dumped, ev)
        content = json.dumps(dumped, ensure_ascii=False)
        results.append(f"{name}: {content}")
        return content, result

    def answer(state: State) -> State:
        if state.get("draft") or not state.get("data"):
            return {}
        return {
            "draft": gw.answer(
                state.get("system") or answer_system(state.get("lang", "de")), state["data"]
            )
        }

    def ground(state: State) -> State:
        lang = state.get("lang", "de")
        t = texts(lang)
        draft, out = state.get("draft"), {}
        reason = state.get("reason")
        body = state.get("fixed") or ""
        if draft and any(leaks_system_prompt(draft, p) for p in _PROMPTS):
            body, out = t.leak_reply, {"guard": "leak"}
        elif draft:
            claims = 0
            if not reason:  # the code did not fall back: no claim that no tour meets all wishes
                draft, claims = strip_unsat_claims(draft, lang)
                if not draft and state.get("route") == "search":  # the cards are shown
                    draft = t.claim_only_tours
            wish = state.get("weather_guard")
            if wish and draft:  # the forecast says no / unknown: no weather claim of the model
                draft, dropped = strip_weather_claims(
                    draft, lambda part: has_weather_word(part, wish), lang
                )
                claims += dropped
                if not draft and state.get("route") == "search":
                    draft = t.claim_only_tours
            g = grounding_check(
                draft, Evidence(**state["evidence"]), deps.trail_names, lang
            )
            # numbers are replaced; unknown tour names stay but get a hint (R21)
            body = g.text
            out = {
                "unsupported": len(g.unsupported),
                "unsupported_names": g.unsupported_names,
                "unsat_claims_removed": claims,
            }
        # the code's honest sentences come first, verbatim, whatever the model wrote
        lead = state.get("prefix") or ""
        near = state.get("near_sentence") or ""
        wsent = state.get("weather_sentence") or ""
        text = "\n\n".join(
            x for x in (lead, f"{reason}." if reason else "", body, near, wsent) if x
        )
        for chunk in _CHUNK.findall(text):
            _emit(TokenEvent(text=chunk))
        if state.get("sources"):
            _emit(SourcesEvent(sources=[SourceBrief(**s) for s in state["sources"]]))
        return out | {"final_text": text}

    def log(state: State, config: RunnableConfig) -> State:
        conf = config["configurable"]
        usage: LLMUsage = conf["usage"]
        _write_log(
            settings,
            conf["request_id"],
            state,
            usage,
            None,
            conf.get("user_hash"),
            conf["user_id"].value,
            conf.get("trace"),
        )
        _emit(
            DoneEvent(
                usage=usage,
                unsupported=state.get("unsupported", 0),
                unsupported_names=state.get("unsupported_names", []),
                unsat_claims_removed=state.get("unsat_claims_removed", 0),
            )
        )
        return {}

    g = StateGraph(State)
    for name, fn in [
        ("guard", guard),
        ("understand", understand),
        ("clarify", clarify),
        ("reply", reply),
        ("search", search),
        ("multiday", multiday),
        ("groups", groups),
        ("events", events),
        ("react", react),
        ("answer", answer),
        ("ground", ground),
        ("log", log),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", lambda s: s["route"], ["understand", "reply"])
    g.add_conditional_edges(
        "understand",
        lambda s: s["route"],
        ["clarify", "reply", "search", "multiday", "react", "groups", "events"],
    )
    g.add_edge("clarify", "log")
    g.add_edge("reply", "log")
    g.add_edge("search", "answer")
    g.add_edge("multiday", "answer")
    g.add_edge("react", "answer")
    g.add_edge("groups", "answer")
    g.add_edge("events", "answer")
    g.add_edge("answer", "ground")
    g.add_edge("ground", "log")
    g.add_edge("log", END)
    return g.compile(checkpointer=deps.checkpointer)


def _write_log(
    settings: Settings,
    request_id: str,
    state: dict,
    usage: LLMUsage,
    error: str | None,
    user_hash: str | None = None,
    user_id: str | None = None,
    tr: Trace | None = None,
) -> None:
    history = state.get("history") or []
    chatlog.write(
        settings.chat_log_path,
        ChatLogEntry(
            request_id=request_id,
            user_hash=user_hash,
            intent=state.get("intent"),
            activity=state.get("activity"),
            tool_calls=state.get("tool_calls", 0),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            calls_without_cost=usage.calls_without_cost,
            grounding_unsupported=state.get("unsupported", 0),
            grounding_unsupported_names=len(state.get("unsupported_names", [])),
            unsat_claims_removed=state.get("unsat_claims_removed", 0),
            guard=state.get("guard"),
            discarded_model_numbers=state.get("discarded_numbers", 0),
            error=error,  # exception class name only, never a message text
            user_id=user_id,
            message=state.get("message"),
            previous_messages=history[:-1][-5:],
            request=state.get("current"),
            answer=state.get("final_text"),
            fallback_reason=state.get("reason"),
            candidates=state.get("candidates") or [],
            plan=state.get("plan") if state.get("route") == "multiday" else None,
            weather_days=state.get("weather_days"),
            llm_calls=tr.llm_calls if tr else [],
            tools=tr.tool_calls if tr else [],
            duration_ms=int((time.monotonic() - tr.started) * 1000) if tr else None,
        ),
    )


@dataclass(frozen=True)
class _Private:
    """A value for the log node that must not become LangSmith metadata: LangChain copies
    every str/int/float/bool of `configurable` into the tracing metadata, a wrapper it does
    not (and its repr hides the value)."""

    value: str | None = field(repr=False)


def _graph_thread(thread_id: str, user_hash: str | None) -> str:
    # keyed by user as well: a thread id alone never continues another user's chat
    return f"{user_hash or ''}:{thread_id}"


def _turn_lang(deps: AgentDeps, thread_id: str, user_hash: str | None, message: str, page: Lang) -> Lang:
    """Reply language of this turn: the message's own, else the conversation's so far, else the
    page's (agent/reply_lang.py)."""
    try:
        state = deps.graph.get_state({"configurable": {"thread_id": _graph_thread(thread_id, user_hash)}})
        previous = (state.values or {}).get("lang")
    except Exception:  # noqa: BLE001 - no saved state is no reason to fail the turn
        previous = None
    return reply_lang(message, previous if previous in ("de", "en") else None, page)


def _run_config(
    thread_id: str,
    request_id: str,
    user_hash: str | None,
    user_id: str | None,
    lang: Lang,
    usage: LLMUsage,
    tr: Trace,
) -> RunnableConfig:
    """Config of one chat turn. run_name/tags/metadata only matter with LangSmith tracing on:
    request_id matches the chat log line (/admin); thread and user only as hashes, never the
    raw user id or an e-mail."""
    graph_thread = _graph_thread(thread_id, user_hash)
    return {
        "run_name": "chat",
        "tags": ["chat", f"lang:{lang}"],
        "metadata": {
            "request_id": request_id,
            "thread_id": hashlib.sha256(graph_thread.encode()).hexdigest()[:12],
            "user_hash": user_hash,
            "lang": lang,
        },
        "configurable": {
            "thread_id": graph_thread,
            "usage": usage,
            "request_id": request_id,
            "user_hash": user_hash,
            "user_id": _Private(user_id),
            "lang": lang,
            "trace": tr,
        },
    }


def _run(
    deps: AgentDeps,
    thread_id: str,
    message: str,
    user_hash: str | None,
    user_id: str | None,
    lang: Lang = "de",
) -> Iterator[ChatEvent]:
    request_id = uuid.uuid4().hex
    lang = _turn_lang(deps, thread_id, user_hash, message, lang)
    with metered(max_cost_usd=deps.settings.max_cost_usd) as usage, traced() as tr:
        config = _run_config(thread_id, request_id, user_hash, user_id, lang, usage, tr)
        stream = deps.graph.stream(_turn(message, lang), config, stream_mode="custom")
        logged = False  # the log node writes the line and then emits "done"
        try:
            for event in stream:
                logged = logged or event.type == "done"
                yield event
        except LLMError as exc:
            logged = True
            state = deps.graph.get_state(config).values
            _write_log(
                deps.settings, request_id, state, usage, type(exc).__name__, user_hash, user_id, tr
            )
            t = texts(lang)
            msg = t.error_budget if isinstance(exc, BudgetExceeded) else t.error_unavailable
            yield ErrorEvent(message=msg)
        except GeneratorExit:  # client went away: model cost may already be spent (best effort)
            if not logged:
                _abort_log(deps, config, request_id, usage, user_hash, user_id, tr)
            raise
        finally:
            stream.close()


def _abort_log(
    deps: AgentDeps,
    config: RunnableConfig,
    request_id: str,
    usage: LLMUsage,
    user_hash: str | None,
    user_id: str | None = None,
    tr: Trace | None = None,
) -> None:
    try:
        state = deps.graph.get_state(config).values
        _write_log(
            deps.settings, request_id, state, usage, "ClientDisconnected", user_hash, user_id, tr
        )
    except Exception:  # never mask the disconnect with a logging error
        log.exception("chat log after disconnect failed")


def run_chat(
    deps: AgentDeps,
    thread_id: str,
    message: str,
    user_hash: str | None = None,
    user_id: str | None = None,
    lang: Lang = "de",
) -> Iterator[ChatEvent]:
    """Stream the events of one chat message. Each step runs in one fixed context, so the
    per-message cost metering holds even if the consumer calls next() from different threads."""
    ctx = contextvars.copy_context()
    inner = _run(deps, thread_id, message, user_hash, user_id, lang)
    try:
        while True:
            try:
                event = ctx.run(next, inner)
            except StopIteration:
                return
            yield event
    finally:
        ctx.run(inner.close)
