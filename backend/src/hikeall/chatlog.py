"""Chat log: one JSON line per request with metrics only, never message text."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ChatLogEntry(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    request_id: str
    intent: str | None = None
    activity: str | None = None
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls_without_cost: int = 0
    grounding_unsupported: int = 0
    guard: str | None = None
    error: str | None = None


def write(path: Path, entry: ChatLogEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
