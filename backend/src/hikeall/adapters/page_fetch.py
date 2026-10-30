"""Fetch one web page for the events search, safely: the URL comes from search results, so it is
user-influenced. Only http/https on the default ports, only public addresses (checked on every
redirect hop, at most 3 hops), robots.txt respected with our own User-Agent, 10 s for the whole
fetch, at most 1 MB read, only text/html. Nothing is stored: the page lives in memory only."""

from __future__ import annotations

import ipaddress
import os
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Comment
from protego import Protego

from hikeall.adapters.http import USER_AGENT
from hikeall.adapters.web_search import host_of, is_blocked

MAX_BYTES = 1_000_000
MAX_ROBOTS_BYTES = 500_000
TIMEOUT_S = 10.0
MAX_REDIRECTS = 3
_REDIRECTS = {301, 302, 303, 307, 308}
_HIDDEN = ("script", "style", "noscript", "template", "svg", "iframe")

Resolver = Callable[[str], list[str]]


class PageSkipped(Exception):
    """The page was not read; the message is the German reason (for the report and the user)."""


def user_agent() -> str:
    """HIKEALL_USER_AGENT, else the neutral project agent (never a personal e-mail)."""
    return os.environ.get("HIKEALL_USER_AGENT") or USER_AGENT


def resolve_host(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return []
    return list(dict.fromkeys(str(info[4][0]).split("%")[0] for info in infos))


@dataclass(frozen=True)
class PageText:
    url: str  # after redirects
    text: str  # visible text, whitespace normalised
    fetched_at: datetime
    html: str = field(repr=False)
    anchors: tuple[tuple[str, str], ...] = field(default=(), repr=False)  # (text, absolute href)

    @property
    def links(self) -> frozenset[str]:
        return frozenset(href for _, href in self.anchors)

    @classmethod
    def from_html(cls, url: str, data: bytes, encoding: str | None = None) -> PageText:
        soup = BeautifulSoup(data, "html.parser", from_encoding=encoding)
        html = data.decode(soup.original_encoding or encoding or "utf-8", errors="replace")
        anchors = tuple(
            (" ".join(a.get_text(" ").split()), urljoin(url, str(a["href"]).strip()))
            for a in soup.find_all("a", href=True)
        )
        for tag in soup.find_all(_HIDDEN):
            tag.decompose()
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()
        text = " ".join(soup.get_text(" ").split())
        return cls(url=url, text=text, fetched_at=datetime.now(UTC), html=html, anchors=anchors)


def _check_target(url: str, resolve: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PageSkipped("nur http/https-Adressen werden abgerufen")
    if is_blocked(url):
        raise PageSkipped("Domain ist gesperrt (Nutzungsbedingungen)")
    host = host_of(url)
    try:
        ips = [str(ipaddress.ip_address(host))]
    except ValueError:
        ips = resolve(host)
    if not ips:
        raise PageSkipped("Adresse nicht auflösbar")
    for raw in ips:
        ip = ipaddress.ip_address(raw)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:  # private, loopback, link-local, reserved, …
            raise PageSkipped("private oder reservierte Adresse – nicht abgerufen")
    try:
        port = parts.port
    except ValueError as exc:
        raise PageSkipped("ungültiger Port") from exc
    if port not in (None, 80, 443):
        raise PageSkipped("nur Standard-Ports (80/443)")


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise PageSkipped(f"Zeitlimit {TIMEOUT_S:g} s überschritten")
    return left


@dataclass
class _Reply:
    url: str
    status: int
    content_type: str
    encoding: str | None
    body: bytes


def _get(
    http: httpx.Client,
    url: str,
    ua: str,
    resolve: Resolver,
    deadline: float,
    cap: int,
    *,
    html_only: bool,
    robots: dict[str, Protego | None] | None = None,
) -> _Reply:
    """GET with redirects followed by hand (each hop checked again, at most MAX_REDIRECTS).
    With `robots`, each hop's robots.txt is asked first (cache per origin)."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _check_target(current, resolve)
        if robots is not None and not _allowed(http, current, ua, resolve, deadline, robots):
            raise PageSkipped("robots.txt verbietet den Abruf")
        headers = {"User-Agent": ua, "Accept": "text/html" if html_only else "*/*"}
        try:
            with http.stream(
                "GET", current, headers=headers, follow_redirects=False,
                timeout=_remaining(deadline),
            ) as r:  # fmt: skip
                location = r.headers.get("location")
                if r.status_code in _REDIRECTS and location:
                    current = urljoin(current, location)
                    continue
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if html_only and r.status_code < 400 and ctype != "text/html":
                    raise PageSkipped(f"kein HTML ({ctype or 'ohne Typ'})")
                if int(r.headers.get("content-length") or 0) > cap:
                    raise PageSkipped(f"größer als {cap / 1e6:g} MB")
                body = bytearray()
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > cap:  # stop reading beyond the cap
                        raise PageSkipped(f"größer als {cap / 1e6:g} MB")
                    _remaining(deadline)
                return _Reply(current, r.status_code, ctype, r.charset_encoding, bytes(body))
        except httpx.TimeoutException as exc:
            raise PageSkipped(f"Zeitlimit {TIMEOUT_S:g} s überschritten") from exc
        except httpx.HTTPError as exc:
            raise PageSkipped(f"nicht erreichbar ({type(exc).__name__})") from exc
    raise PageSkipped(f"zu viele Weiterleitungen (mehr als {MAX_REDIRECTS})")


def _allowed(
    http: httpx.Client,
    url: str,
    ua: str,
    resolve: Resolver,
    deadline: float,
    cache: dict[str, Protego | None],
) -> bool:
    """robots.txt per RFC 9309: missing (4xx) allows everything; unreachable or 5xx disallows."""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in cache:
        try:
            reply = _get(
                http, origin + "/robots.txt", ua, resolve, deadline, MAX_ROBOTS_BYTES,
                html_only=False,
            )  # fmt: skip
        except PageSkipped:
            cache[origin] = Protego.parse("User-agent: *\nDisallow: /")
        else:
            if reply.status >= 500:
                cache[origin] = Protego.parse("User-agent: *\nDisallow: /")
            elif reply.status >= 400:
                cache[origin] = None
            else:
                cache[origin] = Protego.parse(reply.body.decode("utf-8", errors="replace"))
    rules = cache[origin]
    return rules is None or rules.can_fetch(url, ua)


def fetch_page(
    http: httpx.Client,
    url: str,
    *,
    resolve: Resolver = resolve_host,
    ua: str | None = None,
    robots: dict[str, Protego | None] | None = None,
) -> PageText:
    """The page's visible text; raises PageSkipped with the reason when it is not read."""
    deadline = time.monotonic() + TIMEOUT_S
    cache = robots if robots is not None else {}
    reply = _get(
        http, url, ua or user_agent(), resolve, deadline, MAX_BYTES, html_only=True, robots=cache
    )
    if reply.status >= 400:
        raise PageSkipped(f"HTTP {reply.status}")
    return PageText.from_html(reply.url, reply.body, reply.encoding)
