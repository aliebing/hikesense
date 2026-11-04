"""Chat without an account: guests are counted per IP (IPv6 per /64) and all together, over a
sliding 24 h window kept in Postgres, so neither a restart nor a new IP lifts the total cap."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import psycopg
from starlette.requests import Request

from hikesense.config import Settings
from hikesense.db import connect

log = logging.getLogger(__name__)
_warned = False

WINDOW = "24 hours"
_LOCK_ID = 7_340_001  # pg_advisory_xact_lock key: one guest decision at a time


@dataclass(frozen=True)
class GuestDecision:
    allowed: bool
    reason: Literal["ok", "ip", "total"]
    retry_after_s: int = 0


class GuestQuota(Protocol):
    def acquire(self, key: str) -> GuestDecision: ...


def client_ip(request: Request, trusted_hops: int = 0) -> str:
    """The guest's address. Next's rewrite proxy (/api/chat) does NOT add to X-Forwarded-For, it
    passes the client's own header through, so that header is only believed when
    `trusted_hops` reverse proxies in front of Next (Caddy, nginx, Cloudflare) append to it: the
    entry `trusted_hops` from the end is the address the outermost trusted proxy saw. Otherwise
    (default, local setup) the peer address counts; behind Next that is Next itself, so all
    guests share one key. Safe, never forgeable; the total cap applies either way."""
    global _warned
    forwarded = request.headers.get("x-forwarded-for", "")
    if trusted_hops > 0:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    elif forwarded and not _warned:
        _warned = True
        log.warning(
            "X-Forwarded-For is ignored (HIKESENSE_TRUSTED_PROXY_HOPS=0): all guests and backend "
            "logins share one key. Behind a reverse proxy or cloudflared tunnel that is the only "
            "way in, set HIKESENSE_TRUSTED_PROXY_HOPS=1."
        )
    return request.client.host if request.client else "unknown"


def ip_key(ip: str) -> str:
    """IPv4 as is, IPv6 as its /64 network (one connection usually owns a whole /64)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def guest_owner(key: str) -> str:
    """Log owner of a guest: never the IP itself."""
    return "gast:" + hashlib.sha256(key.encode()).hexdigest()[:12]


def _retry(conn: psycopg.Connection, key: str | None) -> int:
    where, params = ("where key = %s", (key,)) if key is not None else ("", ())
    row = conn.execute(
        f"select ceil(extract(epoch from min(ts) + interval '{WINDOW}' - now())) from guest_requests {where}",
        params,
    ).fetchone()
    return max(1, int(row[0])) if row and row[0] is not None else 1


def quota_acquire(
    conn: psycopg.Connection, key: str, per_day: int, total_per_day: int
) -> GuestDecision:
    """Counts one guest request for `key` if both caps allow it. Runs in the caller's
    transaction (the advisory lock is released at its end); the caller commits."""
    conn.execute("select pg_advisory_xact_lock(%s)", (_LOCK_ID,))
    conn.execute(f"delete from guest_requests where ts < now() - interval '{WINDOW}'")
    mine, total = conn.execute(
        "select count(*) filter (where key = %s), count(*) from guest_requests", (key,)
    ).fetchone()
    if mine >= per_day:
        return GuestDecision(False, "ip", _retry(conn, key))
    if total >= total_per_day:
        return GuestDecision(False, "total", _retry(conn, None))
    conn.execute("insert into guest_requests (key) values (%s)", (key,))
    return GuestDecision(True, "ok", 0)


class DbGuestQuota:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def acquire(self, key: str) -> GuestDecision:
        s = self._settings
        with connect(s.supabase_db_url) as conn:
            d = quota_acquire(conn, key, s.hikesense_guest_per_day, s.hikesense_guest_total_per_day)
            conn.commit()
            return d
