"""Read-only access to the chat log for the admin backend (pure functions, no FastAPI/DB)."""

from __future__ import annotations

import json
from pathlib import Path

from hikesense.chatlog import hash_user
from hikesense.users import AppUser

UNKNOWN = "unknown"
GUEST = "guest"  # all guest requests (user_hash "gast:…") form one owner


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
        order = sorted(
            range(len(rows)), key=lambda i: (str(rows[i].get("ts") or ""), i), reverse=True
        )
        return [rows[i] for i in order]


def owner_of(entry: dict, accounts: list[AppUser]) -> str:
    if str(entry.get("user_hash") or "").startswith("gast:"):
        return GUEST
    uid = entry.get("user_id")
    if uid and any(p.user_id == uid for p in accounts):
        return uid
    h = entry.get("user_hash")
    if h:
        for p in accounts:
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


def account_label(owner: str) -> str | None:
    """Short pseudonym of an account for the search views ("#3f9a2c"): who searched is visible
    without the e-mail address (data minimisation). The account list shows label and e-mail side by
    side, for the rare case the person is needed. None for guests and unknown owners."""
    if owner in (GUEST, UNKNOWN):
        return None
    return "#" + hash_user(owner)[:6]


def summary(entry: dict, owner: str) -> dict:
    detailed = "llm_calls" in entry  # present in every new line, even error lines
    candidates = entry.get("candidates") or []
    hits = None
    if any(t.get("name") == "search_day_hikes" for t in entry.get("tools") or []):
        hits = sum(1 for c in candidates if c.get("status") in ("shown", "fallback"))
    fallback = bool(entry.get("fallback_reason")) or any(
        c.get("status") == "fallback" for c in candidates
    )
    return {
        "request_id": entry.get("request_id"),
        "ts": entry.get("ts"),
        "owner": owner,
        "account": account_label(owner),
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


def users(entries: list[dict], accounts: list[AppUser]) -> list[dict]:
    counts: dict[str, int] = {}
    for e in entries:
        o = owner_of(e, accounts)
        counts[o] = counts.get(o, 0) + 1
    rows = [
        {
            "user_id": p.user_id,
            "account": account_label(p.user_id),
            "email": p.email,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "last_sign_in_at": p.last_sign_in_at.isoformat() if p.last_sign_in_at else None,
            "searches": counts.get(p.user_id, 0),
        }
        for p in accounts
    ]
    rows.sort(key=lambda r: (-r["searches"], r["email"] or ""))
    for owner, status in ((GUEST, "gast"), (UNKNOWN, None)):
        if counts.get(owner, 0) > 0:
            rows.append(
                {
                    "user_id": owner,
                    "account": None,
                    "email": None,
                    "status": status,
                    "created_at": None,
                    "last_sign_in_at": None,
                    "searches": counts[owner],
                }
            )
    return rows


def searches(
    entries: list[dict], accounts: list[AppUser], owner: str | None, offset: int, limit: int
) -> dict:
    selected = []
    for e in entries:
        o = owner_of(e, accounts)
        if owner is None or o == owner:
            selected.append((e, o))
    costs = [c for c in (_cost(e) for e, _ in selected) if c is not None]
    durations = [e["duration_ms"] for e, _ in selected if e.get("duration_ms") is not None]
    page = selected[offset : offset + limit]
    return {
        "items": [summary(e, o) for e, o in page],
        "total": len(selected),
        "sums": {
            "count": len(selected),
            "cost_usd": sum(costs) if costs else None,
            "avg_duration_ms": sum(durations) / len(durations) if durations else None,
        },
    }


def detail(entries: list[dict], accounts: list[AppUser], request_id: str) -> dict | None:
    for e in entries:
        if e.get("request_id") == request_id:
            o = owner_of(e, accounts)
            shown = {k: v for k, v in e.items() if k != "user_id"}  # the owner field says whose it is
            return {**shown, "owner": o, "account": account_label(o)}
    return None
