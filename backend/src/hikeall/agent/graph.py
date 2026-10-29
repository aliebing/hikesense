"""Agent flow (LangGraph): guard → understand → search | react | fixed reply → answer → ground → log.

Every number shown comes from a tool result of the round: the model only words the answer, the
grounding check replaces unsupported numbers, and the code prefixes the honest fallback sentence.
Events are streamed with LangGraph's custom stream writer; the conversation state (last request,
open clarify question) lives in a MemorySaver keyed by thread_id and holds only plain JSON data.
"""

from __future__ import annotations

import contextvars
import json
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from hikeall import chatlog
from hikeall.agent.constraints import (
    ConstraintResult,
    PreferenceMatch,
    Scored,
    contradiction,
    format_deviation,
)
from hikeall.agent.grounding import Evidence, grounding_check
from hikeall.agent.prompts import (
    ANSWER_SYSTEM,
    CLARIFY_START,
    CONTRADICTION_HINT,
    ERROR_BUDGET,
    ERROR_UNAVAILABLE,
    LEAK_REPLY,
    MULTIDAY_REPLY,
    NO_TOURS_HINT,
    OTHER_REPLY,
    REACT_SYSTEM,
    TOOL_ERROR,
    TOOL_LIMIT,
    TOOL_UNKNOWN,
    TRAIL_NOT_FOUND,
)
from hikeall.agent.request import Clarify, HikeRequest, RawRequest
from hikeall.agent.tools import (
    TOOL_SPECS,
    AgentTools,
    KnowledgeHit,
    LodgingBrief,
    SourceBrief,
    TrailDetails,
)
from hikeall.agent.understand import SYSTEM_PROMPT as UNDERSTAND_SYSTEM
from hikeall.agent.understand import echo, parse, resolve, resolve_option
from hikeall.chatlog import ChatLogEntry
from hikeall.config import Settings
from hikeall.guard import INJECTION_REPLY, leaks_system_prompt, looks_like_injection, sanitize_text
from hikeall.llm.gateway import LLMGateway
from hikeall.llm.usage import BudgetExceeded, LLMError, LLMUsage, metered
from hikeall.tags.vocabulary import TagVocabulary

__all__ = [
    "AgentDeps",
    "ChatEvent",
    "ClarifyEvent",
    "DoneEvent",
    "ErrorEvent",
    "ResultsEvent",
    "SourcesEvent",
    "TokenEvent",
    "TourCard",
    "UnderstoodEvent",
    "build_graph",
    "run_chat",
]

TOUR_INTENTS = ("day_hike", "change")
_PROMPTS = (ANSWER_SYSTEM, REACT_SYSTEM, UNDERSTAND_SYSTEM)
_CHUNK = re.compile(r"\S+\s*|\s+")
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
    distance_km: float
    cover_thumb_url: str | None = None
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


class ClarifyEvent(ChatEvent):
    type: Literal["clarify"] = "clarify"
    question: str
    options: list[str]


class ResultsEvent(ChatEvent):
    type: Literal["results"] = "results"
    cards: list[TourCard]
    fallback_reason: str | None


class TokenEvent(ChatEvent):
    type: Literal["token"] = "token"
    text: str


class SourcesEvent(ChatEvent):
    type: Literal["sources"] = "sources"
    sources: list[SourceBrief]


class DoneEvent(ChatEvent):
    type: Literal["done"] = "done"
    usage: LLMUsage
    unsupported: int


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

    @cached_property
    def graph(self) -> Any:
        return build_graph(self)


class State(TypedDict, total=False):
    message: str
    request: dict | None  # last tour request (for "change"), persists per thread
    pending: dict | None  # open clarify question with the partial request, persists per thread
    # per message:
    route: str
    intent: str | None
    activity: str | None
    current: dict | None
    clarify: dict | None
    reply: str | None
    reason: str | None
    data: str | None
    draft: str | None
    fixed: str | None
    evidence: dict
    sources: list[dict]
    tool_calls: int
    guard: str | None
    unsupported: int


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
        data=None,
        draft=None,
        fixed=None,
        evidence={"numbers": [], "names": []},
        sources=[],
        tool_calls=0,
        guard=None,
        unsupported=0,
    )


def _emit(event: ChatEvent) -> None:
    get_stream_writer()(event)


def _de(x: float, decimals: int = 1) -> str:
    s = f"{round(x, decimals):.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").removesuffix(".")
    return s.replace(".", ",")


# --- search: cards, facts for the model, evidence -----------------------------------------


