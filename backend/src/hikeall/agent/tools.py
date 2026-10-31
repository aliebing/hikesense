"""Agent tools: day-hike search, trail details, lodgings, walking time, multi-day plans,
weather and running events (read-only SQL; weather from Open-Meteo; events searched live on the
web, never stored)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, Protocol

import psycopg
from pydantic import BaseModel, Field

from hikeall.adapters.open_meteo import DayWeather, OpenMeteoClient
from hikeall.agent import multiday
from hikeall.agent.constraints import Candidate, Selection, select
from hikeall.agent.events import EventFinder, EventsResult
from hikeall.agent.multiday import (
    DayPlan,
    MultidayPlan,
    Profile,
    RainVariant,
    StationOnTrail,
    Stop,
    load_trail_for_multiday,
    start_km_for,
)
from hikeall.agent.request import (
    DEFAULT_DAY_KM,
    DEFAULT_RADIUS_KM,
    DEFAULT_START_TIME,
    DayChange,
    HikeRequest,
)
from hikeall.agent.weather import REASON_DOWN, NoForecast, weather_for_days
from hikeall.geo import METRIC_SRID
from hikeall.hiking_time import din33466
from hikeall.knowledge.models import KnowledgeHit, KnowledgeIndex
from hikeall.models import HikingTime

MAX_SEARCH_KM = 50.0
SEARCH_FACTOR = 3.0
MAX_POIS = 10
MAX_LODGINGS = 10
MAX_LODGING_DIST_M = 5000
MAX_GROUPS = 10
DEFAULT_GROUP_RADIUS_KM = 25.0
STALE_DAYS = 180  # a group not checked for longer than this is shown as "veraltet"


class SourceBrief(BaseModel):
    id: str
    name: str | None
    url: str | None
    license: str | None
    status: str | None = None  # own knowledge texts: "entwurf" | "geprüft"


class DayHikeResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    selection: Selection
    searched_radius_km: float
    total_in_area: int
    source_ids: list[str] = Field(default_factory=list)
    sources: list[SourceBrief] = Field(default_factory=list)  # name, url, licence per source id


class StageBrief(BaseModel):
    seq: int | None
    name: str | None
    start_name: str | None
    end_name: str | None
    length_km: float | None
    ascent_m: int | None
    descent_m: int | None


class PoiBrief(BaseModel):
    name: str | None
    kind: str
    dist_m: int | None
    along_km: float | None


class TrailDetails(BaseModel):
    trail_id: str
    name: str | None
    kind: str | None
    length_km: float | None
    ascent_m: int | None
    descent_m: int | None
    roundtrip: bool | None
    surface_shares: dict[str, float] | None
    way_type_shares: dict[str, float] | None
    stages: list[StageBrief]
    pois: list[PoiBrief]
    photo_count: int
    sources: list[SourceBrief]
    source_ids: list[str]


class LodgingBrief(BaseModel):
    name: str | None
    kind: str | None
    dist_m: int | None
    along_km: float | None
    website: str | None
    source_id: str | None = None


KNOWLEDGE_MISSING = "Wissensindex fehlt – `make knowledge` ausführen"
__all__ = ["KnowledgeHit", "KnowledgeIndex"]


class GroupBrief(BaseModel):
    """A group of the hand-curated list: no persons, no dates (spec §3 exception)."""

    name: str
    kind: str
    place: str
    url: str
    checked_at: date
    stale: bool
    dist_km: float
    # "vorschlag": page and name fetched automatically, not yet confirmed by hand; "geprüft": by hand
    status: str = "vorschlag"


def is_stale(checked_at: date, today: date) -> bool:
    return today - checked_at > timedelta(days=STALE_DAYS)


def _f(x: Any) -> float | None:
    return None if x is None else float(x)


def search_radius_km(req: HikeRequest) -> float:
    """Search space: 3x the requested radius (default 15 km), at most 50 km."""
    maxes = [k.max for k in req.constraints if k.kind == "radius_km" and k.max is not None]
    radius = min(maxes) if maxes else DEFAULT_RADIUS_KM
    return min(radius * SEARCH_FACTOR, MAX_SEARCH_KM)


# The cover photo: the first Commons photo of the trail (lowest id) with a thumbnail, else null.
_COLS = """t.id, t.name, t.length_km, t.ascent_m, t.descent_m, t.roundtrip, t.source_id,
       c.thumb_url, c.author, c.license, c.license_url, c.page_url"""
_COVER_JOIN = """left join lateral (
        select p.thumb_url, p.author, p.license, p.license_url, p.page_url from photos p
        where p.trail_id = t.id and p.source = 'commons' and p.thumb_url is not null
        order by p.id limit 1) c on true"""


def search_day_hikes(conn: psycopg.Connection, req: HikeRequest) -> DayHikeResult:
    radius = search_radius_km(req)
    start = req.start
    if (
        start is not None
        and start.kind == "place"
        and start.lat is not None
        and start.lon is not None
    ):
        rows = conn.execute(
            f"""
            select {_COLS},
                   st_distance(t.geom::geography, p.pt::geography) / 1000.0 as dist_km
            from trails t
            {_COVER_JOIN},
                 (select st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326) as pt) p
            where t.kind = 'day_hike' and t.geom is not null
              and st_dwithin(t.geom::geography, p.pt::geography, %(m)s)
            order by dist_km, t.id
            """,
            {"lon": start.lon, "lat": start.lat, "m": radius * 1000.0},
        ).fetchall()
    elif start is not None and start.kind == "area" and start.bbox is not None:
        b = start.bbox
        rows = conn.execute(
            f"""
            select {_COLS}, 0.0 as dist_km
            from trails t
            {_COVER_JOIN}
            where t.kind = 'day_hike' and t.geom is not null
              and st_intersects(t.geom, st_makeenvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326))
            order by t.id
            """,
            {"w": b.west, "s": b.south, "e": b.east, "n": b.north},
        ).fetchall()
    else:
        rows = []
    ids = [r[0] for r in rows]
    tags: dict[str, set[str]] = {i: set() for i in ids}
    if ids:
        for trail_id, tag_id in conn.execute(
            "select trail_id, tag_id from trail_tags where trail_id = any(%s)", (ids,)
        ):
            tags[trail_id].add(tag_id)
    sources = {r[0]: r[6] for r in rows}
    cands = [
        Candidate(
            trail_id=r[0],
            name=r[1] or r[0],
            length_km=_f(r[2]),
            ascent_m=r[3],
            descent_m=r[4],
            roundtrip=r[5],
            distance_km=float(r[12]),
            tags=tags[r[0]],
            cover_thumb_url=r[7],
            cover_author=r[8],
            cover_license=r[9],
            cover_license_url=r[10],
            cover_page_url=r[11],
        )
        for r in rows
    ]
    selection = select(cands, req)
    shown = [s.candidate.trail_id for s in selection.matches + selection.fallbacks]
    source_ids = sorted({sources[i] for i in shown if sources.get(i)})
    return DayHikeResult(
        selection=selection,
        searched_radius_km=radius,
        total_in_area=len(cands),
        source_ids=source_ids,
        sources=_source_briefs(conn, source_ids),
    )


def _source_briefs(conn: psycopg.Connection, ids: list[str]) -> list[SourceBrief]:
    """Name, URL and licence of each source; an id without a row stays visible (fields null)."""
    if not ids:
        return []
    rows = {
        r[0]: SourceBrief(id=r[0], name=r[1], url=r[2], license=r[3])
        for r in conn.execute(
            "select id, name, url, license from sources where id = any(%s)", (sorted(ids),)
        )
    }
    return [
        rows.get(i) or SourceBrief(id=i, name=None, url=None, license=None) for i in sorted(ids)
    ]


def get_trail_details(conn: psycopg.Connection, trail_id: str) -> TrailDetails | None:
    t = conn.execute(
        """
        select id, name, kind, length_km, ascent_m, descent_m, roundtrip,
               surface_shares, way_type_shares, source_id
        from trails where id = %s
        """,
        (trail_id,),
    ).fetchone()
    if t is None:
        return None
    stages = [
        StageBrief(
            seq=r[0],
            name=r[1],
            start_name=r[2],
            end_name=r[3],
            length_km=_f(r[4]),
            ascent_m=r[5],
            descent_m=r[6],
        )
        for r in conn.execute(
            """
            select seq, name, start_name, end_name, length_km, ascent_m, descent_m
            from stages where trail_id = %s order by seq
            """,
            (trail_id,),
        )
    ]
    poi_rows = conn.execute(
        """
        select p.name, p.kind, tp.dist_m, tp.along_km, p.source_id
        from trail_pois tp join pois p on p.id = tp.poi_id
        where tp.trail_id = %s
        order by tp.along_km nulls last, p.id
        limit %s
        """,
        (trail_id, MAX_POIS),
    ).fetchall()
    pois = [PoiBrief(name=r[0], kind=r[1], dist_m=r[2], along_km=_f(r[3])) for r in poi_rows]
    photo_count = conn.execute(
        "select count(*) from photos where trail_id = %s", (trail_id,)
    ).fetchone()[0]
    src_ids = {t[9]} if t[9] else set()
    src_ids |= {r[4] for r in poi_rows if r[4]}
    src_ids |= {
        r[0]
        for r in conn.execute(
            "select distinct source_id from stages where trail_id = %s and source_id is not null",
            (trail_id,),
        )
    }
    sources = [
        SourceBrief(id=r[0], name=r[1], url=r[2], license=r[3])
        for r in conn.execute(
            "select id, name, url, license from sources where id = any(%s) order by id",
            (sorted(src_ids),),
        )
    ]
    return TrailDetails(
        trail_id=t[0],
        name=t[1],
        kind=t[2],
        length_km=_f(t[3]),
        ascent_m=t[4],
        descent_m=t[5],
        roundtrip=t[6],
        surface_shares=t[7],
        way_type_shares=t[8],
        stages=stages,
        pois=pois,
        photo_count=photo_count,
        sources=sources,
        source_ids=[s.id for s in sources],
    )


def find_accommodation(
    conn: psycopg.Connection,
    trail_id: str,
    near_km: float | None = None,
    max_dist_m: int = 1000,
) -> list[LodgingBrief]:
    """Lodgings within max_dist_m (1..5000) of the trail; ordered by distance to near_km."""
    if not 1 <= max_dist_m <= MAX_LODGING_DIST_M:
        raise ValueError(f"max_dist_m must be between 1 and {MAX_LODGING_DIST_M}")
    rows = conn.execute(
        """
        select l.name, l.kind, tl.dist_m, tl.along_km, l.website, l.source_id
        from trail_lodgings tl join lodgings l on l.id = tl.lodging_id
        where tl.trail_id = %(t)s and tl.dist_m <= %(d)s
        order by
          case when %(near)s::numeric is null then 0
               else abs(tl.along_km - %(near)s::numeric) end nulls last,
          tl.along_km nulls last, tl.dist_m, l.id
        limit %(n)s
        """,
        {"t": trail_id, "d": max_dist_m, "near": near_km, "n": MAX_LODGINGS},
    ).fetchall()
    return [
        LodgingBrief(
            name=r[0], kind=r[1], dist_m=r[2], along_km=_f(r[3]), website=r[4], source_id=r[5]
        )
        for r in rows
    ]


def find_groups(
    conn: psycopg.Connection,
    lat: float,
    lon: float,
    radius_km: float = DEFAULT_GROUP_RADIUS_KM,
    kind: str | None = None,
    today: date | None = None,
) -> list[GroupBrief]:
    """Groups within radius_km of the point, nearest first (at most 10)."""
    today = today or date.today()
    rows = conn.execute(
        """
        select name, kind, place, url, checked_at, d / 1000.0, status
        from (
          select *, st_distance(geom::geography,
                                st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326)::geography) as d
          from groups
        ) g
        where d <= %(r)s * 1000 and (%(kind)s::text is null or kind = %(kind)s)
        order by d, id
        limit %(n)s
        """,
        {"lat": lat, "lon": lon, "r": radius_km, "kind": kind, "n": MAX_GROUPS},
    ).fetchall()
    return [
        GroupBrief(
            name=r[0], kind=r[1], place=r[2], url=r[3], checked_at=r[4],
            stale=is_stale(r[4], today), dist_km=round(float(r[5]), 1), status=r[6],
        )
        for r in rows
    ]  # fmt: skip


def stage_places(conn: psycopg.Connection, trail_id: str) -> list[str]:
    """Start and end names of the trail's stages, in walking order, without repeats."""
    rows = conn.execute(
        "select start_name, end_name from stages where trail_id = %s order by seq", (trail_id,)
    ).fetchall()
    names = [n for row in rows for n in row if n]
    return list(dict.fromkeys(names))


