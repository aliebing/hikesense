"""Live search for official running events: web search, safe page fetch, quote-checked fields,
the agent's events intent. No network: fake search, respx pages, FakeGateway."""

from datetime import date
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage
from test_agent_graph import (  # noqa: F401 (vocab, settings are fixtures)
    FakeTools,
    make,
    one,
    raw,
    run,
    settings,
    text_of,
    types,
    vocab,
)

from hikeall.adapters.page_fetch import PageSkipped, PageText, fetch_page
from hikeall.adapters.web_search import BLOCKED_DOMAINS, OpenRouterWebSearch, SearchHit, is_blocked
from hikeall.agent.events import (
    CalendarLink,
    EventFinder,
    EventsResult,
    Field,
    RaceInfo,
    VerifiedRace,
    load_calendars,
    verify,
)
from hikeall.agent.request import RawRequest
from hikeall.llm.gateway import FakeGateway
from hikeall.llm.usage import BudgetExceeded, metered, record_usage

FIXTURES = Path(__file__).parent / "fixtures"
HALB = (FIXTURES / "race_page_halbmarathon.html").read_text(encoding="utf-8")
PAST = (FIXTURES / "race_page_past.html").read_text(encoding="utf-8")
TODAY = date(2026, 10, 30)
HTML = {"content-type": "text/html; charset=utf-8"}


def public(host: str) -> list[str]:
    return ["93.184.216.34"]


def page(url: str = "https://lauf.example.org/", html: str = HALB) -> PageText:
    return PageText.from_html(url, html.encode("utf-8"), "utf-8")


def good_race(**over) -> RaceInfo:
    fields = {
        "name": Field(value="Dreisamtal-Halbmarathon 2027", quote="Dreisamtal-Halbmarathon 2027"),
        "date": Field(
            value="2027-04-18", quote="Der Lauf findet am Sonntag, 18.04.2027 in Kirchzarten statt."
        ),
        "place": Field(value="Kirchzarten", quote="Start und Ziel: Sportplatz Kirchzarten"),
        "distances": Field(value="Halbmarathon (21,1 km)", quote="Halbmarathon (21,1 km)"),
        "registration_url": Field(
            value="https://anmeldung.example.org/dreisamtal-2027", quote="Jetzt online anmelden"
        ),
        "registration_deadline": Field(value="2027-04-11", quote="Anmeldeschluss: 11.04.2027"),
        "fee": Field(value=None, quote=None),
    }
    return RaceInfo(**(fields | over))


class FakeSearch:
    def __init__(self, hits: list[SearchHit]):
        self.hits = hits
        self.queries: list[str] = []

    def search(self, query: str, k: int = 5) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits[:k]


def robots_404(respx_mock):
    respx_mock.get(url__regex=r"^https?://[^/]+/robots\.txt$").respond(404)


def finder(hits, races, http, **kw) -> tuple[EventFinder, FakeGateway]:
    gw = FakeGateway(structured={RaceInfo: list(races)})
    kw.setdefault("calendars", [CalendarLink(name="BLV", url="https://www.blv-online.de/x")])
    return EventFinder(FakeSearch(hits), http, gw, resolve=public, **kw), gw


# --- verify: every field needs a verbatim quote --------------------------------------------


def test_field_without_quote_is_not_given():
    race = good_race(fee=Field(value="35 €", quote=None))
    checked = verify(race, page())
    assert checked.fee.value is None  # "nicht angegeben"
    assert checked.name.value == "Dreisamtal-Halbmarathon 2027"
    assert checked.place.value == "Kirchzarten"  # whitespace in the page does not matter
    assert checked.distances.value == "Halbmarathon (21,1 km)"


def test_quote_must_occur_on_page():
    race = good_race(
        fee=Field(value="35 €", quote="Startgebühr: 35 €"),  # invented
        place=Field(
            value="Freiburg", quote="Start und Ziel: Sportplatz Kirchzarten"
        ),  # not in quote
    )
    checked = verify(race, page())
    assert checked.fee.value is None and checked.fee.quote is None
    assert checked.place.value is None
    # a quote taken from a script is not page text either
    scripted = verify(good_race(fee=Field(value="99 €", quote="Startgebühr: 99 €")), page())
    assert scripted.fee.value is None


