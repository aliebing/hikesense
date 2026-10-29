"""Per-request LLM usage metering. A ContextVar keeps concurrent requests apart while the
gateway itself is shared. Cost is only what OpenRouter reports (usage.cost), never estimated."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage

from hikeall.errors import HikeAllError


class LLMError(HikeAllError):
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


_current: ContextVar[LLMUsage | None] = ContextVar("hikeall_llm_usage", default=None)


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


def record_usage(message: Any) -> None:
    """Add one model reply to the current metering scope; raise BudgetExceeded over the limit."""
    usage = _current.get()
    if usage is None or not isinstance(message, AIMessage):
        return
    meta = message.usage_metadata or {}
    token_usage = (message.response_metadata or {}).get("token_usage") or {}
    cost = token_usage.get("cost") if isinstance(token_usage, dict) else None
    usage.calls += 1
    usage.input_tokens += _count(meta.get("input_tokens"))
    usage.output_tokens += _count(meta.get("output_tokens"))
    if isinstance(cost, int | float) and not isinstance(cost, bool) and cost >= 0:
        usage.cost_usd += float(cost)
    else:
        usage.calls_without_cost += 1
    if usage.max_cost_usd is not None and usage.cost_usd > usage.max_cost_usd:
        raise BudgetExceeded(f"Kosten {usage.cost_usd:.4f} USD über Limit {usage.max_cost_usd}")
