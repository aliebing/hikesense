"""Per-user caps on chat requests, so a bot cannot run up the provider bill."""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

MINUTE_S = 60
DAY_S = 86400


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after_s: int = 0


class RateLimiter:
    """Sliding windows (60 s and 24 h) per key (user id). Process-wide state."""

    def __init__(
        self,
        per_minute: int = 10,
        per_day: int = 100,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = ((MINUTE_S, per_minute), (DAY_S, per_day))
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_prune = clock()

    def prune(self, now: float) -> None:
        """Drops keys without a hit in the last 24 h (bounds memory). Caller holds no lock."""
        with self._lock:
            self._prune_locked(now)

    def _prune_locked(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= DAY_S]:
            del self._hits[key]
        self._last_prune = now

    def acquire(self, key: str) -> RateDecision:
        """Counts the call only if every window allows it."""
        now = self._clock()
        with self._lock:
            if now - self._last_prune >= MINUTE_S:  # at most once a minute
                self._prune_locked(now)
            hits = self._hits[key]
            while hits and now - hits[0] >= DAY_S:
                hits.popleft()
            wait = 0
            for window, limit in self._limits:
                recent = [t for t in hits if now - t < window]
                if len(recent) >= limit:
                    wait = max(wait, math.ceil(window - (now - recent[-limit])))
            if wait:
                return RateDecision(False, wait)
            hits.append(now)
            return RateDecision(True)