def test_null_written_as_text_is_not_given():
    race = good_race(fee=Field(value="null", quote="null"), place=Field(value="None", quote="None"))
    checked = verify(race, page(html="<p>null None</p>"))
    assert checked.fee.value is None and checked.place.value is None


def test_dates_must_be_the_same_day():
    wrong = good_race(date=Field(value="2027-04-17", quote="Sonntag, 18.04.2027"))
    assert verify(wrong, page()).date.value is None
    german = good_race(date=Field(value="18. April 2027", quote="Sonntag, 18.04.2027"))
    assert verify(german, page()).date.value == "2027-04-18"  # normalised to ISO
    named = verify(
        good_race(date=Field(value="2026-10-04", quote="Termin: 4. Oktober 2026, Musterdorf")),
        page(html=PAST),
    )
    assert named.date.value == "2026-10-04"
    deadline = verify(good_race(), page()).registration_deadline
    assert deadline.value == "2027-04-11"


def test_link_must_be_in_the_html():
    ok = verify(good_race(), page())
    assert ok.registration_url.value == "https://anmeldung.example.org/dreisamtal-2027"
    invented = good_race(
        registration_url=Field(value="https://evil.example.com/pay", quote="Jetzt online anmelden")
    )
    assert verify(invented, page()).registration_url.value is None
    relative = good_race(
        registration_url=Field(value="https://lauf.example.org/impressum", quote="Impressum")
    )
    assert verify(relative, page()).registration_url.value == "https://lauf.example.org/impressum"
    itself = good_race(registration_url=Field(value="https://lauf.example.org/", quote="Start"))
    assert verify(itself, page()).registration_url.value is None  # the page is no sign-up link
    script = good_race(registration_url=Field(value="javascript:alert(1)", quote="Impressum"))
    assert verify(script, page()).registration_url.value is None


# --- web search ----------------------------------------------------------------------------


class WebGateway:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def web_completion(self, user: str, plugin: dict) -> dict:
        self.calls.append((user, plugin))
        record_usage(
            AIMessage(content="", response_metadata={"token_usage": self.response.get("usage", {})})
        )
        return self.response


def test_openrouter_web_search_uses_exa_plugin_and_filters_blocked_domains():
    annotations = [
        {"type": "url_citation", "url_citation": {"url": u, "title": f"T {i}"}}
        for i, u in enumerate(
            [
                "https://www.dreisamtal-lauf.example.org/",
                "https://www.laufen.de/laufkalender/x",
                "https://sub.hdsports.org/lauf",
                "ftp://files.example.org/a",
                "https://www.dreisamtal-lauf.example.org/",
                "https://anmeldung.example.org/x",
            ]
        )
    ]
    gw = WebGateway(
        {
            "choices": [{"message": {"content": "…", "annotations": annotations}}],
            "usage": {"cost": 0.0123},
        }
    )
    with metered(max_cost_usd=0.05) as usage:
        hits = OpenRouterWebSearch(gw).search("Halbmarathon bei Freiburg")
    assert [h.url for h in hits] == [
        "https://www.dreisamtal-lauf.example.org/",
        "https://anmeldung.example.org/x",
    ]
    plugin = gw.calls[0][1]
    assert plugin == {
        "id": "web",
        "engine": "exa",
        "max_results": 5,
        "exclude_domains": BLOCKED_DOMAINS,
    }
    assert usage.cost_usd == pytest.approx(0.0123)


def test_blocked_domain_check_includes_subdomains():
    assert is_blocked("https://www.laufen.de/x")
    assert is_blocked("https://sub.hdsports.org/")
    assert is_blocked("https://LADV.de/")
    assert not is_blocked("https://notlaufen.de/")
    assert not is_blocked("https://www.mein-freiburgmarathon.de/")


