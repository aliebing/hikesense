"""Fetch one web page for the events search, safely: the URL comes from search results, so it is
user-influenced. Only http/https on the default ports, only public addresses (checked on every
redirect hop, at most 3 hops), robots.txt respected with our own User-Agent, 10 s for the whole
fetch (DNS included), at most 1 MB read (after decompression), only text/html. Nothing is stored:
the page lives in memory only.

The address check runs twice: `_check_target` before each request (clear reasons, test seam),
and `PinnedBackend.connect_tcp` when the socket is opened – it resolves again, applies the same
check and connects to the vetted address itself, so a DNS answer that changes in between (DNS
rebinding) cannot lead into the local network. Use `safe_client()` for real fetches."""

from __future__ import annotations

import ipaddress
import os
import socket
import time
import zlib
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpcore
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
# NAT64 prefixes and IPv4-compatible addresses carry an IPv4 address in their last 32 bits
_EMBEDDED_V4 = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("::/96"),
)
_DNS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hikeall-dns")


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
    anchors: tuple[tuple[str, str], ...] = field(default=(), repr=False)  # (text, absolute href)

    @property
    def links(self) -> frozenset[str]:
        return frozenset(href for _, href in self.anchors)

    @classmethod
    def from_html(cls, url: str, data: bytes, encoding: str | None = None) -> PageText:
        soup = BeautifulSoup(data, "html.parser", from_encoding=encoding)
        for tag in soup.find_all(_HIDDEN):
            tag.decompose()
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()
        anchors = tuple(  # visible links only (not in scripts, templates, comments)
            (" ".join(a.get_text(" ").split()), urljoin(url, str(a["href"]).strip()))
            for a in soup.find_all("a", href=True)
        )
        text = " ".join(soup.get_text(" ").split())
        return cls(url=url, text=text, fetched_at=datetime.now(UTC), anchors=anchors)


def _timeout_reason() -> str:
    return f"Zeitlimit {TIMEOUT_S:g} s überschritten"


def _is_public(raw: str) -> bool:
    ip = ipaddress.ip_address(raw)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif any(ip in net for net in _EMBEDDED_V4):
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    # private, loopback, link-local, reserved, shared, unspecified, multicast
    return ip.is_global and not ip.is_multicast


def vetted_ips(host: str, resolve: Resolver, timeout_s: float) -> list[str]:
    """The host's addresses (resolved in a worker, within `timeout_s`); PageSkipped unless
    every address is public."""
    try:
        ips = [str(ipaddress.ip_address(host.strip("[]")))]
    except ValueError:
        if timeout_s <= 0:
            raise PageSkipped(_timeout_reason()) from None
        try:
            ips = _DNS.submit(resolve, host).result(timeout=timeout_s)
        except FutureTimeout as exc:
            raise PageSkipped(_timeout_reason()) from exc
    if not ips:
        raise PageSkipped("Adresse nicht auflösbar")
    if not all(_is_public(ip) for ip in ips):
        raise PageSkipped("private oder reservierte Adresse – nicht abgerufen")
    return ips


class PinnedBackend(httpcore.NetworkBackend):
    """httpcore backend that resolves the host itself, refuses non-public addresses and
    connects to the vetted address; TLS still uses the request's host name (SNI, certificate)."""

    def __init__(
        self, resolve: Resolver = resolve_host, inner: httpcore.NetworkBackend | None = None
    ) -> None:
        self._resolve = resolve
        self._inner = inner or httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        ips = vetted_ips(host, self._resolve, TIMEOUT_S if timeout is None else timeout)
        last: Exception | None = None
        for ip in ips:
            try:
                return self._inner.connect_tcp(ip, port, timeout, local_address, socket_options)
            except httpcore.ConnectError as exc:
                last = exc
        raise last or httpcore.ConnectError("keine Adresse erreichbar")

    def connect_unix_socket(self, *args, **kwargs) -> httpcore.NetworkStream:
        raise PageSkipped("Unix-Sockets werden nicht abgerufen")

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def safe_client(timeout_s: float = TIMEOUT_S, resolve: Resolver = resolve_host) -> httpx.Client:
    """The client for real page fetches: no proxies from the environment (they would resolve
    for us), no automatic redirects, every connection pinned to a vetted address."""
    transport = httpx.HTTPTransport(trust_env=False)
    # httpx exposes no network_backend option; its pool creates connections with this one
    transport._pool._network_backend = PinnedBackend(resolve)
    return httpx.Client(
        transport=transport, timeout=timeout_s, follow_redirects=False, trust_env=False
    )


def _check_target(url: str, resolve: Resolver, deadline: float | None = None) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PageSkipped("nur http/https-Adressen werden abgerufen")
    if is_blocked(url):
        raise PageSkipped("Domain ist gesperrt (Nutzungsbedingungen)")
    left = TIMEOUT_S if deadline is None else deadline - time.monotonic()
    vetted_ips(host_of(url), resolve, left)
    try:
        port = parts.port
    except ValueError as exc:
        raise PageSkipped("ungültiger Port") from exc
    if port not in (None, 80, 443):
        raise PageSkipped("nur Standard-Ports (80/443)")


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise PageSkipped(_timeout_reason())
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
        _check_target(current, resolve, deadline)
        if robots is not None and not _allowed(http, current, ua, resolve, deadline, robots):
            raise PageSkipped("robots.txt verbietet den Abruf")
        headers = {
            "User-Agent": ua,
            "Accept": "text/html" if html_only else "*/*",
            "Accept-Encoding": "identity",  # a compressed body is still decoded bounded
        }
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
                body = _read_capped(r, cap, deadline)
                return _Reply(current, r.status_code, ctype, r.charset_encoding, body)
        except httpx.TimeoutException as exc:
            raise PageSkipped(_timeout_reason()) from exc
        except httpx.HTTPError as exc:
            raise PageSkipped(f"nicht erreichbar ({type(exc).__name__})") from exc
    raise PageSkipped(f"zu viele Weiterleitungen (mehr als {MAX_REDIRECTS})")


def _read_capped(r: httpx.Response, cap: int, deadline: float) -> bytes:
    """The body, decompressed by hand so the cap applies to the decoded bytes and no single
    chunk can inflate beyond it (decompression bomb); reading stops beyond the cap."""
    encoding = r.headers.get("content-encoding", "identity").strip().lower()
    if encoding in ("", "identity"):
        inflate = None
    elif encoding in ("gzip", "x-gzip"):
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        inflate = zlib.decompressobj()
    else:
        raise PageSkipped(f"Kodierung {encoding} nicht unterstützt")
    too_big = PageSkipped(f"größer als {cap / 1e6:g} MB")
    body = bytearray()
    try:
        for chunk in r.iter_raw():
            _remaining(deadline)
            if inflate is None:
                body += chunk
            else:
                data = chunk
                while data and len(body) <= cap:
                    body += inflate.decompress(data, cap + 1 - len(body))
                    data = inflate.unconsumed_tail
            if len(body) > cap:  # stop reading beyond the cap
                raise too_big
    except zlib.error as exc:
        raise PageSkipped("Inhalt nicht lesbar (Kompression)") from exc
    return bytes(body)


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
