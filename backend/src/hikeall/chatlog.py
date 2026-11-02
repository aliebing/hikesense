"""Chat log: one JSON line per request. Holds search text, prompts and tool calls for the admin
backend; never passwords, tokens or exception texts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ChatLogEntry(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    request_id: str
    user_hash: str | None = None  # first 12 chars of sha256(user id), never the id itself
    intent: str | None = None
    activity: str | None = None
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls_without_cost: int = 0
    grounding_unsupported: int = 0  # numbers only
    grounding_unsupported_names: int = 0  # count only, never the names
    unsat_claims_removed: int = 0  # false "no tour meets all wishes" claims removed
    guard: str | None = None
    # model-filled conditions the user never wrote, discarded (R27): numbers (length, ascent, duration,
    # radius, …) and also a roundtrip yes/no — the name is historical, the count covers both
    discarded_model_numbers: int = 0
    error: str | None = None
    # details for the admin backend (all defaulted: old lines stay readable)
    user_id: str | None = None
    message: str | None = None  # the sanitised current message
    previous_messages: list[str] = []  # up to 5 earlier messages of the thread, oldest first
    request: dict | None = None  # the understood HikeRequest
    answer: str | None = None  # the text the user saw: answer, question or fixed reply
    fallback_reason: str | None = None
    candidates: list[dict] = []
    plan: dict | None = None  # multi-day plan, route "multiday" only
    weather_days: dict | None = None  # weather day finder (day hikes with a weather wish)
    llm_calls: list[dict] = []
    tools: list[dict] = []
    duration_ms: int | None = None


def hash_user(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def write(path: Path, entry: ChatLogEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