# --- page fetch ----------------------------------------------------------------------------


def test_blocked_domains_never_fetched(respx_mock):
    robots_404(respx_mock)
    hits = [
        SearchHit(url="https://www.laufen.de/lauf", title="a"),
        SearchHit(url="https://sub.hdsports.org/lauf", title="b"),
        SearchHit(url="https://marathon.de/x", title="c"),
    ]
    blocked = respx_mock.route(host__regex=r"(laufen|hdsports|marathon)\.(de|org)$")
    with httpx.Client() as http:
        f, gw = finder(hits, [], http)
        result = f.find_events("Halbmarathon", TODAY)
        with pytest.raises(PageSkipped):
            fetch_page(http, "https://www.laufen.de/lauf", resolve=public)
    assert not blocked.called
    assert result.events == [] and result.fallback  # nothing fetched -> calendar links
    assert gw.calls["structured"] == 0


def test_redirect_to_blocked_domain_is_not_followed(respx_mock):
    robots_404(respx_mock)
    respx_mock.get("https://lauf.example.org/").respond(
        302, headers={"location": "https://www.ladv.de/ausschreibung"}
    )
    target = respx_mock.get(host="www.ladv.de")
    with httpx.Client() as http, pytest.raises(PageSkipped):
        fetch_page(http, "https://lauf.example.org/", resolve=public)
    assert not target.called


def test_robots_disallow_skips_page(respx_mock):
    respx_mock.get("https://lauf.example.org/robots.txt").respond(
        200, text="User-agent: *\nDisallow: /privat/\n"
    )
    route = respx_mock.get("https://lauf.example.org/privat/lauf").respond(200, html=HALB)
    with httpx.Client() as http:
        with pytest.raises(PageSkipped, match="robots.txt"):
            fetch_page(http, "https://lauf.example.org/privat/lauf", resolve=public)
        hits = [SearchHit(url="https://lauf.example.org/privat/lauf", title="x")]
        f, _ = finder(hits, [], http)
        result = f.find_events("Halbmarathon", TODAY)
    assert not route.called
    assert [(s.url, "robots.txt" in s.reason) for s in result.skipped] == [
        ("https://lauf.example.org/privat/lauf", True)
    ]


def test_private_addresses_are_refused(respx_mock):
    local = respx_mock.route(host__in=["127.0.0.1", "localhost", "intern.example.org"])
    with httpx.Client() as http:
        for url, ips in [
            ("http://127.0.0.1:54321/rest/v1/", ["127.0.0.1"]),
            ("http://localhost:8000/chat", ["::1"]),
            ("https://intern.example.org/", ["10.0.0.5"]),
            ("https://intern.example.org/", ["169.254.169.254"]),
            ("https://intern.example.org/", ["93.184.216.34", "192.168.1.2"]),
        ]:
            with pytest.raises(PageSkipped, match="Adresse"):
                fetch_page(http, url, resolve=lambda host, ips=ips: ips)
        with pytest.raises(PageSkipped, match="http"):
            fetch_page(http, "file:///etc/passwd", resolve=public)
    assert not local.called


def test_redirect_into_private_network_is_refused(respx_mock):
    robots_404(respx_mock)
    respx_mock.get("https://lauf.example.org/").respond(
        302, headers={"location": "http://intern.example.org/admin"}
    )
    inner = respx_mock.get(host="intern.example.org")

    def resolve(host):
        return ["10.1.2.3"] if host == "intern.example.org" else ["93.184.216.34"]

    with httpx.Client() as http, pytest.raises(PageSkipped, match="Adresse"):
        fetch_page(http, "https://lauf.example.org/", resolve=resolve)
    assert not inner.called


