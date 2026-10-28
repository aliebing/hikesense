"""Overpass API client (OSM data, ODbL)."""

from __future__ import annotations

from typing import Any

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import OverpassError

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class OverpassClient:
    def __init__(self, http: httpx.Client, url: str = OVERPASS_URL, backoff_s: float = 5.0):
        self._http = http
        self._url = url
        self._backoff_s = backoff_s

    def run(self, query: str) -> dict[str, Any]:
        data = request_json(
            self._http, "POST", self._url, data={"data": query},
            error_cls=OverpassError, retries=2, backoff_s=self._backoff_s,
        )
        if not isinstance(data, dict) or "elements" not in data:
            raise OverpassError("Overpass response has no 'elements'")
        return data