def hiking_time(length_km: float, ascent_m: float, descent_m: float) -> HikingTime:
    return din33466(length_km, ascent_m, descent_m)


class StartNotOnTrail(ValueError):
    """The start is off the trail (> 2 km) or at its very end: no plan can start there."""


class TrailData(BaseModel):
    """Everything the multi-day planner needs about one long-distance trail."""

    trail_id: str
    name: str
    length_km: float
    stops: list[Stop]
    stations: list[StationOnTrail]
    profile: Profile
    source_ids: list[str]
    end_name: str | None  # end place of the last stage ("Basel")


def load_trail_data(conn: psycopg.Connection, trail_id: str) -> TrailData:
    stops, stations, profile, length_km, name, source_ids = load_trail_for_multiday(conn, trail_id)
    stage_sources = {
        r[0]
        for r in conn.execute(
            "select distinct source_id from stages where trail_id = %s and source_id is not null",
            (trail_id,),
        )
    }
    places = stage_places(conn, trail_id)
    return TrailData(
        trail_id=trail_id,
        name=name,
        length_km=length_km,
        stops=stops,
        stations=stations,
        profile=profile,
        source_ids=sorted(set(source_ids) | stage_sources),
        end_name=places[-1] if places else None,
    )


def day_end_points(
    conn: psycopg.Connection, trail_id: str, days: list[DayPlan]
) -> dict[int, tuple[float, float] | None]:
    """(lat, lon) where each day ends, in one query: the lodging, else the point on the trail
    at end_km (the trail end)."""
    if not days:
        return {}
    rows = conn.execute(
        f"""
        with d(day, lodging_id, end_km) as (
          select * from unnest(%(days)s::int[], %(lodgings)s::bigint[], %(kms)s::float8[]))
        select d.day, st_y(p.pt), st_x(p.pt)
        from d
        left join lodgings l on l.id = d.lodging_id
        left join trails t on t.id = %(trail)s and t.geom is not null
        cross join lateral (select case
            when d.lodging_id is not null then st_pointonsurface(l.geom)
            else st_transform(st_lineinterpolatepoint(  -- km in metres (geo.METRIC_SRID)
                   st_transform(t.geom, {METRIC_SRID}),
                   least(greatest(d.end_km / nullif(t.length_km, 0), 0), 1)), 4326)
          end as pt) p
        """,
        {
            "days": [d.day for d in days],
            "lodgings": [d.stop.lodging_id if d.stop else None for d in days],
            "kms": [d.end_km for d in days],
            "trail": trail_id,
        },
    ).fetchall()
    out: dict[int, tuple[float, float] | None] = {d.day: None for d in days}
    for day, lat, lon in rows:
        if lat is not None and lon is not None:
            out[day] = (float(lat), float(lon))
    return out


