"""Wikimedia Commons and Wikidata client for freely licensed route photos."""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, replace

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import ImageFetchError

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
API_ERROR_RETRIES = 2
_TAG = re.compile(r"<[^>]+>")
_NO_AUTHOR = {"unknown", "unknown author", "unbekannt", "anonymous", "anonym"}


@dataclass(frozen=True)
class ImageInfo:
    title: str
    thumb_url: str
    page_url: str
    author: str  # "" when Commons names no author: callers must not store such an image
    license: str | None  # None/"" when Commons names no licence: same
    url: str = ""  # large rendition (`large_width` px), set by image_infos(large_width=...)
    width: int = 0  # original size in px (aspect-ratio filter)
    height: int = 0
    license_url: str | None = None


def _plain(text: str, limit: int = 120) -> str:
    """Commons metadata contains HTML; keep plain text only."""
    return " ".join(html.unescape(_TAG.sub("", text)).split())[:limit]


def _author(meta: dict) -> str:
    author = _plain((meta.get("Artist") or {}).get("value", ""))
    return "" if author.lower() in _NO_AUTHOR else author


class CommonsClient:
    def __init__(
        self, http: httpx.Client, backoff_s: float = 2.0, api_error_retries: int = API_ERROR_RETRIES
    ) -> None:
        self._http = http
        self._backoff_s = backoff_s
        self._api_error_retries = api_error_retries

    def _get(self, url: str, params: dict) -> dict:
        """MediaWiki reports overload ("cirrussearch-too-busy-error") as HTTP 200 with an
        `error` object: retry that with backoff too, and never treat it as "no results"."""
        for attempt in range(self._api_error_retries + 1):
            if attempt and self._backoff_s:
                time.sleep(self._backoff_s * min(attempt, 3))  # capped: overload errors are random
            data = request_json(
                self._http,
                "GET",
                url,
                params={**params, "format": "json"},
                error_cls=ImageFetchError,
                retries=2,
                backoff_s=self._backoff_s,
            )
            data = data if isinstance(data, dict) else {}
            err = data.get("error")
            if not err:
                return data
            code = err.get("code", "unknown") if isinstance(err, dict) else str(err)
        raise ImageFetchError(
            f"{url} returned API error {code} after {self._api_error_retries + 1} tries"
        )

    def geosearch(self, lat: float, lon: float, radius_m: int = 1000, limit: int = 10) -> list[str]:
        data = self._get(
            COMMONS_API,
            {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lon}",
                "gsradius": radius_m,
                "gsnamespace": 6,
                "gslimit": limit,
                "formatversion": 2,
            },
        )
        return [
            g["title"] for g in (data.get("query") or {}).get("geosearch", []) if g.get("title")
        ]

    def wikidata_image(self, qid: str) -> str | None:
        data = self._get(WIKIDATA_API, {"action": "wbgetclaims", "entity": qid, "property": "P18"})
        try:
            value = data["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
        except (KeyError, IndexError, TypeError):
            return None
        return f"File:{value}" if isinstance(value, str) else None

    def image_infos(
        self, titles: list[str], width: int = 400, large_width: int | None = None
    ) -> list[ImageInfo]:
        """Info for up to 50 titles; `thumb_url` is `width` px wide. With `large_width` a second
        request adds `url` (that width, or the original if it is smaller)."""
        infos = self._image_infos(titles, width)
        if large_width is None or not infos:
            return infos
        large = {
            i.title: i.thumb_url for i in self._image_infos([i.title for i in infos], large_width)
        }
        return [replace(i, url=large[i.title]) for i in infos if i.title in large]

    def _image_infos(self, titles: list[str], width: int) -> list[ImageInfo]:
        wanted = [t for t in titles if t.lower().endswith(IMAGE_EXTENSIONS)][:50]
        if not wanted:
            return []
        data = self._get(
            COMMONS_API,
            {
                "action": "query",
                "titles": "|".join(wanted),
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiurlwidth": width,
                "formatversion": 2,
            },
        )
        infos: list[ImageInfo] = []
        for page in (data.get("query") or {}).get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            title = page.get("title", "")
            if page.get("missing") or not info or not title.lower().endswith(IMAGE_EXTENSIONS):
                continue
            meta = info.get("extmetadata") or {}
            page_url = info.get("descriptionurl", "")
            if not info.get("thumburl") or not page_url.startswith(
                "https://commons.wikimedia.org/"
            ):
                continue
            infos.append(
                ImageInfo(
                    title=title,
                    thumb_url=info["thumburl"],
                    page_url=page_url,
                    author=_author(meta),
                    license=_plain((meta.get("LicenseShortName") or {}).get("value", "")),
                    width=int(info.get("width") or 0),
                    height=int(info.get("height") or 0),
                    license_url=(meta.get("LicenseUrl") or {}).get("value") or None,
                )
            )
        return infos
