"""Per-request LLM usage metering. A ContextVar keeps concurrent requests apart while the
gateway itself is shared. Cost is only what OpenRouter reports (usage.cost), never estimated."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage

from hikesense.errors import HikeSenseError


class LLMError(HikeSenseError):
    """Base class for LLM failures."""


class LLMUnavailable(LLMError):
    """The model service is not configured or cannot be reached."""


class LLMBadOutput(LLMError):
    """The model returned no usable (or invalid structured) output."""


class BudgetExceeded(LLMError):
    """The cost of one request went over the limit."""


@dataclass
class LLMUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls_without_cost: int = 0
    max_cost_usd: float | None = None


_current: ContextVar[LLMUsage | None] = ContextVar("hikesense_llm_usage", default=None)


@contextmanager
def metered(max_cost_usd: float | None = None) -> Iterator[LLMUsage]:
    usage = LLMUsage(max_cost_usd=max_cost_usd)
    token = _current.set(usage)
    try:
        yield usage
    finally:
        _current.reset(token)


def _count(value: Any) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def call_usage(message: Any) -> tuple[int, int, float | None]:
    """Input tokens, output tokens and the cost OpenRouter reported (None if not reported)."""
    if not isinstance(message, AIMessage):
        return 0, 0, None
    meta = message.usage_metadata or {}
    token_usage = (message.response_metadata or {}).get("token_usage") or {}
    cost = token_usage.get("cost") if isinstance(token_usage, dict) else None
    if not (isinstance(cost, int | float) and not isinstance(cost, bool) and cost >= 0):
        cost = None
    return (
        _count(meta.get("input_tokens")),
        _count(meta.get("output_tokens")),
        (None if cost is None else float(cost)),
    )


def record_usage(message: Any) -> None:
    """Add one model reply to the current metering scope; raise BudgetExceeded over the limit."""
    usage = _current.get()
    if usage is None or not isinstance(message, AIMessage):
        return
    input_tokens, output_tokens, cost = call_usage(message)
    usage.calls += 1
    usage.input_tokens += input_tokens
    usage.output_tokens += output_tokens
    if cost is not None:
        usage.cost_usd += cost
    else:
        usage.calls_without_cost += 1
    if usage.max_cost_usd is not None and usage.cost_usd > usage.max_cost_usd:
        raise BudgetExceeded(f"Kosten {usage.cost_usd:.4f} USD über Limit {usage.max_cost_usd}")