def test_redirects_capped_at_three(respx_mock):
    robots_404(respx_mock)
    for i in range(5):
        respx_mock.get(f"https://lauf.example.org/{i}").respond(
            301, headers={"location": f"/{i + 1}"}
        )
    with httpx.Client() as http, pytest.raises(PageSkipped, match="Weiterleitung"):
        fetch_page(http, "https://lauf.example.org/0", resolve=public)
    respx_mock.get("https://lauf.example.org/a").respond(302, headers={"location": "/b"})
    respx_mock.get("https://lauf.example.org/b").respond(200, html=HALB)
    with httpx.Client() as http:
        got = fetch_page(http, "https://lauf.example.org/a", resolve=public)
    assert got.url == "https://lauf.example.org/b"


def test_only_html_and_at_most_one_megabyte(respx_mock):
    robots_404(respx_mock)
    respx_mock.get("https://lauf.example.org/a.pdf").respond(
        200, content=b"%PDF", headers={"content-type": "application/pdf"}
    )
    respx_mock.get("https://lauf.example.org/big").respond(
        200, content=b"<p>" + b"x" * 1_100_000, headers=HTML
    )
    with httpx.Client() as http:
        with pytest.raises(PageSkipped, match="HTML"):
            fetch_page(http, "https://lauf.example.org/a.pdf", resolve=public)
        with pytest.raises(PageSkipped, match="1 MB"):
            fetch_page(http, "https://lauf.example.org/big", resolve=public)


def test_page_text_without_scripts_and_styles(respx_mock):
    robots_404(respx_mock)
    route = respx_mock.get("https://lauf.example.org/").respond(200, html=HALB)
    with httpx.Client(headers={"User-Agent": "x"}) as http:
        got = fetch_page(http, "https://lauf.example.org/", resolve=public)
    assert "Start und Ziel: Sportplatz Kirchzarten" in got.text  # whitespace normalised
    assert "99 €" not in got.text and "font-family" not in got.text
    ua = route.calls[0].request.headers["user-agent"]
    assert ua.startswith("HikeAll") and "@" not in ua


# --- find_events ---------------------------------------------------------------------------


def test_past_events_hidden(respx_mock):
    robots_404(respx_mock)
    respx_mock.get("https://alt.example.org/").respond(200, html=PAST)
    past = RaceInfo(
        name=Field(value="Herbstlauf Musterdorf 2026", quote="Herbstlauf Musterdorf 2026"),
        date=Field(value="2026-10-04", quote="Termin: 4. Oktober 2026, Musterdorf"),
    )
    with httpx.Client() as http:
        f, _ = finder([SearchHit(url="https://alt.example.org/", title="x")], [past], http)
        result = f.find_events("Herbstlauf", TODAY)
    assert result.events == []
    assert result.fallback  # nothing to show -> calendar links


def test_race_without_verified_date_hidden(respx_mock):
    robots_404(respx_mock)
    respx_mock.get("https://lauf.example.org/").respond(200, html=HALB)
    undated = good_race(date=Field(value="2027-05-01", quote="am 1. Mai 2027"))  # not on the page
    with httpx.Client() as http:
        f, _ = finder([SearchHit(url="https://lauf.example.org/", title="x")], [undated], http)
        assert f.find_events("Halbmarathon", TODAY).events == []


def test_no_results_gives_calendar_links():
    with httpx.Client() as http:
        f, _ = finder([], [], http, calendars=None)
        result = f.find_events("Halbmarathon", TODAY)
    assert result.events == []
    urls = [c.url for c in result.fallback]
    assert urls == [c.url for c in load_calendars()]
    assert "https://www.blv-online.de/laeufe/veranstaltungstermine" in urls
    assert "https://www.laufen.de/laufkalender" in urls  # only as a link, never fetched
    assert result.searched_at == TODAY


