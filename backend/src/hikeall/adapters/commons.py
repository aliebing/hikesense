"""Wikimedia Commons and Wikidata client for freely licensed route photos."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import ImageFetchError

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class ImageInfo:
    title: str
    thumb_url: str
    page_url: str
    author: str
    license: str


def _plain(text: str, limit: int = 120) -> str:
    """Commons metadata contains HTML; keep plain text only."""
    return " ".join(html.unescape(_TAG.sub("", text)).split())[:limit]


class CommonsClient:
    def __init__(self, http: httpx.Client, backoff_s: float = 2.0) -> None:
        self._http = http
        self._backoff_s = backoff_s

    def _get(self, url: str, params: dict) -> dict:
        data = request_json(self._http, "GET", url, params={**params, "format": "json"},
                            error_cls=ImageFetchError, retries=2, backoff_s=self._backoff_s)
        return data if isinstance(data, dict) else {}

    def geosearch(self, lat: float, lon: float, radius_m: int = 1000, limit: int = 10) -> list[str]:
        data = self._get(COMMONS_API, {
            "action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}",
            "gsradius": radius_m, "gsnamespace": 6, "gslimit": limit, "formatversion": 2,
        })
        return [g["title"] for g in (data.get("query") or {}).get("geosearch", []) if g.get("title")]

    def wikidata_image(self, qid: str) -> str | None:
        data = self._get(WIKIDATA_API, {"action": "wbgetclaims", "entity": qid, "property": "P18"})
        try:
            value = data["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
        except (KeyError, IndexError, TypeError):
            return None
        return f"File:{value}" if isinstance(value, str) else None

    def image_infos(self, titles: list[str], width: int = 400) -> list[ImageInfo]:
        wanted = [t for t in titles if t.lower().endswith(IMAGE_EXTENSIONS)][:50]
        if not wanted:
            return []
        data = self._get(COMMONS_API, {
            "action": "query", "titles": "|".join(wanted), "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": width, "formatversion": 2,
        })
        infos: list[ImageInfo] = []
        for page in (data.get("query") or {}).get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            title = page.get("title", "")
            if page.get("missing") or not info or not title.lower().endswith(IMAGE_EXTENSIONS):
                continue
            meta = info.get("extmetadata") or {}
            page_url = info.get("descriptionurl", "")
            if not info.get("thumburl") or not page_url.startswith("https://commons.wikimedia.org/"):
                continue
            infos.append(ImageInfo(
                title=title,
                thumb_url=info["thumburl"],
                page_url=page_url,
                author=_plain((meta.get("Artist") or {}).get("value", "")) or "unknown author",
                license=_plain((meta.get("LicenseShortName") or {}).get("value", "")) or "see Commons",
            ))
        return infos
