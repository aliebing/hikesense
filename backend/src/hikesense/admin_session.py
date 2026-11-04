"""The admin's own sign-in for /backend: bcrypt check against HIKESENSE_ADMIN_PASSWORD_HASH and a
signed session cookie (HMAC with HIKESENSE_ADMIN_SESSION_SECRET). Independent of Supabase Auth:
no app account, and no Supabase token, ever opens the backend."""

from __future__ import annotations

import hashlib
import hmac
import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

import bcrypt

COOKIE = "hs_admin"
SESSION_S = 8 * 3600
ADMIN_NAME = "admin"


def check_password(password: str, bcrypt_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), bcrypt_hash.encode())
    except ValueError:  # not a bcrypt hash
        return False


def _sig(secret: str, exp: int) -> str:
    return hmac.new(secret.encode(), f"admin:{exp}".encode(), hashlib.sha256).hexdigest()


def issue(secret: str, now: float) -> str:
    exp = int(now) + SESSION_S
    return f"{exp}.{_sig(secret, exp)}"


def valid(cookie: str | None, secret: str, now: float) -> bool:
    if not cookie:
        return False
    exp_text, _, sig = cookie.partition(".")
    if not exp_text.isdigit() or not sig:
        return False
    exp = int(exp_text)
    return hmac.compare_digest(sig, _sig(secret, exp)) and exp > now


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

    def failed(self, ip: str) -> None:
        with self._lock:
            self._fails[ip].append(self._clock())

    def succeeded(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)