class AgentTools(Protocol):
    def search_day_hikes(self, req: HikeRequest) -> DayHikeResult: ...

    def get_trail_details(self, trail_id: str) -> TrailDetails | None: ...

    def find_accommodation(
        self, trail_id: str, near_km: float | None = None, max_dist_m: int = 1000
    ) -> list[LodgingBrief]: ...

    def hiking_time(self, length_km: float, ascent_m: float, descent_m: float) -> HikingTime: ...

    def find_groups(
        self,
        lat: float,
        lon: float,
        radius_km: float = DEFAULT_GROUP_RADIUS_KM,
        kind: str | None = None,
        today: date | None = None,
    ) -> list[GroupBrief]: ...

    def search_knowledge(self, query: str, k: int = 5) -> list[KnowledgeHit]: ...

    def start_km(self, trail_id: str, lat: float, lon: float) -> float | None: ...

    def stage_places(self, trail_id: str) -> list[str]: ...

    def plan_multiday(self, req: HikeRequest) -> MultidayPlan:
        """Raises StartNotOnTrail if the start is off the trail or at its very end."""
        ...

    def change_day(
        self, plan: MultidayPlan, day_change: DayChange, start_name: str | None = None
    ) -> MultidayPlan: ...

    def day_end_points(
        self, trail_id: str, days: list[DayPlan]
    ) -> dict[int, tuple[float, float] | None]: ...

    def weather_days(
        self, points: list[tuple[float, float, date]], today: date
    ) -> list[DayWeather | NoForecast]:
        """Forecast per (lat, lon, day), all fetched in one request."""
        ...

    def rain_variants(self, plan: MultidayPlan, days: list[int]) -> dict[int, RainVariant | None]: ...

    def sources(self, ids: list[str]) -> list[SourceBrief]: ...

    def find_events(self, query: str, today: date, max_calls: int = 8) -> EventsResult:
        """Official running events, searched live; calendar links when none is verified."""
        ...


