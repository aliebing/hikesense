"""Agent tools: day-hike search, trail details, lodgings, walking time (all read-only SQL)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import psycopg
from pydantic import BaseModel, Field

from hikeall.agent.constraints import Candidate, Selection, select
from hikeall.agent.request import DEFAULT_RADIUS_KM, HikeRequest
from hikeall.hiking_time import din33466
from hikeall.models import HikingTime

MAX_SEARCH_KM = 50.0
SEARCH_FACTOR = 3.0
MAX_POIS = 10
MAX_LODGINGS = 10
MAX_LODGING_DIST_M = 5000


class DayHikeResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    selection: Selection
    searched_radius_km: float
    total_in_area: int
    source_ids: list[str] = Field(default_factory=list)


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


class SourceBrief(BaseModel):
    id: str
    name: str | None
    url: str | None
    license: str | None


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


class KnowledgeHit(BaseModel):
    """One passage from the knowledge index."""

    text: str
    source_id: str | None = None
    title: str | None = None
    url: str | None = None
    license: str | None = None
    score: float | None = None


class KnowledgeIndex(Protocol):
    """Implemented by hikeall.knowledge.search.KnowledgeIndex (ChromaDB + BM25)."""

    def search(self, query: str, k: int = 5) -> list[KnowledgeHit]: ...


def _f(x: Any) -> float | None:
    return None if x is None else float(x)


def search_radius_km(req: HikeRequest) -> float:
    """Search space: 3x the requested radius (default 15 km), at most 50 km."""
    maxes = [k.max for k in req.constraints if k.kind == "radius_km" and k.max is not None]
    radius = min(maxes) if maxes else DEFAULT_RADIUS_KM
    return min(radius * SEARCH_FACTOR, MAX_SEARCH_KM)


_COLS = "t.id, t.name, t.length_km, t.ascent_m, t.descent_m, t.roundtrip, t.source_id"


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
            from trails t,
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
            distance_km=float(r[7]),
            tags=tags[r[0]],
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
    )


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


def hiking_time(length_km: float, ascent_m: float, descent_m: float) -> HikingTime:
    return din33466(length_km, ascent_m, descent_m)


class AgentTools(Protocol):
    def search_day_hikes(self, req: HikeRequest) -> DayHikeResult: ...

    def get_trail_details(self, trail_id: str) -> TrailDetails | None: ...

    def find_accommodation(
        self, trail_id: str, near_km: float | None = None, max_dist_m: int = 1000
    ) -> list[LodgingBrief]: ...

    def hiking_time(self, length_km: float, ascent_m: float, descent_m: float) -> HikingTime: ...

    def search_knowledge(self, query: str, k: int = 5) -> list[KnowledgeHit]: ...


class DbTools:
    """AgentTools on Postgres. conn_factory must return a FRESH connection per call; every
    tool call runs inside `with conn_factory() as conn:`, which closes it afterwards."""

    def __init__(
        self,
        conn_factory: Callable[[], psycopg.Connection],
        knowledge: KnowledgeIndex | None = None,
    ) -> None:
        self._conn_factory = conn_factory
        self._knowledge = knowledge

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

    def search_knowledge(self, query: str, k: int = 5) -> list[KnowledgeHit]:
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