def test_at_most_three_pages_fetched(respx_mock):
    robots_404(respx_mock)
    pages = respx_mock.get(url__regex=r"^https://l\d\.example\.org/$").respond(200, html=HALB)
    hits = [SearchHit(url=f"https://l{i}.example.org/", title=str(i)) for i in range(5)]
    with httpx.Client() as http:
        f, gw = finder(hits, [good_race()] * 5, http)
        result = f.find_events("Halbmarathon", TODAY)
    assert pages.call_count == 3
    assert gw.calls["structured"] == 3
    assert result.calls == 7  # search + 3 pages + 3 extractions (<= 8 per message)
    assert len(result.events) == 1  # the same race on three pages is shown once
    race = result.events[0]
    assert race.source_url == "https://l0.example.org/"
    assert race.day == date(2027, 4, 18)
    assert race.fee.value is None


def test_same_race_under_a_shorter_name_is_shown_once(respx_mock):
    robots_404(respx_mock)
    respx_mock.get(url__regex=r"^https://l\d\.example\.org/$").respond(200, html=HALB)
    hits = [SearchHit(url=f"https://l{i}.example.org/", title=str(i)) for i in range(2)]
    short = good_race(
        name=Field(value="Dreisamtal-Halbmarathon", quote="Dreisamtal-Halbmarathon 2027")
    )
    with httpx.Client() as http:
        f, _ = finder(hits, [good_race(), short], http)
        result = f.find_events("Halbmarathon", TODAY)
    assert [r.name.value for r in result.events] == ["Dreisamtal-Halbmarathon 2027"]


def test_tool_budget_limits_pages(respx_mock):
    robots_404(respx_mock)
    pages = respx_mock.get(url__regex=r"^https://l\d\.example\.org/$").respond(200, html=HALB)
    hits = [SearchHit(url=f"https://l{i}.example.org/", title=str(i)) for i in range(5)]
    with httpx.Client() as http:
        f, _ = finder(hits, [good_race()] * 5, http)
        result = f.find_events("Halbmarathon", TODAY, max_calls=4)
    assert pages.call_count == 1 and result.calls == 3


def test_search_failure_gives_calendar_links_but_budget_propagates():
    class Down:
        def search(self, query, k=5):
            raise httpx.ConnectError("down")

    class Costly:
        def search(self, query, k=5):
            raise BudgetExceeded("x")

    with httpx.Client() as http:
        f = EventFinder(Down(), http, FakeGateway(), resolve=public)
        result = f.find_events("Halbmarathon", TODAY)
        assert result.search_failed and result.fallback and result.events == []
        with pytest.raises(BudgetExceeded):
            EventFinder(Costly(), http, FakeGateway(), resolve=public).find_events("x", TODAY)