class DbTools:
    """AgentTools on Postgres. conn_factory must return a FRESH connection per call; every
    tool call runs inside `with conn_factory() as conn:`, which closes it afterwards."""

    def __init__(
        self,
        conn_factory: Callable[[], psycopg.Connection],
        knowledge: KnowledgeIndex | None = None,
        knowledge_opener: Callable[[], KnowledgeIndex | None] | None = None,
        weather_client: OpenMeteoClient | None = None,
        event_finder: EventFinder | None = None,
    ) -> None:
        self._conn_factory = conn_factory
        self._event_finder = event_finder
        self._knowledge = knowledge
        self._weather_client = weather_client
        self._trails: dict[str, TrailData] = {}  # static between imports: loaded once per trail
        self._trails_lock = threading.Lock()
        # a missing index is opened again on the next question (built while the API was up)
        self._knowledge_opener = knowledge_opener

    def search_day_hikes(self, req: HikeRequest) -> DayHikeResult:
        with self._conn_factory() as conn:
            return search_day_hikes(conn, req)

    def get_trail_details(self, trail_id: str) -> TrailDetails | None:
        with self._conn_factory() as conn:
            return get_trail_details(conn, trail_id)

    def find_accommodation(
        self, trail_id: str, near_km: float | None = None, max_dist_m: int = 1000
    ) -> list[LodgingBrief]:
        with self._conn_factory() as conn:
            return find_accommodation(conn, trail_id, near_km, max_dist_m)

    def hiking_time(self, length_km: float, ascent_m: float, descent_m: float) -> HikingTime:
        return hiking_time(length_km, ascent_m, descent_m)

    def find_groups(
        self,
        lat: float,
        lon: float,
        radius_km: float = DEFAULT_GROUP_RADIUS_KM,
        kind: str | None = None,
        today: date | None = None,
    ) -> list[GroupBrief]:
        with self._conn_factory() as conn:
            return find_groups(conn, lat, lon, radius_km, kind, today)

    def start_km(self, trail_id: str, lat: float, lon: float) -> float | None:
        with self._conn_factory() as conn:
            return start_km_for(conn, trail_id, lat, lon)

    def stage_places(self, trail_id: str) -> list[str]:
        with self._conn_factory() as conn:
            return stage_places(conn, trail_id)

    def _trail(self, trail_id: str) -> TrailData:
        with self._trails_lock:
            if trail_id not in self._trails:
                with self._conn_factory() as conn:
                    self._trails[trail_id] = load_trail_data(conn, trail_id)
            return self._trails[trail_id]

    def plan_multiday(self, req: HikeRequest) -> MultidayPlan:
        if req.trail_id is None or req.days is None or req.start is None:
            raise ValueError("multi-day request without trail, days or start")
        if req.start.lat is None or req.start.lon is None:
            raise ValueError("start without coordinates")
        trail = self._trail(req.trail_id)
        start_km = self.start_km(req.trail_id, req.start.lat, req.start.lon)
        if start_km is None or start_km >= trail.length_km:
            raise StartNotOnTrail(f"{req.start.label} is off {req.trail_id} or at its end")
        return multiday.plan_multiday(
            trail.stops,
            trail.profile,
            trail.length_km,
            start_km,
            req.days,
            req.day_km or DEFAULT_DAY_KM,
            req.start_date,
            req.start_time or DEFAULT_START_TIME,
            trail_id=trail.trail_id,
            trail_name=trail.name,
            source_ids=trail.source_ids,
            start_name=req.start.label,
            end_name=trail.end_name,
        )

    def change_day(
        self, plan: MultidayPlan, day_change: DayChange, start_name: str | None = None
    ) -> MultidayPlan:
        trail = self._trail(plan.trail_id)
        return multiday.change_day(
            plan,
            day_change.day,
            day_change.change,
            trail.stops,
            trail.profile,
            trail.length_km,
            start_name=start_name,
            end_name=trail.end_name,
        )

    def day_end_points(
        self, trail_id: str, days: list[DayPlan]
    ) -> dict[int, tuple[float, float] | None]:
        with self._conn_factory() as conn:
            return day_end_points(conn, trail_id, days)

    def weather_days(
        self, points: list[tuple[float, float, date]], today: date
    ) -> list[DayWeather | NoForecast]:
        if self._weather_client is None:
            return [NoForecast(REASON_DOWN) for _ in points]
        return weather_for_days(self._weather_client, points, today)

    def rain_variants(self, plan: MultidayPlan, days: list[int]) -> dict[int, RainVariant | None]:
        trail = self._trail(plan.trail_id)
        return {
            n: multiday.rain_variant(plan.days[n - 1], trail.stations, trail.profile) for n in days
        }

    def sources(self, ids: list[str]) -> list[SourceBrief]:
        with self._conn_factory() as conn:
            return _source_briefs(conn, ids)

    def find_events(self, query: str, today: date, max_calls: int = 8) -> EventsResult:
        if self._event_finder is None:  # no web search configured: the calendars only
            return EventsResult(
                events=[], fallback=EventFinder.default_calendars(), searched_at=today,
                search_failed=True,
            )  # fmt: skip
        return self._event_finder.find_events(query, today, max_calls)

    def search_knowledge(self, query: str, k: int = 5) -> list[KnowledgeHit]:
        if self._knowledge is None and self._knowledge_opener is not None:
            self._knowledge = self._knowledge_opener()
        if self._knowledge is None:
            return [KnowledgeHit(text=KNOWLEDGE_MISSING)]
        return self._knowledge.search(query, k)


