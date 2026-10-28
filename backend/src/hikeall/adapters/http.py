"""Shared httpx client factory and JSON request helper with timeouts and retry."""

from __future__ import annotations

import time
from typing import Any

import httpx

from hikeall.errors import HikeAllError

USER_AGENT = "HikeAll/0.1 (Black Forest hiking planner)"
_TRANSIENT_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_S = 30.0


def _retry_after_s(response: httpx.Response) -> float | None:
    """Seconds requested by a Retry-After header (numeric form), capped; None if absent."""
    try:
        return min(float(response.headers["Retry-After"]), MAX_RETRY_AFTER_S)
    except (KeyError, ValueError):
        return None


def make_http_client(timeout_s: float) -> httpx.Client:
    return httpx.Client(
        timeout=timeout_s, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    error_cls: type[HikeAllError],
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    retries: int = 1,
    backoff_s: float = 0.0,
    rate_limit_wait_s: float | None = None,
) -> Any:
    """Send a request and return parsed JSON; raise `error_cls` on any failure.

    `rate_limit_wait_s` is the pause after an HTTP 429 without a Retry-After header
    (e.g. Open-Meteo's per-minute limit); without it, 429 uses the normal backoff.
    """
    last_problem = "unknown error"
    wait_s: float | None = None
    for attempt in range(retries + 1):
        if attempt:
            delay = wait_s if wait_s is not None else backoff_s * attempt
            if delay:
                time.sleep(delay)
        wait_s = None
        try:
            response = client.request(method, url, params=params, data=data)
        except httpx.TransportError as exc:  # includes timeouts and connection errors
            last_problem = type(exc).__name__
            continue
        if response.status_code in _TRANSIENT_STATUS:
            last_problem = f"HTTP {response.status_code}"
            wait_s = _retry_after_s(response)  # the server says how long to back off
            if wait_s is None and response.status_code == 429:
                wait_s = rate_limit_wait_s
            continue
        if response.status_code >= 400:
            raise error_cls(f"{url} returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise error_cls(f"{url} returned invalid JSON") from exc
    raise error_cls(f"{url} failed after {retries + 1} attempts ({last_problem})")
