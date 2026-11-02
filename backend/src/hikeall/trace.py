"""Per-request trace of LLM and tool calls, for the admin backend. A ContextVar keeps
concurrent requests apart (same pattern as llm/usage.py). Costs are only what OpenRouter
reported (None otherwise). Exception message texts are never stored, only class names."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date
from datetime import time as dtime
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from hikeall.llm.usage import call_usage

log = logging.getLogger(__name__)

TOOL_RESULT_MAX_CHARS = 20_000


@dataclass
class Trace:
    started: float = field(default_factory=time.monotonic)
    llm_calls: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


_current: ContextVar[Trace | None] = ContextVar("hikeall_trace", default=None)


@contextmanager
def traced() -> Iterator[Trace]:
    t = Trace()
    token = _current.set(t)
    try:
        yield t
    finally:
        _current.reset(token)


def current() -> Trace | None:
    return _current.get()


def record_llm(
    step: str, model: str | None, messages: list[dict], output: Any, reply: Any, duration_ms: int
) -> None:
    t = _current.get()
    if t is None:
        return
    input_tokens, output_tokens, cost = call_usage(reply)
    messages, output, output_truncated = _bounded(messages, output)
    t.llm_calls.append(
        {
            "step": step,
            "model": model,
            "messages": messages,
            "output": output,
            "output_truncated": output_truncated,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "duration_ms": duration_ms,
        }
    )


def _cut(text: str) -> tuple[str, bool]:
    return (text[:TOOL_RESULT_MAX_CHARS], True) if len(text) > TOOL_RESULT_MAX_CHARS else (text, False)


def _bounded(messages: list[dict], output: Any) -> tuple[list[dict], Any, bool]:
    """Cut every message content and a text output to TOOL_RESULT_MAX_CHARS (flagged)."""
    out_messages = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            cut, was_cut = _cut(content)
            m = {**m, "content": cut, **({"truncated": True} if was_cut else {})}
        out_messages.append(m)
    truncated = False
    if isinstance(output, str):
        output, truncated = _cut(output)
    elif isinstance(output, dict) and isinstance(output.get("content"), str):
        cut, truncated = _cut(output["content"])
        output = {**output, "content": cut}
    return out_messages, output, truncated


_ROLES = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}


def _text(content: Any) -> str:
    return (
        content
        if isinstance(content, str)
        else json.dumps(to_jsonable(content), ensure_ascii=False)
    )


def _calls(message: AIMessage) -> list[dict]:
    return [
        {"name": c.get("name"), "args": to_jsonable(c.get("args"))}
        for c in message.tool_calls or []
    ]


def message_dicts(messages: Sequence[BaseMessage]) -> list[dict]:
    out = []
    for m in messages:
        d: dict = {"role": _ROLES.get(m.type, m.type), "content": _text(m.content)}
        if isinstance(m, AIMessage) and m.tool_calls:
            d["tool_calls"] = _calls(m)
        out.append(d)
    return out


def ai_output(message: AIMessage) -> dict:
    """Trace output of a tool round: the text plus the requested tool calls."""
    return {"content": _text(message.content), "tool_calls": _calls(message)}


def to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json", warnings=False)
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, set | frozenset):
        return sorted((to_jsonable(v) for v in obj), key=lambda v: (str(type(v)), str(v)))
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, date | dtime):
        return obj.isoformat()
    return str(obj)


class TracedTools:
    """Wraps a tools object; every public callable is recorded in the active trace."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if name.startswith("_") or not callable(attr):
            return attr

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.monotonic()
            try:
                result = attr(*args, **kwargs)
            except Exception as exc:
                self._record(name, args, kwargs, None, False, started, type(exc).__name__)
                raise
            try:
                text = json.dumps(to_jsonable(result), ensure_ascii=False)
            except Exception:  # noqa: BLE001 - unserializable result, fall back to str
                text = str(result)
            truncated = len(text) > TOOL_RESULT_MAX_CHARS
            self._record(name, args, kwargs, text[:TOOL_RESULT_MAX_CHARS], truncated, started, None)
            return result

        return wrapper

    @staticmethod
    def _record(name, args, kwargs, result, truncated, started, error) -> None:
        t = _current.get()
        if t is None:
            return
        try:
            call_args = {f"arg{i}": a for i, a in enumerate(args)} | kwargs
            t.tool_calls.append(
                {
                    "name": name,
                    "args": to_jsonable(call_args),
                    "result": result,
                    "truncated": truncated,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "error": error,
                }
            )
        except Exception:
            log.exception("Trace: Tool-Aufruf konnte nicht aufgezeichnet werden")
