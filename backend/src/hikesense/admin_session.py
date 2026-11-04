"""The admin's own sign-in for /backend: bcrypt check against HIKESENSE_ADMIN_PASSWORD_HASH and a
signed session cookie (HMAC with HIKESENSE_ADMIN_SESSION_SECRET). Independent of Supabase Auth:
no app account, and no Supabase token, ever opens the backend."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

import bcrypt

COOKIE = "hs_admin"
SESSION_S = 8 * 3600
ADMIN_NAME = "admin"


MAX_PASSWORD_BYTES = 72  # bcrypt ignores (bcrypt 4) or refuses (bcrypt 5) anything longer


def check_password(password: str, bcrypt_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, bcrypt_hash.encode())
    except ValueError:  # not a bcrypt hash
        return False


def _ascii_int(text: str) -> int | None:
    """Only 0-9: str.isdigit() also accepts "²" or Arabic-Indic digits, which int() rejects."""
    return int(text) if text and text.isascii() and text.isdigit() else None


class Sessions:
    """Signed backend sessions that the server also remembers: `exp.sid.sig`, HMAC over expiry
    and session id. Sign-out drops the id, so a copied cookie stops working at once; a restart
    forgets all ids (the admin signs in again). One process (uvicorn without workers)."""

    MAX = 50  # sessions kept at once; the oldest goes first

    def __init__(self) -> None:
        self._live: dict[str, int] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._live)

    @staticmethod
    def _sig(secret: str, exp: int, sid: str) -> str:
        return hmac.new(secret.encode(), f"admin:{exp}:{sid}".encode(), hashlib.sha256).hexdigest()

    def issue(self, secret: str, now: float) -> str:
        exp, sid = int(now) + SESSION_S, secrets.token_urlsafe(16)
        with self._lock:
            self._live = {k: e for k, e in self._live.items() if e > now}
            while len(self._live) >= self.MAX:
                self._live.pop(min(self._live, key=self._live.__getitem__))
            self._live[sid] = exp
        return f"{exp}.{sid}.{self._sig(secret, exp, sid)}"

    def valid(self, cookie: str | None, secret: str, now: float) -> bool:
        parts = (cookie or "").split(".")
        if len(parts) != 3:
            return False
        exp, sid, sig = _ascii_int(parts[0]), parts[1], parts[2]
        if exp is None or not sid or not sig:
            return False
        if not hmac.compare_digest(sig, self._sig(secret, exp, sid)) or exp <= now:
            return False
        with self._lock:
            return self._live.get(sid) == exp

    def revoke(self, cookie: str | None) -> None:
        parts = (cookie or "").split(".")
        if len(parts) == 3:
            with self._lock:
                self._live.pop(parts[1], None)


class LoginThrottle:
    """At most `max_failures` failed sign-ins per IP within `window_s`; process-wide."""

    def __init__(
        self,
        max_failures: int = 5,
        window_s: float = 900,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max, self._window, self._clock = max_failures, window_s, clock
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, ip: str, now: float) -> deque[float]:
        q = self._fails[ip]
        while q and q[0] <= now - self._window:
            q.popleft()
        if not q:
            self._fails.pop(ip, None)
        return q

    def blocked(self, ip: str) -> int:
        """Seconds until the next attempt is allowed; 0 when free."""
        with self._lock:
            now = self._clock()
            q = self._prune(ip, now)
            if len(q) < self._max:
                return 0
            return max(1, math.ceil(q[0] + self._window - now))

    def try_acquire(self, ip: str) -> int:
        """Reserves one attempt before the password check (0 = go ahead, else Retry-After
        seconds). Counting at the start keeps parallel requests from slipping past the cap;
        a successful sign-in clears the IP with `succeeded`."""
        with self._lock:
            now = self._clock()
            q = self._prune(ip, now)
            if len(q) >= self._max:
                return max(1, math.ceil(q[0] + self._window - now))
            self._fails[ip].append(now)
            return 0

    def failed(self, ip: str) -> None:
        with self._lock:
            self._fails[ip].append(self._clock())

    def succeeded(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)
