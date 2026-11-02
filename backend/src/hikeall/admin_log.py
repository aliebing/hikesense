"""Read-only access to the chat log for the admin backend (pure functions, no FastAPI/DB)."""

from __future__ import annotations

import json
from pathlib import Path

from hikeall.chatlog import hash_user
from hikeall.roles import Profile

UNKNOWN = "unknown"
# Same as graph.TOUR_INTENTS (not imported to keep the agent graph out of here).
TOUR_INTENTS = ("day_hike", "change")


class LogReader:
    def __init__(self, path: Path):
        self.path = path
        self._sig: tuple[int, int] | None = None
        self._cache: list[dict] = []

    def entries(self) -> list[dict]:
        try:
            st = self.path.stat()
        except OSError:
            self._sig, self._cache = None, []
            return []
        sig = (st.st_mtime_ns, st.st_size)
        if sig != self._sig:
            self._cache = self._load()
            self._sig = sig
        return self._cache

    def _load(self) -> list[dict]:
        rows: list[dict] = []
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        for line in text.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("request_id"):
                rows.append(obj)
        order = sorted(range(len(rows)), key=lambda i: (str(rows[i].get("ts") or ""), i), reverse=True)
        return [rows[i] for i in order]


def owner_of(entry: dict, profiles: list[Profile]) -> str:
    uid = entry.get("user_id")
    if uid and any(p.user_id == uid for p in profiles):
        return uid
    h = entry.get("user_hash")
    if h:
        for p in profiles:
            if hash_user(p.user_id) == h:
                return p.user_id
    return UNKNOWN


def _cost(entry: dict) -> float | None:
    cost = entry.get("cost_usd")
    if cost is None:
        return None
    if (entry.get("calls_without_cost") or 0) > 0 and cost == 0:
        return None
    return float(cost)


def summary(entry: dict, owner: str, email: str | None) -> dict:
    detailed = "message" in entry
    candidates = entry.get("candidates") or []
    hits = None
    if detailed and entry.get("intent") in TOUR_INTENTS:
        hits = sum(1 for c in candidates if c.get("status") in ("shown", "fallback"))
    fallback = bool(entry.get("fallback_reason")) or any(
        c.get("status") == "fallback" for c in candidates
    )
    return {
        "request_id": entry.get("request_id"),
        "ts": entry.get("ts"),
        "owner": owner,
        "email": email,
        "message": entry.get("message"),
        "intent": entry.get("intent"),
        "hits": hits,
        "fallback": fallback,
        "tool_calls": entry.get("tool_calls"),
        "tokens": (entry.get("input_tokens") or 0) + (entry.get("output_tokens") or 0),
        "cost_usd": _cost(entry),
        "duration_ms": entry.get("duration_ms"),
        "error": entry.get("error"),
        "detailed": detailed,
    }


def _email_map(profiles: list[Profile]) -> dict[str, str | None]:
    return {p.user_id: p.email for p in profiles}


def users(entries: list[dict], profiles: list[Profile]) -> list[dict]:
    counts: dict[str, int] = {}
    for e in entries:
        o = owner_of(e, profiles)
        counts[o] = counts.get(o, 0) + 1
    rows = [
        {"user_id": p.user_id, "email": p.email, "role": p.role, "searches": counts.get(p.user_id, 0)}
        for p in profiles
    ]
    rows.sort(key=lambda r: (-r["searches"], r["email"] or ""))
    if counts.get(UNKNOWN, 0) > 0:
        rows.append({"user_id": UNKNOWN, "email": None, "role": None, "searches": counts[UNKNOWN]})
    return rows


def searches(
    entries: list[dict], profiles: list[Profile], owner: str | None, offset: int, limit: int
) -> dict:
    emails = _email_map(profiles)
    selected = []
    for e in entries:
        o = owner_of(e, profiles)
        if owner is None or o == owner:
            selected.append((e, o))
    costs = [c for c in (_cost(e) for e, _ in selected) if c is not None]
    durations = [e["duration_ms"] for e, _ in selected if e.get("duration_ms") is not None]
    page = selected[offset : offset + limit]
    return {
        "items": [summary(e, o, emails.get(o)) for e, o in page],
        "total": len(selected),
        "sums": {
            "count": len(selected),
            "cost_usd": sum(costs),
            "avg_duration_ms": sum(durations) / len(durations) if durations else None,
        },
    }


def detail(entries: list[dict], profiles: list[Profile], request_id: str) -> dict | None:
    for e in entries:
        if e.get("request_id") == request_id:
            o = owner_of(e, profiles)
            return {**e, "owner": o, "email": _email_map(profiles).get(o)}
    return None