def _spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


# OpenAI/LangChain function specs for bind_tools; search_day_hikes is called by the graph itself.
TOOL_SPECS: list[dict] = [
    _spec(
        "get_trail_details",
        "Liefert Details zu einer Tour aus der Datenbank: Länge, Höhenmeter, Belag, Etappen, "
        "Sehenswürdigkeiten, Anzahl Fotos und Quellen. Fehlende Werte sind null (unbekannt).",
        {"trail_id": {"type": "string", "description": "ID der Tour"}},
        ["trail_id"],
    ),
    _spec(
        "find_accommodation",
        "Findet Unterkünfte nahe einer Tour (höchstens 10), optional sortiert nach Nähe zu einem Tourkilometer.",
        {
            "trail_id": {"type": "string", "description": "ID der Tour"},
            "near_km": {
                "type": "number",
                "description": "Ergebnisse sortiert nach Nähe zu km X der Tour (kein Filter)",
            },
            "max_dist_m": {
                "type": "integer",
                "description": "Maximaler Abstand zur Tour in Metern (1 bis 5000, Standard 1000)",
            },
        },
        ["trail_id"],
    ),
    _spec(
        "hiking_time",
        "Berechnet die Gehzeit nach DIN 33466 (ohne Pausen) aus Länge, Aufstieg und Abstieg.",
        {
            "length_km": {"type": "number"},
            "ascent_m": {"type": "number"},
            "descent_m": {"type": "number"},
        },
        ["length_km", "ascent_m", "descent_m"],
    ),
    _spec(
        "search_knowledge",
        "Sucht Hintergrundwissen zum Schwarzwald (Regeln, Natur, Wetter, Ausrüstung) im "
        "Wissensindex und liefert Textstellen mit Quelle.",
        {
            "query": {"type": "string", "description": "Suchfrage auf Deutsch"},
            "k": {"type": "integer", "description": "Anzahl Treffer (Standard 5)"},
        },
        ["query"],
    ),
]
