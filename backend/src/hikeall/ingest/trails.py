"""Import curated long-distance trails: OSM geometry → one line → official stages + elevation."""

from __future__ import annotations

from typing import Any, NamedTuple

import psycopg

from hikeall.adapters.overpass import OverpassClient
from hikeall.db import delete_stages_after, upsert_source, upsert_stage, upsert_trail
from hikeall.errors import GapError, OutsideRegionError
from hikeall.geo import Point, haversine_km, path_length_km
from hikeall.ingest.assemble import assemble_with_report, orient_by_members
from hikeall.ingest.elevation import ElevationProvider, elevation_source, elevation_stats
from hikeall.ingest.stages import cut_stages, trim_to_stages
from hikeall.models import TrailSpec
from hikeall.regions import Region, region_of_line

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


def relations_query(relation_ids: list[int]) -> str:
    ids = ",".join(str(i) for i in relation_ids)
    return f"[out:json][timeout:180];\nrelation(id:{ids});\nout geom;"


def trail_query(spec: TrailSpec) -> str:
    return relations_query(spec.relation_ids)


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


def trail_line(spec: TrailSpec, data: dict[str, Any]) -> tuple[list[Point], list[str]]:
    """Assemble each listed entry on its own (a relation, or a group of relations as one
    piece), then chain them in trails.yaml order.

    Returns the line and warnings about small leftover segments that assembly dropped."""
    lines, warnings = [], []
    for rid in spec.osm_relation_ids:
        line, warns = relation_line(
            data,
            rid,
            context=f"{spec.id}: relation {_label(rid)}",
            graph_fallback=spec.assemble == "graph",
        )
        lines.append(line)
        warnings.extend(warns)
    try:
        line = chain_lines(lines)
    except GapError as e:
        raise GapError(e.gap_m, e.at, f"{spec.id}: between child relations") from e
    if len(lines) == 1 and spec.stages:
        # One piece has no chaining order to orient it: run it from the first stage start.
        start = spec.stages[0].start
        if haversine_km(line[-1], start) < haversine_km(line[0], start):
            line = line[::-1]
    check_in_region(line, spec.id)
    return line, warnings


def _label(relation_id: int | list[int]) -> str:
    return "+".join(map(str, relation_id)) if isinstance(relation_id, list) else str(relation_id)


def relation_line(
    data: dict[str, Any],
    relation_id: int | list[int],
    context: str,
    oriented: bool = False,
    graph_fallback: bool = False,
) -> tuple[list[Point], list[str]]:
    """One relation's route members assembled into a line, plus warnings about dropped
    leftovers. A list of ids is assembled as one piece from the union of their route ways.
    GapError carries `context`. With `oriented`, the line follows OSM member order
    (see `orient_by_members`); otherwise it keeps the direction `assemble` chose."""
    ids = relation_id if isinstance(relation_id, list) else [relation_id]
    segments = [s for rid in ids for s in relation_segments(data, rid)]
    try:
        res = assemble_with_report(segments, max_gap_m=MAX_GAP_M, graph_fallback=graph_fallback)
    except GapError as e:
        raise GapError(e.gap_m, e.at, context) from e
    warnings = []
    if res.dropped_count:
        warnings.append(
            f"Relation {_label(relation_id)}: {res.dropped_count} Teilstück(e), zusammen "
            f"{res.dropped_m:.0f} m, neben dem Weg verworfen"
        )
    line = orient_by_members(res.line, segments) if oriented else res.line
    return line, warnings


def check_in_region(line: list[Point], context: str) -> Region:
    """Return the region whose box contains the whole line, else raise OutsideRegionError."""
    region = region_of_line(line)
    if region is None:
        raise OutsideRegionError(
            f"{context}: Linie liegt in keiner Region vollständig (z. B. Punkt {line[0]})"
        )
    return region


def import_trail(
    conn: psycopg.Connection, spec: TrailSpec, overpass: OverpassClient, dem: ElevationProvider
) -> ImportReport:
    """Fetch, assemble, cut and store one trail with its stages. Idempotent (upserts).

    Does not commit: the caller decides, so a failing trail leaves nothing half written."""
    from hikeall.ingest.shares import fetch_way_tags, trail_shares  # shares imports this module

    data = overpass.run(trail_query(spec))
    line, warnings = trail_line(spec, data)
    surface, way_type = trail_shares(
        data, spec.relation_ids, fetch_way_tags(overpass, spec.relation_ids)
    )
    region = check_in_region(line, spec.id)
    if spec.trim:
        line = trim_to_stages(line, spec.stages)  # drop OSM line outside the official stages
    parts = cut_stages(line, spec.stages)  # before any write: offset/order errors abort cleanly
    length_km = round(path_length_km([line]), 2)
    stats = elevation_stats(line, dem)

    upsert_source(conn, spec.geometry_source)
    upsert_source(conn, spec.source)
    upsert_source(conn, elevation_source())
    upsert_trail(
        conn,
        id=spec.id,
        name=spec.name,
        kind=spec.kind,
        region=region.id,
        roundtrip=haversine_km(line[0], line[-1]) < ROUNDTRIP_KM,
        # one relation id only when the trail is exactly one relation; otherwise see trails.yaml
        osm_relation_id=spec.relation_ids[0] if len(spec.relation_ids) == 1 else None,
        length_km=length_km,
        ascent_m=stats.ascent_m,
        descent_m=stats.descent_m,
        profile=stats.profile,
        line=line,
        source_id=spec.geometry_source.id,
        surface_shares=surface,
        way_type_shares=way_type,
    )

    stage_km: list[float] = []
    for stage, part in zip(spec.stages, parts, strict=True):
        km = round(path_length_km([part]), 2)
        stage_km.append(km)
        if stage.official_km and abs(km - stage.official_km) / stage.official_km > STAGE_DEVIATION:
            warnings.append(
                f"Etappe {stage.seq} {stage.start_name} – {stage.end_name}: {km:.1f} km "
                f"statt offiziell {stage.official_km:.1f} km"
            )
        s = elevation_stats(part, dem)
        upsert_stage(
            conn,
            id=f"{spec.id}-{stage.seq:02d}",
            trail_id=spec.id,
            seq=stage.seq,
            name=f"{stage.start_name} – {stage.end_name}",
            start_name=stage.start_name,
            end_name=stage.end_name,
            length_km=km,
            ascent_m=s.ascent_m,
            descent_m=s.descent_m,
            profile=s.profile,
            line=part,
            source_id=spec.source.id,
        )
    delete_stages_after(conn, spec.id, len(spec.stages))
    return ImportReport(spec.id, length_km, len(spec.stages), stage_km, warnings)
