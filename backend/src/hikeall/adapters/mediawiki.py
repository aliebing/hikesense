"""Wikipedia / Wikivoyage plain-text extracts with revision id (CC BY-SA). Adapted from HikeAI."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import KnowledgeFetchError

WIKI_LICENSE = "CC BY-SA 4.0"


@dataclass(frozen=True)
class WikiPage:
    title: str
    url: str  # permalink with revision (oldid)
    text: str
    revid: int


class MediaWikiClient:
    def __init__(self, http: httpx.Client, backoff_s: float = 1.0) -> None:
        self._http = http
        self._backoff_s = backoff_s

    def page_text(self, site: str, title: str) -> WikiPage | None:
        """Full plain-text article, or None if missing/empty."""
        data = request_json(
            self._http,
            "GET",
            f"https://{site}/w/api.php",
            error_cls=KnowledgeFetchError,
            backoff_s=self._backoff_s,
            params={
                "action": "query",
                "prop": "extracts|revisions",
                "rvprop": "ids",
                "explaintext": 1,
                "titles": title,
                "format": "json",
                "formatversion": 2,
                "redirects": 1,
            },
        )
        pages = ((data.get("query") or {}).get("pages") or []) if isinstance(data, dict) else []
        if not pages or pages[0].get("missing") or not pages[0].get("extract"):
            return None
        page = pages[0]
        revisions = page.get("revisions") or []
        if not revisions or "revid" not in revisions[0]:
            raise KnowledgeFetchError(f"{site}: no revision id for '{title}'")
        revid = int(revisions[0]["revid"])
        name = page["title"]
        url = f"https://{site}/w/index.php?title={quote(name.replace(' ', '_'))}&oldid={revid}"
        return WikiPage(title=name, url=url, text=page["extract"], revid=revid)
