"""Import curated long-distance trails: OSM geometry → one line → official stages + elevation."""

from __future__ import annotations

from typing import Any, NamedTuple

import psycopg
from psycopg.types.json import Jsonb

from hikeall.adapters.overpass import OverpassClient
from hikeall.db import upsert_source
from hikeall.errors import GapError, OutsideRegionError
from hikeall.geo import Point, haversine_km, path_length_km
from hikeall.ingest.assemble import assemble
from hikeall.ingest.elevation import ElevationProvider, elevation_stats
from hikeall.ingest.stages import cut_stages
from hikeall.models import BLACK_FOREST_BBOX, LatLon, TrailSpec

# Member roles that carry the walked route. Everything else is skipped: side trips
# (alternative/excursion/approach/connection/link) and POI outlines that some stage relations
# list as ways (shelter/viewpoint/poi/guidepost).
ROUTE_ROLES = frozenset({"", "main", "forward", "backward", "first", "last"})
MAX_GAP_M = 200
ROUNDTRIP_KM = 0.3
STAGE_DEVIATION = 0.05


class ImportReport(NamedTuple):
    trail_id: str
    length_km: float
    stages: int
    stage_km: list[float]
    warnings: list[str]


def trail_query(spec: TrailSpec) -> str:
    ids = ",".join(str(i) for i in spec.osm_relation_ids)
    return f"[out:json][timeout:180];\nrelation(id:{ids});\nout geom;"


def relation_segments(data: dict[str, Any], relation_id: int | None = None) -> list[list[Point]]:
    """Way geometries of the route members (Overpass `out geom`), in member order.

    With `relation_id`, only that relation is read (a ValueError names it if it is missing)."""
    relations = [el for el in data.get("elements", []) if el.get("type") == "relation"]
    if relation_id is not None:
        relations = [el for el in relations if el.get("id") == relation_id]
        if not relations:
            raise ValueError(f"relation {relation_id} not in Overpass response")
    segments: list[list[Point]] = []
    for rel in relations:
        for member in rel.get("members") or []:
            if member.get("type") != "way" or member.get("role", "") not in ROUTE_ROLES:
                continue
            geom = [(g["lat"], g["lon"]) for g in (member.get("geometry") or []) if g]
            if len(geom) >= 2:
                segments.append(geom)
    return segments


def chain_lines(lines: list[list[Point]], max_gap_m: float = MAX_GAP_M) -> list[Point]:
    """Join already assembled lines in the given order, flipping each as needed.

    The first line is oriented towards the second; every following line starts at whichever
    of its ends is nearer the chain end. A gap above `max_gap_m` raises GapError (no bridging)."""
    if not lines:
        raise ValueError("no lines to chain")
    first = list(lines[0])
    if len(lines) > 1:
        nxt = lines[1]
        to_end = min(haversine_km(first[-1], nxt[0]), haversine_km(first[-1], nxt[-1]))
        to_start = min(haversine_km(first[0], nxt[0]), haversine_km(first[0], nxt[-1]))
        if to_start < to_end:
            first.reverse()
    chain = first
    for line in lines[1:]:
        d_fwd, d_rev = haversine_km(chain[-1], line[0]), haversine_km(chain[-1], line[-1])
        part, dist = (list(line), d_fwd) if d_fwd <= d_rev else (line[::-1], d_rev)
        if dist * 1000 > max_gap_m:
            raise GapError(dist * 1000, chain[-1])
        chain.extend(part[1:] if dist == 0 else part)
    return chain


def trail_line(spec: TrailSpec, data: dict[str, Any]) -> list[Point]:
    """Assemble each listed relation on its own, then chain them in trails.yaml order."""
    lines = []
    for rid in spec.osm_relation_ids:
        try:
            lines.append(assemble(relation_segments(data, rid), max_gap_m=MAX_GAP_M))
        except GapError as e:
            raise GapError(e.gap_m, e.at, f"{spec.id}: relation {rid}") from e
    try:
        line = chain_lines(lines)
    except GapError as e:
        raise GapError(e.gap_m, e.at, f"{spec.id}: between child relations") from e
    outside = [p for p in line if not BLACK_FOREST_BBOX.contains(LatLon(lat=p[0], lon=p[1]))]
    if outside:
        raise OutsideRegionError(
            f"{spec.id}: {len(outside)} points outside the Black Forest bbox, e.g. {outside[0]}"
        )
    return line


