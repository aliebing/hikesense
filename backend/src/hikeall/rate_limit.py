"""Per-IP caps on chat requests, so a bot cannot run up the provider bill."""

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
    """Sliding windows (60 s and 24 h) per client IP. Process-wide state."""

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

    def acquire(self, ip: str) -> RateDecision:
        """Counts the call only if every window allows it."""
        now = self._clock()
        with self._lock:
            hits = self._hits[ip]
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