def _card(s: Scored) -> TourCard:
    c = s.candidate
    return TourCard(
        trail_id=c.trail_id,
        name=c.name,
        length_km=c.length_km,
        ascent_m=c.ascent_m,
        duration_h=s.duration_h,
        distance_km=c.distance_km,
        results=[_as_float(r) for r in s.results],
        deviation_text=format_deviation(s.violated) if s.violated else None,
        preference=s.preference,
    )


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
            f"Entfernung zum Start {_de(card.distance_km)} km",
        ]
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


def _card_evidence(ev: Evidence, scored: list[Scored]) -> None:
    for s in scored:
        c = s.candidate
        ev.add_name(c.name)
        ev.add(c.length_km, "km")
        ev.add(c.ascent_m, "Hm")
        ev.add(c.descent_m, "Hm")
        ev.add(c.distance_km, "km")
        ev.add(s.duration_h, "h")
        for r in s.results:
            if r.ok is not True:
                ev.numbers.append(format_deviation(r))


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


def _dump(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [_dump(x) for x in result]
    return result


def _unit(key: str) -> str | None:
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
    seen = {(s["id"], s.get("url")) for s in have}
    out = list(have)
    for s in new:
        if (s.id, s.url) not in seen:
            seen.add((s.id, s.url))
            out.append(s.model_dump(mode="json"))
    return out


def _text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
    return "".join(parts).strip()


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

    def _continue_pending(pending: dict, message: str, previous: HikeRequest | None):
        """Answer to an open clarify question: a place answer continues the partial request
        without a model call; anything else goes to the model with the earlier message."""
        if pending.get("raw"):
            raw = RawRequest.model_validate(pending["raw"])
            if raw.intent in (*TOUR_INTENTS, "multiday"):
                start = resolve_option(vocab, message)
                if start is not None:
                    res = resolve(vocab, raw, pending["message"], previous, start=start)
                else:
                    probe = raw.model_copy(update={"start_text": message})
                    res = resolve(vocab, probe, pending["message"], previous)
                if isinstance(res, HikeRequest) and res.start is not None:
                    return raw, res, pending["message"]
        combined = f"{pending['message']}\nRückfrage: {pending['question']}\nAntwort: {message}"
        return None, None, combined

    def understand(state: State) -> State:
        message = state["message"]
        previous = HikeRequest.model_validate(state["request"]) if state.get("request") else None
        raw, res, base = None, None, message
        if state.get("pending"):
            raw, res, base = _continue_pending(state["pending"], message, previous)
        if res is None:
            raw = parse(gw, vocab, base, previous)
            res = resolve(vocab, raw, base, previous)
        out: State = {"pending": None, "intent": raw.intent, "activity": raw.activity}
        if isinstance(res, HikeRequest):
            out.update(intent=res.intent, activity=res.activity)
            if res.intent in TOUR_INTENTS and res.start is None:
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
            _emit(UnderstoodEvent(text=echo(req, vocab), request=req))
        out["current"] = req.model_dump(mode="json")
        if req.intent in TOUR_INTENTS:
            return out | {"request": out["current"], "route": "search"}
        if req.intent == "knowledge":
            return out | {"route": "react"}
        reply = MULTIDAY_REPLY if req.intent == "multiday" else OTHER_REPLY
        return out | {"reply": reply, "route": "reply"}

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
        ev = Evidence(numbers=[echo(req, vocab)])
        contra = contradiction(req.constraints)
        if contra:  # no search, no fallback tours
            reason = f"Keine Tour erfüllt alle Wünsche, weil {contra}"
            _emit(ResultsEvent(cards=[], fallback_reason=reason))
            return {"reason": reason, "fixed": CONTRADICTION_HINT}
        result = tools.search_day_hikes(req)
        sel = result.selection
        scored = sel.matches or sel.fallbacks
        cards = [_card(s) for s in scored]
        reason = None if sel.matches else sel.reason
        _emit(ResultsEvent(cards=cards, fallback_reason=reason))
        sources = [SourceBrief(id=s, name=None, url=None, license=None) for s in result.source_ids]
        out: State = {"tool_calls": 1, "reason": reason, "sources": _add_sources([], sources)}
        if not cards:
            return out | {"fixed": NO_TOURS_HINT}
        data = _search_data(req, cards, not sel.matches, vocab)
        _card_evidence(ev, scored)
        ev.add(result.searched_radius_km, "km")
        ev.numbers += [data, reason or ""]
        if req.start is not None:
            ev.add_name(req.start.label)
        return out | {"data": data, "evidence": vars(ev)}

    def react(state: State) -> State:
        req = HikeRequest.model_validate(state["current"])
        question = req.question or state["message"]
        messages: list[BaseMessage] = [SystemMessage(REACT_SYSTEM), HumanMessage(question)]
        ev = Evidence()
        sources: list[dict] = []
        results: list[str] = []
        executed = 0
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
        if draft:
            return out | {"draft": draft}
        data = f"Frage: {question}\nWerkzeug-Ergebnisse:\n" + "\n".join(results)
        return out | {"data": data}

    def _run_tool(call: dict, ev: Evidence, results: list[str]) -> tuple[str, Any]:
        name = call["name"]
        try:
            result = _call_tool(tools, name, call.get("args") or {})
        except LLMError:
            raise
        except _UnknownTool:
            return TOOL_UNKNOWN.format(name=name), None
        except Exception as exc:  # noqa: BLE001 - tool errors go back to the model, never abort
            return TOOL_ERROR.format(name=name, kind=type(exc).__name__), None
        if result is None:
            return TRAIL_NOT_FOUND, None
        dumped = _dump(result)
        _walk(dumped, ev)
        content = json.dumps(dumped, ensure_ascii=False)
        results.append(f"{name}: {content}")
        return content, result

    def answer(state: State) -> State:
        if state.get("draft") or not state.get("data"):
            return {}
        return {"draft": gw.answer(ANSWER_SYSTEM, state["data"])}

    def ground(state: State) -> State:
        draft, out = state.get("draft"), {}
        reason = state.get("reason")
        if draft and any(leaks_system_prompt(draft, p) for p in _PROMPTS):
            text, out = LEAK_REPLY, {"guard": "leak"}
        else:
            body = state.get("fixed") or ""
            if draft:
                g = grounding_check(draft, Evidence(**state["evidence"]))
                body, out = g.text, {"unsupported": len(g.unsupported)}
            text = "\n\n".join(x for x in (f"{reason}." if reason else "", body) if x)
        for chunk in _CHUNK.findall(text):
            _emit(TokenEvent(text=chunk))
        if state.get("sources"):
            _emit(SourcesEvent(sources=[SourceBrief(**s) for s in state["sources"]]))
        return out

    def log(state: State, config: RunnableConfig) -> State:
        conf = config["configurable"]
        usage: LLMUsage = conf["usage"]
        _write_log(settings, conf["request_id"], state, usage, None)
        _emit(DoneEvent(usage=usage, unsupported=state.get("unsupported", 0)))
        return {}

    g = StateGraph(State)
    for name, fn in [
        ("guard", guard),
        ("understand", understand),
        ("clarify", clarify),
        ("reply", reply),
        ("search", search),
        ("react", react),
        ("answer", answer),
        ("ground", ground),
        ("log", log),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", lambda s: s["route"], ["understand", "reply"])
    g.add_conditional_edges(
        "understand", lambda s: s["route"], ["clarify", "reply", "search", "react"]
    )
    g.add_edge("clarify", "log")
    g.add_edge("reply", "log")
    g.add_edge("search", "answer")
    g.add_edge("react", "answer")
    g.add_edge("answer", "ground")
    g.add_edge("ground", "log")
    g.add_edge("log", END)
    return g.compile(checkpointer=deps.checkpointer)


def _write_log(
    settings: Settings, request_id: str, state: dict, usage: LLMUsage, error: str | None
) -> None:
    chatlog.write(
        settings.chat_log_path,
        ChatLogEntry(
            request_id=request_id,
            intent=state.get("intent"),
            activity=state.get("activity"),
            tool_calls=state.get("tool_calls", 0),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            calls_without_cost=usage.calls_without_cost,
            grounding_unsupported=state.get("unsupported", 0),
            guard=state.get("guard"),
            error=error,  # exception class name only, never a message text
        ),
    )


def _run(deps: AgentDeps, thread_id: str, message: str) -> Iterator[ChatEvent]:
    request_id = uuid.uuid4().hex
    with metered(max_cost_usd=deps.settings.max_cost_usd) as usage:
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id, "usage": usage, "request_id": request_id}
        }
        try:
            yield from deps.graph.stream(_turn(message), config, stream_mode="custom")
        except LLMError as exc:
            state = deps.graph.get_state(config).values
            _write_log(deps.settings, request_id, state, usage, type(exc).__name__)
            msg = ERROR_BUDGET if isinstance(exc, BudgetExceeded) else ERROR_UNAVAILABLE
            yield ErrorEvent(message=msg)


def run_chat(deps: AgentDeps, thread_id: str, message: str) -> Iterator[ChatEvent]:
    """Stream the events of one chat message. Each step runs in one fixed context, so the
    per-message cost metering holds even if the consumer calls next() from different threads."""
    ctx = contextvars.copy_context()
    inner = _run(deps, thread_id, message)
    try:
        while True:
            try:
                event = ctx.run(next, inner)
            except StopIteration:
                return
            yield event
    finally:
        ctx.run(inner.close)
