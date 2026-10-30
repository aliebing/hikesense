"""Official running events, searched live (spec note 2026-10-29, point 7): one web search, at
most 3 pages read, the model fills the fields of one race per page, and the code keeps a field
only if its verbatim quote is on the page and the value is in the quote (dates: the same day;
links: the URL is in the page's HTML). Everything else is shown as „nicht angegeben“. Races
without a verified date or with a past date are not shown. Nothing is stored."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel
from pydantic import Field as PField

from hikeall.adapters.page_fetch import PageSkipped, PageText, Resolver, fetch_page, resolve_host
from hikeall.adapters.web_search import WebSearch, is_blocked, is_web_url
from hikeall.agent.prompts import EXTRACT_SYSTEM
from hikeall.config import data_root
from hikeall.llm.gateway import LLMGateway
from hikeall.llm.usage import BudgetExceeded, LLMError

log = logging.getLogger(__name__)

MAX_PAGES = 3
SEARCH_K = 5
MAX_PAGE_CHARS = 30_000  # page text sent to the model (cost bound); quotes are checked on all
MAX_ANCHORS = 80
MAX_QUOTE_CHARS = 300
CALENDARS_YAML = "events/calendars.yaml"
DATE_FIELDS = ("date", "registration_deadline")
_NULLS = {"null", "none", "n/a", "nicht angegeben", "unbekannt", "-", "–"}
_MONTHS = {
    "januar": 1, "jan": 1, "jänner": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3,
    "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8,
    "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10, "okt": 10, "november": 11,
    "nov": 11, "dezember": 12, "dez": 12,
}  # fmt: skip
_MONTH_NAMES = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                "September", "Oktober", "November", "Dezember")  # fmt: skip
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4}|\d{2})\b")
_NAMED = re.compile(r"\b(\d{1,2})\.?\s*([A-Za-zÄÖÜäöü]{3,})\.?\s+(\d{4})\b")


class Field(BaseModel):
    """One race field: the value and the verbatim page quote it rests on (None: not given)."""

    value: str | None = None
    quote: str | None = None


class RaceInfo(BaseModel):
    name: Field = PField(default_factory=Field)
    date: Field = PField(default_factory=Field)
    place: Field = PField(default_factory=Field)
    distances: Field = PField(default_factory=Field)
    registration_url: Field = PField(default_factory=Field)
    registration_deadline: Field = PField(default_factory=Field)
    fee: Field = PField(default_factory=Field)


FIELDS = tuple(RaceInfo.model_fields)


class VerifiedRace(RaceInfo):
    """A race after verify(): every field with a value is on the page `source_url`."""

    source_url: str
    day: date


class CalendarLink(BaseModel):
    name: str
    url: str


class Skipped(BaseModel):
    url: str
    reason: str


class EventsResult(BaseModel):
    events: list[VerifiedRace]
    fallback: list[CalendarLink]  # only when no race is shown
    searched_at: date
    skipped: list[Skipped] = []
    pages: list[str] = []  # pages read
    calls: int = 0  # search + page fetches + extractions (count against max_tool_calls)
    search_failed: bool = False


def load_calendars(path: Path | None = None) -> list[CalendarLink]:
    path = path or data_root() / CALENDARS_YAML
    return [CalendarLink(**row) for row in yaml.safe_load(path.read_text(encoding="utf-8"))]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _day(y: int, m: int, d: int) -> date | None:
    try:
        return date(y + 2000 if y < 100 else y, m, d)
    except ValueError:
        return None


def dates_in(text: str) -> set[date]:
    """Every full date (with year) written in the text: 18.04.2027, 18.4.27, 18. April 2027,
    2027-04-18."""
    found = [_day(int(y), int(m), int(d)) for y, m, d in _ISO.findall(text)]
    found += [_day(int(y), int(m), int(d)) for d, m, y in _NUMERIC.findall(text)]
    for d, month, y in _NAMED.findall(text):
        m = _MONTHS.get(month.casefold())
        if m:
            found.append(_day(int(y), m, int(d)))
    return {x for x in found if x is not None}


def parse_day(value: str) -> date | None:
    days = dates_in(value)
    return next(iter(days)) if len(days) == 1 else None


def _bare(url: str) -> str:
    return url.split("#")[0].rstrip("/").casefold()


def _given(text: str | None) -> bool:
    """The model sometimes writes "null" as text for a missing value."""
    return bool(text and text.strip() and text.strip().casefold() not in _NULLS)


def _contains(text: str, part: str) -> bool:
    """`part` occurs in `text` as whole tokens: "5 €" is not in "25 €", "10 km" not in "110 km",
    "25" not in "25,50" or "25.50". Both are already normalised."""
    return re.search(rf"(?<![\w,.]){re.escape(part)}(?![\w,]|\.\d)", text) is not None


def _checked(name: str, f: Field, page: PageText, page_text: str) -> Field:
    if not _given(f.value) or not _given(f.quote) or len(f.quote) > MAX_QUOTE_CHARS:
        return Field()
    quote = _norm(f.quote)
    if not _contains(page_text, quote):
        return Field()
    if name in DATE_FIELDS:
        day = parse_day(f.value)
        if day is not None and day in dates_in(f.quote):
            return Field(value=day.isoformat(), quote=f.quote)
        if name == "date" or not _contains(quote, _norm(f.value)):  # a deadline may be a phrase
            return Field()
        return f
    if name == "registration_url":
        url = f.value.strip()
        on_page = url in page.links  # exactly a link of the page, not text in a script
        itself = _bare(url) == _bare(page.url)  # a page linking to itself is no sign-up link
        return (
            Field(value=url, quote=f.quote)
            if is_web_url(url) and on_page and not itself
            else Field()
        )
    return f if _contains(quote, _norm(f.value)) else Field()


def verify(race: RaceInfo, page: PageText) -> RaceInfo:
    """Keep a field only if its quote (at most 300 characters) is on the page and the value is
    in the quote, both as whole tokens; a link only if it is exactly a link of the page."""
    text = _norm(page.text)
    return RaceInfo(**{n: _checked(n, getattr(race, n), page, text) for n in FIELDS})


def extract_race(gw: LLMGateway, page: PageText, query: str = "") -> RaceInfo:
    anchors = [
        f"- {text or '(ohne Text)'}: {href}"
        for text, href in page.anchors[:MAX_ANCHORS]
        if is_web_url(href)
    ]
    user = (
        f"Anfrage: {query}\nSeite: {page.url}\n\nSeitentext:\n{page.text[:MAX_PAGE_CHARS]}"
        "\n\nLinks auf der Seite:\n" + "\n".join(anchors)
    )
    return gw.structured(RaceInfo, EXTRACT_SYSTEM, user)


class EventFinder:
    """search -> at most 3 pages -> one race per page, quote-checked. The page fetch goes
    through the safe fetcher (public addresses only, robots.txt, 10 s, 1 MB, text/html); for
    real fetches `http` must be page_fetch.safe_client() (connections pinned to vetted IPs)."""

    def __init__(
        self,
        search: WebSearch,
        http: httpx.Client,
        gateway: LLMGateway,
        calendars: list[CalendarLink] | None = None,
        resolve: Resolver = resolve_host,
        ua: str | None = None,
    ) -> None:
        self._ua = ua
        self._search = search
        self._http = http
        self._gw = gateway
        self._calendars = calendars
        self._resolve = resolve

    @staticmethod
    def default_calendars() -> list[CalendarLink]:
        return load_calendars()

    def calendars(self) -> list[CalendarLink]:
        if self._calendars is None:
            self._calendars = load_calendars()
        return self._calendars

    def find_events(self, query: str, today: date, max_calls: int = 8) -> EventsResult:
        result = EventsResult(events=[], fallback=[], searched_at=today)
        # the index holds many past editions: name the years of coming dates
        wanted = f"{query} (kommende Termine {today.year}/{today.year + 1})"
        result.calls = 1
        try:
            hits = self._search.search(wanted, k=SEARCH_K)
        except BudgetExceeded:
            raise
        except (LLMError, httpx.HTTPError) as exc:
            log.warning("events search failed: %s", type(exc).__name__)
            hits, result.search_failed = [], True
        max_pages = min(MAX_PAGES, max(0, (max_calls - result.calls) // 2))
        robots: dict = {}  # per origin, for this request only
        attempted = 0
        seen: list[tuple[str, date]] = []
        for hit in hits:
            if attempted >= max_pages:
                break
            if is_blocked(hit.url):  # never fetched, whatever the search returned
                continue
            attempted += 1
            result.calls += 1
            try:
                page = fetch_page(
                    self._http, hit.url, resolve=self._resolve, ua=self._ua, robots=robots
                )
            except PageSkipped as exc:
                result.skipped.append(Skipped(url=hit.url, reason=str(exc)))
                continue
            result.pages.append(page.url)
            if not page.text:
                continue
            result.calls += 1
            try:
                race = verify(extract_race(self._gw, page, query), page)
            except BudgetExceeded:
                raise
            except LLMError as exc:
                result.skipped.append(
                    Skipped(
                        url=page.url, reason=f"Auswertung fehlgeschlagen ({type(exc).__name__})"
                    )
                )
                continue
            day = parse_day(race.date.value) if race.date.value else None
            if day is None or day < today:  # no verified date, or already over
                continue
            name = _norm(race.name.value or page.url)
            # the same race from another page, maybe under a shorter name ("Freiburg Marathon")
            if any(d == day and (name in n or n in name) for n, d in seen):
                continue
            seen.append((name, day))
            result.events.append(VerifiedRace(**race.model_dump(), source_url=page.url, day=day))
        if not result.events:
            result.fallback = self.calendars()
        return result
