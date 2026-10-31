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
import json
import logging
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import date
from functools import cached_property
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from hikeall import chatlog
from hikeall.adapters.open_meteo import SOURCE_ID as SOURCE_WEATHER
from hikeall.adapters.open_meteo import DayWeather, weather_source
from hikeall.agent.constraints import (
    ConstraintResult,
    PreferenceMatch,
    Scored,
    contradiction,
    format_deviation,
)
from hikeall.agent.events import CalendarLink, EventsResult, VerifiedRace
from hikeall.agent.grounding import Evidence, grounding_check, has_number, strip_unsat_claims
from hikeall.agent.multiday import (
    ACCESS_STRAIGHT,
    NEAR_M,
    NO_RAIN_VARIANT,
    DayPlan,
    MultidayPlan,
    RainVariant,
)
from hikeall.agent.prompts import (
    ANSWER_SYSTEM,
    CLARIFY_START,
    CONTRADICTION_HINT,
    DAY_UNKNOWN,
    ERROR_BUDGET,
    ERROR_UNAVAILABLE,
    EVENTS_FOUND,
    EVENTS_NONE,
    EVENTS_NOTE,
    EVENTS_SEARCH_DOWN,
    EVENTS_SKIPPED,
    GROUP_AUTO,
    GROUP_HAND,
    GROUPS_CHECK_ALL,
    GROUPS_CHECK_MIXED,
    GROUPS_FOUND,
    GROUPS_NO_COORDS,
    GROUPS_NONE,
    GROUPS_STALE,
    LEAK_REPLY,
    NO_PLAN_AT_START,
    NO_PLAN_TO_CHANGE,
    NO_SOURCE_REPLY,
    NO_TOURS_HINT,
    OTHER_REPLY,
    PLAN_SYSTEM,
    REACT_SYSTEM,
    REACT_TOURS,
    TOOL_ERROR,
    TOOL_LIMIT,
    TOOL_UNKNOWN,
    TRAIL_NOT_FOUND,
)
from hikeall.agent.request import MAX_DAYS, Clarify, Constraint, HikeRequest, RawRequest
from hikeall.agent.tools import (
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
from hikeall.agent.understand import DAYS_QUESTION, echo, parse, resolve, resolve_option
from hikeall.agent.understand import SYSTEM_PROMPT as UNDERSTAND_SYSTEM
from hikeall.agent.weather import NoForecast, is_rain_day
from hikeall.chatlog import ChatLogEntry
from hikeall.config import Settings
from hikeall.guard import INJECTION_REPLY, leaks_system_prompt, looks_like_injection, sanitize_text
from hikeall.llm.gateway import LLMGateway
from hikeall.llm.usage import BudgetExceeded, LLMError, LLMUsage, metered
from hikeall.numfmt import de
from hikeall.tags.vocabulary import TagVocabulary, fold

log = logging.getLogger(__name__)

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
_PROMPTS = (ANSWER_SYSTEM, PLAN_SYSTEM, REACT_SYSTEM, UNDERSTAND_SYSTEM)
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
_GROUP_KIND_WORD = {"lauftreff": " (Lauftreff)", "alpenverein": " (Alpenverein)", "wanderverein": " (Wanderverein)"}
_WEEKDAY = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
_LABEL = {
    "length_km": "Länge",
    "ascent_m": "Höhenmeter",
    "duration_h": "Dauer",
    "radius_km": "Entfernung",
    "roundtrip": "Rundweg",
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
    results: list[ConstraintResult]
    deviation_text: str | None = None
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


def _turn(message: str) -> State:
    return State(
        message=message,
        route="",
        intent=None,
        activity=None,
        current=None,
        clarify=None,
        reply=None,
        reason=None,
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
    )


def _emit(event: ChatEvent) -> None:
    get_stream_writer()(event)


def _de(x: float, decimals: int = 1) -> str:
    return de(x, decimals)  # half-up, like the grounding check


# --- search: cards, facts for the model, evidence -----------------------------------------


def _card(s: Scored, area: bool) -> TourCard:
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
        results=[_as_float(r) for r in s.results],
        deviation_text=format_deviation(s.violated) if s.violated else None,
        preference=s.preference,
    )


def _labels(vocab: TagVocabulary, tag_ids: list[str]) -> dict[str, str]:
    return {t: (tag.label if (tag := vocab.get(t)) else t) for t in tag_ids}


def _card_tags(cards: list[TourCard]) -> list[str]:
    return [t for c in cards for t in (*c.preference.met, *c.preference.missing, *c.preference.avoided_hit)]


def _as_float(r: ConstraintResult) -> ConstraintResult:
    """ascent_m is an int; the card field is float | bool | None (keeps JSON serialisation clean)."""
    if isinstance(r.actual, int) and not isinstance(r.actual, bool):
        return replace(r, actual=float(r.actual))
    return r


def _result_text(r: ConstraintResult) -> str:
    if r.ok is True:
        return f"{_LABEL[r.kind]} erfüllt"
    if r.ok is None:
        return f"{_LABEL[r.kind]} unbekannt (nicht prüfbar)"
    return f"{_LABEL[r.kind]} nicht erfüllt: {format_deviation(r)}"


def _search_data(
    req: HikeRequest, cards: list[TourCard], fallback: bool, vocab: TagVocabulary
) -> str:
    def label(tag_id: str) -> str:
        tag = vocab.get(tag_id)
        return tag.label if tag else tag_id

    lines = [echo(req, vocab)]
    lines.append(
        "Ausweichtouren (je genau eine Bedingung verletzt):"
        if fallback
        else "Passende Touren (nach Vorlieben sortiert):"
    )
    time_word = "Laufzeit" if req.activity == "run" else "Gehzeit"
    for i, card in enumerate(cards, start=1):
        facts = [
            f"Länge {_de(card.length_km)} km" if card.length_km is not None else "Länge unbekannt",
            f"Anstieg {card.ascent_m} Hm" if card.ascent_m is not None else "Anstieg unbekannt",
            f"{time_word} {_de(card.duration_h)} h"
            if card.duration_h is not None
            else "Zeit: keine Angabe",
        ]
        if card.distance_km is not None:  # area start: the tour lies in the area
            facts.append(f"Entfernung zum Start {_de(card.distance_km)} km")
        line = f"{i}. {card.name} – {', '.join(facts)}; Bedingungen: " + "; ".join(
            _result_text(r) for r in card.results
        )
        p = card.preference
        if p.met:
            line += "; Vorlieben erfüllt: " + ", ".join(label(t) for t in p.met)
        if p.missing:
            line += "; Vorlieben fehlen: " + ", ".join(label(t) for t in p.missing)
        if p.avoided_hit:
            line += "; enthält Gemiedenes: " + ", ".join(label(t) for t in p.avoided_hit)
        lines.append(line)
    if req.unmatched:
        lines.append("Nicht prüfbar: " + ", ".join(req.unmatched))
    return "\n".join(lines)


def _card_evidence(ev: Evidence, scored: list[Scored], area: bool) -> None:
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
                ev.numbers.append(format_deviation(r))


_BOUND_UNIT = {"length_km": "km", "ascent_m": "Hm", "duration_h": "h", "radius_km": "km"}


def _bound_evidence(ev: Evidence, constraints: list[Constraint]) -> None:
    """The user's own bounds (structured), never the free echo text: an unmatched wish such as
    "max. 3 km Asphalt" must not make "3 km" a supported number."""
    for c in constraints:
        unit = _BOUND_UNIT.get(c.kind)
        if unit:
            for value in (c.min, c.max, c.approx):
                ev.add(value, unit)


# --- multi-day: code sentences, facts for the model, evidence ------------------------------


def _sentence(text: str) -> str:
    return text if text.endswith(".") else f"{text}."


def _plan_prefix(
    plan: MultidayPlan,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
    lead: list[str] | None = None,
) -> str:
    """What the code says before the model: gaps, access paths, trail end, missing forecasts,
    missing rain variants and that times are without breaks (spec §8)."""
    lines = list(lead or [])
    lines += [f"Tag {d.day}: {d.gap}" for d in plan.days if d.gap]
    lines += plan.notes
    if plan.days and plan.days[0].date is None:
        lines.append("Wetter: ohne Datum keine Vorhersage")
    missing = {n: w.reason for n, w in weather.items() if isinstance(w, NoForecast)}
    if missing and len(missing) == len(weather) and len(set(missing.values())) == 1:
        lines.append(f"Wetter: {next(iter(missing.values()))}")
    else:
        lines += [f"Tag {n}: {reason}" for n, reason in missing.items()]
    lines += [f"Tag {n}: {NO_RAIN_VARIANT}" for n, v in rain.items() if v is None]
    if plan.days:
        lines.append("Alle Zeiten ohne Pausen (Gehzeit nach DIN 33466)")
    return "\n".join(dict.fromkeys(_sentence(x) for x in lines))


def _days_text(days: list[int]) -> str:
    """ "Tag 3", "Tag 1–4" (consecutive), "Tag 1, 3 und 5"."""
    if len(days) == 1:
        return f"Tag {days[0]}"
    if days == list(range(days[0], days[-1] + 1)):
        return f"Tag {days[0]}–{days[-1]}"
    return "Tag " + ", ".join(map(str, days[:-1])) + f" und {days[-1]}"


def _clock(t: Any) -> str:
    return f"{t:%H:%M} Uhr"


def _weather_text(w: DayWeather | NoForecast | None) -> str | None:
    if w is None:
        return None
    if isinstance(w, NoForecast):
        return "keine Vorhersage"
    parts = [w.text or "Wetterlage unbekannt"]
    if w.t_min_c is not None and w.t_max_c is not None:
        parts.append(f"{_de(w.t_min_c)} bis {_de(w.t_max_c)} °C")
    parts.append(
        f"Niederschlag {_de(w.precip_mm)} mm" if w.precip_mm is not None else "Niederschlag unbekannt"
    )
    if w.precip_prob_pct is not None:
        parts.append(f"Regenwahrscheinlichkeit {_de(w.precip_prob_pct, 0)} %")
    return ", ".join(parts)


def _day_line(
    d: DayPlan, w: DayWeather | NoForecast | None, has_rain: bool, v: RainVariant | None
) -> str:
    when = f" ({_WEEKDAY[d.date.weekday()]}, {d.date:%d.%m.%Y})" if d.date else ""
    facts = [
        f"{_de(d.length_km)} km"
        + (f" (davon Zuweg {_de(d.access_km, 2)} km Luftlinie)" if d.access_km else ""),
        f"Anstieg {d.ascent_m} Hm",
        f"Abstieg {d.descent_m} Hm",
        f"Gehzeit {_de(d.duration_h)} h",
        f"Start {_clock(d.start_time)}",
        f"Ankunft {_clock(d.arrival)}" if d.arrival else "Ankunft: keine (siehe Hinweis)",
    ]
    line = f"Tag {d.day}{when}: " + ", ".join(facts)
    if d.stop is not None:
        line += f"; Ziel: {d.stop.name or 'Unterkunft ohne Namen'}, {d.stop.dist_m} m vom Weg"
        if d.stop.dist_m > NEAR_M:
            line += f" ({ACCESS_STRAIGHT})"
    else:
        line += "; Ziel: Wegende"
    if d.gap:
        line += f"; Lücke (steht schon im Hinweis): {d.gap}"
    weather = _weather_text(w)
    line += f"; Wetter: {weather}" if weather else "; Wetter: ohne Datum keine Vorhersage"
    if has_rain and v is not None:
        line += (
            f"; Regenvariante: bis {v.station_name}, {_de(v.walk_km)} km, {v.ascent_m} Hm, "
            f"Gehzeit {_de(v.duration_h)} h – {v.note}"
        )
    elif has_rain:
        line += f"; Regenvariante: {NO_RAIN_VARIANT}"
    return line


def _plan_data(
    plan: MultidayPlan,
    start: str | None,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
    prefix: str,
) -> str:
    head = f"Mehrtagesplan {plan.trail_name}"
    if start:
        head += f" ab {start}"
    head += f", {len(plan.days)} Tag(e), Tagesziel {_de(plan.target_km)} km:"
    lines = [head]
    lines += [_day_line(d, weather.get(d.day), d.day in rain, rain.get(d.day)) for d in plan.days]
    lines.append("Hinweise (schreibt das Programm schon davor, nicht wiederholen):")
    lines.append(prefix)
    return "\n".join(lines)


def _plan_evidence(
    ev: Evidence,
    plan: MultidayPlan,
    weather: dict[int, DayWeather | NoForecast],
    rain: dict[int, RainVariant | None],
) -> None:
    ev.add_name(plan.trail_name)
    ev.add(plan.target_km, "km")
    for d in plan.days:
        for km in (d.start_km, d.end_km, d.walk_km, d.access_km, d.length_km):
            ev.add(km, "km")
        ev.add(d.ascent_m, "Hm")
        ev.add(d.descent_m, "Hm")
        ev.add(d.duration_h, "h")
        ev.numbers.append(_clock(d.start_time))
        if d.arrival is not None:
            ev.numbers.append(_clock(d.arrival))
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


def _events_text(found: EventsResult) -> str:
    def pages(n: int) -> str:
        return "Seite" if n == 1 else "Seiten"

    n, read = len(found.events), len(found.pages)
    if found.search_failed:
        text = EVENTS_SEARCH_DOWN
    elif n:
        noun = "Lauf" if n == 1 else "Läufe"
        text = EVENTS_FOUND.format(n=n, noun=noun, pages=read, page_noun=pages(read))
    else:
        text = EVENTS_NONE.format(pages=read, page_noun=pages(read))
    if found.skipped:
        reasons = "; ".join(dict.fromkeys(s.reason for s in found.skipped))
        k = len(found.skipped)
        text += EVENTS_SKIPPED.format(n=k, page_noun=pages(k), reasons=reasons)
    return text


# --- graph --------------------------------------------------------------------------------


def build_graph(deps: AgentDeps) -> Any:
    tools, gw, vocab, settings = deps.tools, deps.gateway, deps.vocab, deps.settings

    def guard(state: State) -> State:
        text = sanitize_text(state["message"])
        if looks_like_injection(text):
            return {
                "message": text,
                "guard": "injection",
                "reply": INJECTION_REPLY,
                "route": "reply",
            }
        return {"message": text, "route": "understand"}

    def _resolve(raw: RawRequest, message: str, previous: HikeRequest | None, **kw: Any):
        return resolve(vocab, raw, message, previous, today=deps.today(), trails=tools, **kw)

    def _continue_pending(pending: dict, message: str, previous: HikeRequest | None):
        """Answer to an open clarify question: a place answer continues the partial request
        without a model call; anything else goes to the model with the earlier message."""
        if pending.get("raw"):
            raw = RawRequest.model_validate(pending["raw"])
            if raw.intent in (*TOUR_INTENTS, "multiday"):
                start = resolve_option(vocab, message)
                if start is not None:
                    res = _resolve(raw, pending["message"], previous, start=start)
                else:
                    probe = raw.model_copy(update={"start_text": message})
                    res = _resolve(probe, pending["message"], previous)
                if isinstance(res, HikeRequest) and res.start is not None:
                    return raw, res, pending["message"]
        if pending["question"] == DAYS_QUESTION and re.fullmatch(r"\s*\d{1,2}\s*", message):
            message = f"{message.strip()} Tage"  # "3" answers "Wie viele Tage?"
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

    def understand(state: State) -> State:
        message = state["message"]
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
            raw, res, base = _continue_pending(state["pending"], message, previous)
        if res is None:
            raw = parse(gw, vocab, base, previous)
            res = _resolve(raw, base, previous)
        out: State = {"pending": None, "intent": raw.intent, "activity": raw.activity}
        if isinstance(res, HikeRequest):
            out.update(intent=res.intent, activity=res.activity)
            out["discarded_numbers"] = res.discarded_model_numbers
            if res.intent in (*TOUR_INTENTS, "groups") and res.start is None:
                res = Clarify(question=CLARIFY_START)
        if isinstance(res, Clarify):
            pending = {
                "raw": raw.model_dump(mode="json"),
                "message": base,
                "question": res.question,
            }
            return out | {"pending": pending, "clarify": res.model_dump(), "route": "clarify"}
        req = res
        if req.intent != "other":
            _emit(
                UnderstoodEvent(
                    text=echo(req, vocab),
                    request=req,
                    labels=_labels(vocab, [p.tag_id for p in req.preferences]),
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
        return out | {"reply": OTHER_REPLY, "route": "reply"}

    def clarify(state: State) -> State:
        c = state["clarify"] or {}
        _emit(ClarifyEvent(question=c.get("question", ""), options=c.get("options", [])))
        return {}

    def reply(state: State) -> State:
        for chunk in _CHUNK.findall(state["reply"] or ""):
            _emit(TokenEvent(text=chunk))
        return {}

    def search(state: State) -> State:
        req = HikeRequest.model_validate(state["current"])
        ev = Evidence()
        _bound_evidence(ev, req.constraints)
        contra = contradiction(req.constraints)
        if contra:  # no search, no fallback tours
            reason = f"Keine Tour erfüllt alle Wünsche, weil {contra}"
            _emit(ResultsEvent(cards=[], fallback_reason=reason))
            return {"reason": reason, "fixed": CONTRADICTION_HINT}
        result = tools.search_day_hikes(req)
        sel = result.selection
        scored = sel.matches or sel.fallbacks
        area = req.start is not None and req.start.kind == "area"
        cards = [_card(s, area) for s in scored]
        reason = None if sel.matches else sel.reason
        _emit(
            ResultsEvent(
                cards=cards, fallback_reason=reason, labels=_labels(vocab, _card_tags(cards))
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
            "last_tours": [{"trail_id": c.trail_id, "name": c.name} for c in cards],
        }
        if not cards:
            return out | {"fixed": NO_TOURS_HINT}
        data = _search_data(req, cards, not sel.matches, vocab)
        _card_evidence(ev, scored, area)
        ev.add(result.searched_radius_km, "km")
        ev.numbers.append(reason or "")
        if req.start is not None:
            ev.add_name(req.start.label)
        return out | {"data": data, "evidence": vars(ev)}

    def groups(state: State) -> State:
        req = HikeRequest.model_validate(state["current"])
        start = req.start
        if start is not None and start.lat is not None and start.lon is not None:
            lat, lon = start.lat, start.lon
        elif start is not None and start.bbox is not None:  # an area: its centre
            lat, lon = (start.bbox.south + start.bbox.north) / 2, (start.bbox.west + start.bbox.east) / 2
        else:
            return {"fixed": GROUPS_NO_COORDS.format(place=start.label if start else "diesem Ort")}
        place = start.label
        text = f"{req.question or ''} {state['message']}"
        kind = next((k for rx, k in _GROUP_KINDS if rx.search(text)), None)
        found = tools.find_groups(lat, lon, DEFAULT_GROUP_RADIUS_KM, kind, deps.today())
        radius = _de(DEFAULT_GROUP_RADIUS_KM)
        if not found:
            body = GROUPS_NONE.format(
                kind=_GROUP_KIND_WORD.get(kind or "", ""), radius=radius, place=place
            )
            return {"tool_calls": 1, "fixed": body}
        note = f"Stand: {min(g.checked_at for g in found):%d.%m.%Y}"
        _emit(GroupsEvent(groups=found, checked_note=note))
        stale = sum(g.stale for g in found)
        hand = sum(g.status == "geprüft" for g in found)
        if hand == len(found):
            check = GROUPS_CHECK_ALL.format(label=GROUP_HAND)
        elif hand == 0:
            check = GROUPS_CHECK_ALL.format(label=GROUP_AUTO)
        else:
            check = GROUPS_CHECK_MIXED.format(hand=hand, auto=len(found) - hand)
        body = GROUPS_FOUND.format(
            n=len(found), noun="Gruppe" if len(found) == 1 else "Gruppen",
            radius=radius, place=place, note=note, check=check,
        )  # fmt: skip
        if stale:
            body += GROUPS_STALE.format(n=stale, verb="ist" if stale == 1 else "sind")
        return {"tool_calls": 1, "fixed": body}

    def events(state: State) -> State:
        """Code-written answer (no model wording): the cards carry every value with its source."""
        req = HikeRequest.model_validate(state["current"])
        today = deps.today()
        found = tools.find_events(req.question or state["message"], today, settings.max_tool_calls)
        note = EVENTS_NOTE.format(date=f"{today:%d.%m.%Y}")
        _emit(EventsEvent(events=found.events, fallback=found.fallback, note=note))
        return {"tool_calls": found.calls, "fixed": _events_text(found)}

    def multiday(state: State) -> State:
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
        if rain_days and stored is not None:
            plan = stored
            unknown = [n for n in rain_days if not 1 <= n <= len(plan.days)]
            rain_days = [n for n in rain_days if n not in unknown]
            lead = [DAY_UNKNOWN.format(n=len(plan.days), day=n) for n in unknown]
            if not rain_days:
                return {"fixed": " ".join(lead)}
        elif req.day_change is not None:
            if stored is None:
                return {"fixed": NO_PLAN_TO_CHANGE}
            if not 1 <= req.day_change.day <= len(stored.days):
                # the plan can be shorter than asked for (trail end, dead end)
                return {"fixed": DAY_UNKNOWN.format(n=len(stored.days), day=req.day_change.day)}
            plan, calls = tools.change_day(stored, req.day_change, start_name=start), 1
        else:
            try:
                plan, calls = tools.plan_multiday(req), 1
            except StartNotOnTrail:
                tag = vocab.get(f"trail:{req.trail_id}")
                trail = tag.label if tag else str(req.trail_id)
                text = NO_PLAN_AT_START.format(start=start or "diesem Ort", trail=trail)
                return {"tool_calls": 1, "plan": None, "plan_request": None, "fixed": text}
            out["plan_request"] = state["current"]
        weather: dict[int, DayWeather | NoForecast] = {}
        dated = [d for d in plan.days if d.date is not None]  # no date: said once in the prefix
        if dated and calls + 2 <= budget:  # one DB lookup, one forecast request
            points = tools.day_end_points(plan.trail_id, dated)
            located = [d for d in dated if points.get(d.day)]
            wanted_points = [(*points[d.day], d.date) for d in located]
            got = tools.weather_days(wanted_points, deps.today())
            weather = {d.day: NoForecast("Ort für die Vorhersage unbekannt") for d in dated}
            weather |= {d.day: w for d, w in zip(located, got, strict=True)}
            calls += 2
        elif dated:
            lead.append(f"Für {_days_text([d.day for d in dated])} keine Vorhersage abgefragt")
        wanted = [n for n, w in weather.items() if isinstance(w, DayWeather) and is_rain_day(w)]
        wanted = sorted({*wanted, *rain_days})
        rain: dict[int, RainVariant | None] = {}
        if wanted and calls + 1 <= budget:
            rain = tools.rain_variants(plan, wanted)
            calls += 1
        elif wanted:
            lead.append(f"Für {_days_text(wanted)} keine Regenvariante berechnet")
        _emit(
            PlanEvent(
                plan=plan,
                weather=weather,
                rain=rain,
                labels=_labels(vocab, [t for t in [f"trail:{plan.trail_id}"] if t in vocab]),
                start_name=start,
            )
        )
        sources = tools.sources([i for i in plan.source_ids if i != SOURCE_WEATHER])
        if any(isinstance(w, DayWeather) for w in weather.values()):
            meteo = weather_source()
            sources.append(
                SourceBrief(id=meteo.id, name=meteo.name, url=meteo.url, license=meteo.license)
            )
        prefix = _plan_prefix(plan, weather, rain, lead)
        out |= {
            "plan": plan.model_dump(mode="json"),
            "tool_calls": calls,
            "sources": _add_sources([], sources),
            "prefix": prefix,
        }
        if not plan.days:  # only the dead-end note: nothing for the model to word
            return out
        ev = Evidence()
        _plan_evidence(ev, plan, weather, rain)
        ev.numbers.append(prefix)
        if start:
            ev.add_name(start)
        data = _plan_data(plan, start, weather, rain, prefix)
        return out | {"data": data, "system": PLAN_SYSTEM, "evidence": vars(ev)}

    def react(state: State) -> State:
        req = HikeRequest.model_validate(state["current"])
        question = req.question or state["message"]
        last_tours = state.get("last_tours") or []
        messages: list[BaseMessage] = [SystemMessage(REACT_SYSTEM)]
        ev = Evidence()
        if last_tours:  # follow-up questions about suggested tours need their ids (I-8)
            lines = [f"- {t['trail_id']}: {t['name']}" for t in last_tours]
            messages.append(SystemMessage(REACT_TOURS + "\n" + "\n".join(lines)))
            for t in last_tours:
                ev.add_name(t["name"])
        messages.append(HumanMessage(question))
        sources: list[dict] = []
        results: list[str] = []
        # the knowledge index is searched in code first, so an answer can rest on a source (I-3)
        pre = {"name": "search_knowledge", "args": {"query": question, "k": 5}, "id": "vorab"}
        content = _run_tool(pre, ev, results)
        if content[1] is not None:
            sources = _add_sources(sources, _sources_of(content[1]))
        executed = 1
        if not sources and not last_tours:  # nothing to stand on: no model free-answer
            return {"tool_calls": executed, "fixed": NO_SOURCE_REPLY}
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
                    messages.append(ToolMessage(TOOL_LIMIT, tool_call_id=call["id"]))
                    continue
                executed += 1
                content = _run_tool(call, ev, results)
                if content[1] is not None:
                    sources = _add_sources(sources, _sources_of(content[1]))
                messages.append(ToolMessage(content[0], tool_call_id=call["id"]))
        out: State = {"tool_calls": executed, "evidence": vars(ev), "sources": sources}
        if not sources:  # the model answered without any sourced tool result
            return {"tool_calls": executed, "fixed": NO_SOURCE_REPLY}
        if draft:
            return out | {"draft": draft}
        data = f"Frage: {question}\nWerkzeug-Ergebnisse:\n" + "\n".join(results)
        return out | {"data": data}

    def _run_tool(call: dict, ev: Evidence, results: list[str]) -> tuple[str, Any]:
        name = call["name"]
        args = call.get("args") or {}
        # a walking time counts as evidence only if its inputs are evidence themselves (I-8)
        trusted = name != "hiking_time" or _inputs_in_evidence(args, ev)
        try:
            result = _call_tool(tools, name, args)
        except LLMError:
            raise
        except _UnknownTool:
            return TOOL_UNKNOWN.format(name=name), None
        except Exception as exc:  # noqa: BLE001 - tool errors go back to the model, never abort
            return TOOL_ERROR.format(name=name, kind=type(exc).__name__), None
        if result is None:
            return TRAIL_NOT_FOUND, None
        dumped = _dump(result)
        if trusted:
            _walk(dumped, ev)
        content = json.dumps(dumped, ensure_ascii=False)
        results.append(f"{name}: {content}")
        return content, result

    def answer(state: State) -> State:
        if state.get("draft") or not state.get("data"):
            return {}
        return {"draft": gw.answer(state.get("system") or ANSWER_SYSTEM, state["data"])}

    def ground(state: State) -> State:
        draft, out = state.get("draft"), {}
        reason = state.get("reason")
        body = state.get("fixed") or ""
        if draft and any(leaks_system_prompt(draft, p) for p in _PROMPTS):
            body, out = LEAK_REPLY, {"guard": "leak"}
        elif draft:
            claims = 0
            if not reason:  # the code did not fall back: no claim that no tour meets all wishes
                draft, claims = strip_unsat_claims(draft)
            g = grounding_check(draft, Evidence(**state["evidence"]), deps.trail_names)
            # numbers are replaced; unknown tour names stay but get a hint (R21)
            body = g.text
            out = {
                "unsupported": len(g.unsupported),
                "unsupported_names": g.unsupported_names,
                "unsat_claims_removed": claims,
            }
        # the code's honest sentences come first, verbatim, whatever the model wrote
        lead = state.get("prefix") or ""
        text = "\n\n".join(x for x in (lead, f"{reason}." if reason else "", body) if x)
        for chunk in _CHUNK.findall(text):
            _emit(TokenEvent(text=chunk))
        if state.get("sources"):
            _emit(SourcesEvent(sources=[SourceBrief(**s) for s in state["sources"]]))
        return out

    def log(state: State, config: RunnableConfig) -> State:
        conf = config["configurable"]
        usage: LLMUsage = conf["usage"]
        _write_log(
            settings, conf["request_id"], state, usage, None, conf.get("user_hash")
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
) -> None:
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
        ),
    )


def _run(
    deps: AgentDeps, thread_id: str, message: str, user_hash: str | None
) -> Iterator[ChatEvent]:
    request_id = uuid.uuid4().hex
    with metered(max_cost_usd=deps.settings.max_cost_usd) as usage:
        config: RunnableConfig = {
            "configurable": {
                # keyed by user as well: a thread id alone never continues another user's chat
                "thread_id": f"{user_hash or ''}:{thread_id}",
                "usage": usage,
                "request_id": request_id,
                "user_hash": user_hash,
            }
        }
        stream = deps.graph.stream(_turn(message), config, stream_mode="custom")
        logged = False  # the log node writes the line and then emits "done"
        try:
            for event in stream:
                logged = logged or event.type == "done"
                yield event
        except LLMError as exc:
            logged = True
            state = deps.graph.get_state(config).values
            _write_log(deps.settings, request_id, state, usage, type(exc).__name__, user_hash)
            msg = ERROR_BUDGET if isinstance(exc, BudgetExceeded) else ERROR_UNAVAILABLE
            yield ErrorEvent(message=msg)
        except GeneratorExit:  # client went away: model cost may already be spent (best effort)
            if not logged:
                _abort_log(deps, config, request_id, usage, user_hash)
            raise
        finally:
            stream.close()


def _abort_log(
    deps: AgentDeps,
    config: RunnableConfig,
    request_id: str,
    usage: LLMUsage,
    user_hash: str | None,
) -> None:
    try:
        state = deps.graph.get_state(config).values
        _write_log(deps.settings, request_id, state, usage, "ClientDisconnected", user_hash)
    except Exception:  # never mask the disconnect with a logging error
        log.exception("chat log after disconnect failed")


def run_chat(
    deps: AgentDeps, thread_id: str, message: str, user_hash: str | None = None
) -> Iterator[ChatEvent]:
    """Stream the events of one chat message. Each step runs in one fixed context, so the
    per-message cost metering holds even if the consumer calls next() from different threads."""
    ctx = contextvars.copy_context()
    inner = _run(deps, thread_id, message, user_hash)
    try:
        while True:
            try:
                event = ctx.run(next, inner)
            except StopIteration:
                return
            yield event
    finally:
        ctx.run(inner.close)