def test_nothing_is_stored(respx_mock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    robots_404(respx_mock)
    respx_mock.get("https://lauf.example.org/").respond(200, html=HALB)
    with httpx.Client() as http:
        f, _ = finder([SearchHit(url="https://lauf.example.org/", title="x")], [good_race()], http)
        f.find_events("Halbmarathon", TODAY)
    assert list(tmp_path.iterdir()) == []


# --- agent: intent events ------------------------------------------------------------------


def verified() -> VerifiedRace:
    checked = verify(good_race(), page())
    return VerifiedRace(
        **checked.model_dump(), source_url="https://lauf.example.org/", day=date(2027, 4, 18)
    )


class EventTools(FakeTools):
    def __init__(self, result: EventsResult):
        super().__init__()
        self.result = result
        self.queries: list[tuple[str, date, int]] = []

    def find_events(self, query, today, max_calls=8):
        self.queries.append((query, today, max_calls))
        return self.result


def test_events_intent_streams_cards_and_code_written_answer(vocab, settings):  # noqa: F811
    result = EventsResult(
        events=[verified()], fallback=[], searched_at=TODAY, calls=7,
        pages=["https://lauf.example.org/"],
    )  # fmt: skip
    tools = EventTools(result)
    deps = make(
        vocab, settings, tools=tools,
        structured={RawRequest: [raw(intent="events", question="Halbmarathon im Frühjahr bei Freiburg")]},
    )  # fmt: skip
    events = run(deps, "Halbmarathon im nächsten Frühjahr bei Freiburg")
    ev = one(events, "events")
    assert [r.name.value for r in ev.events] == ["Dreisamtal-Halbmarathon 2027"]
    assert ev.note == "Angaben ohne Gewähr – bitte beim Veranstalter prüfen. Gesucht am 30.10.2026."
    assert tools.queries[0][0] == "Halbmarathon im Frühjahr bei Freiburg"
    assert tools.queries[0][2] == settings.max_tool_calls
    text = text_of(events)
    assert "1 Lauf gefunden" in text and "nicht angegeben" in text
    assert deps.gateway.calls["answer"] == 0  # no model wording: nothing to ground
    assert types(events)[-1] == "done"


def test_events_intent_without_results_shows_calendars(vocab, settings):  # noqa: F811
    links = [CalendarLink(name="BLV Veranstaltungstermine", url="https://www.blv-online.de/x")]
    result = EventsResult(events=[], fallback=links, searched_at=TODAY, calls=1)
    deps = make(
        vocab, settings, tools=EventTools(result),
        structured={RawRequest: [raw(intent="events", question="Trailrun im Mai")]},
    )  # fmt: skip
    events = run(deps, "Trailrun im Mai")
    ev = one(events, "events")
    assert ev.events == [] and ev.fallback == links
    assert "keinen kommenden Lauf" in text_of(events)
    assert "bald" not in text_of(events)


def test_gateway_web_completion_sends_plugin_and_records_cost(monkeypatch):
    # the OpenAI client does not use httpx (respx cannot see it): its create() is replaced
    from openai.types.chat import ChatCompletion

    from hikeall.config import Settings
    from hikeall.llm.gateway import OpenRouterGateway

    body = {
        "id": "x", "object": "chat.completion", "created": 1, "model": "openai/gpt-4o-mini",
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {
                "role": "assistant", "content": "…",
                "annotations": [{"type": "url_citation", "url_citation": {
                    "url": "https://lauf.example.org/", "title": "Lauf",
                    "start_index": 0, "end_index": 1,
                }}],
            },
        }],
        "usage": {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940, "cost": 0.0207},
    }  # fmt: skip
    gw = OpenRouterGateway.from_settings(
        Settings(supabase_db_url="x", openrouter_api_key="k-test", _env_file=None)
    )
    sent: list[dict] = []

    def create(**kw):
        sent.append(kw)
        return ChatCompletion.model_validate(body)

    monkeypatch.setattr(gw._structured_model.root_client.chat.completions, "create", create)
    with metered(max_cost_usd=0.05) as usage:
        hits = OpenRouterWebSearch(gw).search("Halbmarathon")
    plugins = sent[0]["extra_body"]["plugins"]
    assert plugins[0]["engine"] == "exa" and plugins[0]["exclude_domains"] == BLOCKED_DOMAINS
    assert [h.url for h in hits] == ["https://lauf.example.org/"]
    assert usage.cost_usd == pytest.approx(0.0207) and usage.input_tokens == 900


def test_configured_user_agent_is_sent_and_used_for_robots(respx_mock):
    respx_mock.get("https://lauf.example.org/robots.txt").respond(
        200, text="User-agent: HikeAllTest\nDisallow: /\n"
    )
    route = respx_mock.get("https://lauf.example.org/").respond(200, html=HALB)
    other = respx_mock.get("https://anders.example.org/").respond(200, html=HALB)
    respx_mock.get("https://anders.example.org/robots.txt").respond(404)
    hits = [
        SearchHit(url="https://lauf.example.org/", title="a"),
        SearchHit(url="https://anders.example.org/", title="b"),
    ]
    with httpx.Client() as http:
        f, _ = finder(hits, [good_race()], http, ua="HikeAllTest/1.0 (+https://example.org)")
        result = f.find_events("Halbmarathon", TODAY)
    assert not route.called  # robots.txt disallows this agent
    assert other.calls[0].request.headers["user-agent"] == "HikeAllTest/1.0 (+https://example.org)"
    assert [r.source_url for r in result.events] == ["https://anders.example.org/"]
