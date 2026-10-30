"""Web search for official running events via the OpenRouter web plugin (Exa). The hits are the
url_citation annotations of one completion; its cost (search included) is metered like every
model call. Portals whose terms forbid reuse are never searched and never fetched."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

# laufen.de, marathon.de, DUV, LADV, HDsports: terms forbid copying (note 2026-10-29, §2)
BLOCKED_DOMAINS = [
    "laufen.de",
    "marathon.de",
    "d-u-v.org",
    "ultra-marathon.org",
    "ladv.de",
    "hdsports.org",
]
MAX_RESULTS = 5
SEARCH_PROMPT = (
    "Finde die offiziellen Webseiten der Veranstalter (nicht Laufkalender oder Ergebnisportale) "
    "für kommende Laufveranstaltungen und nenne sie mit Link: {query}"
)


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str


class WebSearch(Protocol):
    def search(self, query: str, k: int = 5) -> list[SearchHit]: ...


class WebCompletion(Protocol):
    def web_completion(self, user: str, plugin: dict) -> dict: ...


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def is_blocked(url: str) -> bool:
    """True for a blocked domain and every subdomain of it (www.laufen.de, sub.hdsports.org)."""
    host = host_of(url)
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


def is_web_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


class OpenRouterWebSearch:
    """One completion with the web plugin; the gateway records its cost (record_usage)."""

    def __init__(self, gateway: WebCompletion) -> None:
        self._gateway = gateway

    def search(self, query: str, k: int = 5) -> list[SearchHit]:
        plugin = {
            "id": "web",
            "engine": "exa",
            "max_results": MAX_RESULTS,
            "exclude_domains": BLOCKED_DOMAINS,
        }
        data = self._gateway.web_completion(SEARCH_PROMPT.format(query=query), plugin)
        return hits_of(data)[:k]


def hits_of(data: Any) -> list[SearchHit]:
    """url_citation annotations of the first choice: web links only, blocked domains dropped
    (also in code: the plugin's exclude list is not trusted alone), each URL once."""
    try:
        annotations = data["choices"][0]["message"].get("annotations") or []
    except (KeyError, IndexError, TypeError, AttributeError):
        return []
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for a in annotations:
        cite = a.get("url_citation") if isinstance(a, dict) else None
        url = cite.get("url") if isinstance(cite, dict) else None
        if not isinstance(url, str) or not is_web_url(url) or is_blocked(url) or url in seen:
            continue
        seen.add(url)
        hits.append(SearchHit(url=url, title=str(cite.get("title") or "")))
    return hits