def _wkt(line: list[Point]) -> str:
    return "LINESTRING(" + ",".join(f"{lon} {lat}" for lat, lon in line) + ")"


def import_trail(
    conn: psycopg.Connection, spec: TrailSpec, overpass: OverpassClient, dem: ElevationProvider
) -> ImportReport:
    """Fetch, assemble, cut and store one trail with its stages. Idempotent (upserts).

    Does not commit: the caller decides, so a failing trail leaves nothing half written."""
    line = trail_line(spec, overpass.run(trail_query(spec)))
    parts = cut_stages(line, spec.stages)  # before any write: offset/order errors abort cleanly
    length_km = round(path_length_km([line]), 2)
    stats = elevation_stats(line, dem)

    upsert_source(conn, spec.geometry_source)
    upsert_source(conn, spec.source)
    conn.execute(
        """
        insert into trails (id, name, kind, roundtrip, osm_relation_id, length_km, ascent_m,
                            descent_m, profile, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s, %(roundtrip)s, %(rel)s, %(len)s, %(asc)s, %(desc)s,
                %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind, roundtrip = excluded.roundtrip,
            osm_relation_id = excluded.osm_relation_id, length_km = excluded.length_km,
            ascent_m = excluded.ascent_m, descent_m = excluded.descent_m,
            profile = excluded.profile, geom = excluded.geom, source_id = excluded.source_id
        """,
        {
            "id": spec.id,
            "name": spec.name,
            "kind": spec.kind,
            "roundtrip": haversine_km(line[0], line[-1]) < ROUNDTRIP_KM,
            # one relation id only when the trail is exactly one relation; otherwise see trails.yaml
            "rel": spec.osm_relation_ids[0] if len(spec.osm_relation_ids) == 1 else None,
            "len": length_km,
            "asc": stats.ascent_m,
            "desc": stats.descent_m,
            "profile": Jsonb(stats.profile),
            "wkt": _wkt(line),
            "src": spec.geometry_source.id,
        },
    )

    stage_km: list[float] = []
    warnings: list[str] = []
    for stage, part in zip(spec.stages, parts, strict=True):
        km = round(path_length_km([part]), 2)
        stage_km.append(km)
        if stage.official_km and abs(km - stage.official_km) / stage.official_km > STAGE_DEVIATION:
            warnings.append(
                f"Etappe {stage.seq} {stage.start_name} – {stage.end_name}: {km:.1f} km "
                f"statt offiziell {stage.official_km:.1f} km"
            )
        s = elevation_stats(part, dem)
        conn.execute(
            """
            insert into stages (id, trail_id, seq, name, start_name, end_name, length_km,
                                ascent_m, descent_m, profile, geom, source_id)
            values (%(id)s, %(trail)s, %(seq)s, %(name)s, %(start)s, %(end)s, %(len)s, %(asc)s,
                    %(desc)s, %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s)
            on conflict (id) do update set
                trail_id = excluded.trail_id, seq = excluded.seq, name = excluded.name,
                start_name = excluded.start_name, end_name = excluded.end_name,
                length_km = excluded.length_km, ascent_m = excluded.ascent_m,
                descent_m = excluded.descent_m, profile = excluded.profile, geom = excluded.geom,
                source_id = excluded.source_id
            """,
            {
                "id": f"{spec.id}-{stage.seq:02d}",
                "trail": spec.id,
                "seq": stage.seq,
                "name": f"{stage.start_name} – {stage.end_name}",
                "start": stage.start_name,
                "end": stage.end_name,
                "len": km,
                "asc": s.ascent_m,
                "desc": s.descent_m,
                "profile": Jsonb(s.profile),
                "wkt": _wkt(part),
                "src": spec.source.id,
            },
        )
    # A shortened stage list must not leave old stages behind.
    conn.execute("delete from stages where trail_id = %s and seq > %s", [spec.id, len(spec.stages)])
    return ImportReport(spec.id, length_km, len(spec.stages), stage_km, warnings)
