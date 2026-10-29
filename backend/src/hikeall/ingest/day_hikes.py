"""Day hikes: scan OSM hiking relations into a curation CSV, then import the accepted ones.

The CSV (data/curated/day_hikes.csv) is the curation record. A scan rewrites the OSM-derived
columns and the automatic decision but never touches `manual_decision`/`manual_reason`;
rows that vanished from OSM are kept with their manual decision. The manual decision, when
set, always wins over the automatic one.
"""

from __future__ import annotations

import csv
import time
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, NamedTuple

import psycopg

from hikeall.adapters.overpass import OverpassClient
from hikeall.db import delete_day_hike, upsert_source, upsert_trail
from hikeall.errors import GapError, HikeAllError, OutsideRegionError
from hikeall.geo import Point, haversine_km, path_length_km
from hikeall.ingest.elevation import ElevationProvider, elevation_source, elevation_stats
from hikeall.ingest.trails import (
    ROUNDTRIP_KM,
    check_in_region,
    relation_line,
    relation_segments,
    relations_query,
)
from hikeall.models import BBox, Source

MIN_KM, MAX_KM = 5.0, 30.0
LONG_DISTANCE_NETWORKS = frozenset({"iwn", "nwn"})
DECISIONS = ("accepted", "rejected")
GONE_REASON = "nicht mehr in OSM gefunden (letzter Scan)"


@dataclass
class Candidate:
    osm_relation_id: int
    name: str | None
    length_km: float | None
    roundtrip: bool | None
    auto_decision: str
    auto_reason: str
    manual_decision: str = ""
    manual_reason: str = ""


COLUMNS = [f.name for f in fields(Candidate)]  # CSV header, in this order


def auto_decision(
    name: str | None, length_km: float, gap_error: bool, network: str | None
) -> tuple[str, str]:
    """Automatic first decision; rules are checked in this order."""
    if not name:
        return "rejected", "kein Name"
    if gap_error:
        return "rejected", "Lücken im Verlauf"
    if length_km < MIN_KM or length_km > MAX_KM:
        return "rejected", "Länge außerhalb 5–30 km"
    if network in LONG_DISTANCE_NETWORKS:
        return "rejected", "Fernweg, kein Tagesziel"
    return "accepted", "automatisch"


def final_decision(c: Candidate) -> tuple[str, str]:
    if c.manual_decision:
        return c.manual_decision, c.manual_reason
    return c.auto_decision, c.auto_reason


def is_roundtrip(tags: dict[str, Any], line: list[Point]) -> bool:
    """OSM `roundtrip=yes`, or start and end less than 300 m apart."""
    return tags.get("roundtrip") == "yes" or haversine_km(line[0], line[-1]) < ROUNDTRIP_KM


# --- scanning ------------------------------------------------------------------------------


def tiles(bbox: BBox, step_deg: float = 0.35) -> list[BBox]:
    """Split the bbox into tiles of at most step_deg × step_deg (after HikeAI ingest.routes)."""
    result: list[BBox] = []
    lat = bbox.south
    while lat < bbox.north:
        north = min(lat + step_deg, bbox.north)
        lon = bbox.west
        while lon < bbox.east:
            east = min(lon + step_deg, bbox.east)
            result.append(BBox(south=lat, west=lon, north=north, east=east))
            lon = east
        lat = north
    return result


def tags_query(tile: BBox) -> str:
    box = f"{tile.south},{tile.west},{tile.north},{tile.east}"
    return f'[out:json][timeout:180];\nrelation["route"="hiking"]({box});\nout tags;'


def _batches(ids: list[int], size: int) -> list[list[int]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def candidate_from_relation(data: dict[str, Any], rel: dict[str, Any]) -> Candidate:
    """Length, roundtrip and automatic decision for one relation of an `out geom` response."""
    rid = int(rel["id"])
    tags = rel.get("tags") or {}
    name = tags.get("name") or None
    segments = relation_segments(data, rid)
    if not segments:
        return Candidate(rid, name, None, None, "rejected", "keine Wege in der Relation")
    try:
        line, _ = relation_line(data, rid, context=f"relation {rid}", oriented=True)
    except GapError:
        km = round(path_length_km(segments), 2)
        return Candidate(rid, name, km, None, *auto_decision(name, km, True, tags.get("network")))
    km = round(path_length_km([line]), 2)
    decision = auto_decision(name, km, False, tags.get("network"))
    if decision[0] == "accepted":
        try:
            check_in_region(line, f"relation {rid}")
        except OutsideRegionError:
            decision = ("rejected", "verlässt die Schwarzwald-Box")
    return Candidate(rid, name, km, is_roundtrip(tags, line), *decision)


class ScanResult(NamedTuple):
    candidates: list[Candidate]
    skipped_segments: int  # node-network segments (signpost to signpost), not listed


def is_network_segment(tags: dict[str, Any]) -> bool:
    """A piece of a waymarked node network between two signposts (`network:type=node_network`),
    e.g. the Schwarzwaldverein network: not a route in itself, so never a day-hike candidate."""
    return tags.get("network:type") == "node_network"


def tag_rejection(rid: int, tags: dict[str, Any]) -> Candidate | None:
    """Rejections decided from tags alone (no geometry fetched, so length stays unknown)."""
    name = tags.get("name") or None
    if name is None:
        return Candidate(rid, None, None, None, "rejected", "kein Name")
    if tags.get("network") in LONG_DISTANCE_NETWORKS:
        return Candidate(rid, name, None, None, "rejected", "Fernweg, kein Tagesziel")
    return None


def scan(
    overpass: OverpassClient,
    bbox: BBox,
    step_deg: float = 0.35,
    batch_size: int = 50,
    pause_s: float = 2.0,
) -> ScanResult:
    """All route=hiking relations touching the bbox, with automatic decisions.

    Tags come tile by tile (cheap). Node-network segments are left out; relations without a
    name or on a long-distance network are rejected from their tags. Geometry is fetched,
    once per relation in id batches, only for the rest. Any Overpass failure (after the
    adapter's retries) raises, so a scan is never half written."""
    tags: dict[int, dict[str, Any]] = {}
    for i, tile in enumerate(tiles(bbox, step_deg)):
        if i and pause_s:
            time.sleep(pause_s)
        data = overpass.run(tags_query(tile))
        for el in data["elements"]:
            if el.get("type") == "relation":
                tags[int(el["id"])] = el.get("tags") or {}
    found: list[Candidate] = []
    need_geometry: list[int] = []
    skipped = 0
    for rid in sorted(tags):
        if is_network_segment(tags[rid]):
            skipped += 1
        elif (rejected := tag_rejection(rid, tags[rid])) is not None:
            found.append(rejected)
        else:
            need_geometry.append(rid)
    for batch in _batches(need_geometry, batch_size):
        if pause_s:
            time.sleep(pause_s)
        data = overpass.run(relations_query(batch))
        for el in data["elements"]:
            if el.get("type") == "relation" and el.get("id") in batch:
                found.append(candidate_from_relation(data, el))
    return ScanResult(sorted(found, key=lambda c: c.osm_relation_id), skipped)


# --- CSV -----------------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _parse_bool(s: str) -> bool | None:
    return {"true": True, "false": False}.get(s.strip().lower())


def read_candidates(path: Path) -> list[Candidate]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        manual = (r.get("manual_decision") or "").strip()
        if manual and manual not in DECISIONS:
            raise ValueError(
                f"{path.name}: relation {r['osm_relation_id']}: manual_decision {manual!r} "
                f"must be empty, 'accepted' or 'rejected'"
            )
        out.append(
            Candidate(
                osm_relation_id=int(r["osm_relation_id"]),
                name=r["name"] or None,
                length_km=float(r["length_km"]) if r["length_km"] else None,
                roundtrip=_parse_bool(r["roundtrip"]),
                auto_decision=r["auto_decision"],
                auto_reason=r["auto_reason"],
                manual_decision=manual,
                manual_reason=r.get("manual_reason") or "",
            )
        )
    return out


def _write(path: Path, rows: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for c in sorted(rows, key=lambda c: c.osm_relation_id):
            w.writerow([_fmt(getattr(c, col)) for col in COLUMNS])
    tmp.replace(path)


def write_candidates(path: Path, scanned: list[Candidate]) -> None:
    """Merge a scan into the CSV: OSM columns and auto decision come from the scan, the
    manual columns from the existing file. Rows missing from the scan stay, marked as gone."""
    existing = {c.osm_relation_id: c for c in read_candidates(path)}
    merged: dict[int, Candidate] = {}
    for c in scanned:
        old = existing.get(c.osm_relation_id)
        if old is not None:
            c.manual_decision, c.manual_reason = old.manual_decision, old.manual_reason
        merged[c.osm_relation_id] = c
    for rid, old in existing.items():
        if rid not in merged:
            old.auto_decision, old.auto_reason = "rejected", GONE_REASON
            merged[rid] = old
    _write(path, list(merged.values()))


def set_manual(path: Path, relation_id: int, decision: str, reason: str) -> None:
    if decision not in (*DECISIONS, ""):
        raise ValueError(f"decision must be 'accepted', 'rejected' or empty, not {decision!r}")
    rows = read_candidates(path)
    for c in rows:
        if c.osm_relation_id == relation_id:
            c.manual_decision, c.manual_reason = decision, reason
            break
    else:
        raise ValueError(f"relation {relation_id} is not in {path.name}")
    _write(path, rows)


# --- import --------------------------------------------------------------------------------


def trail_id(relation_id: int) -> str:
    return f"day-{relation_id}"


class DayHikeReport(NamedTuple):
    trail_id: str
    name: str
    length_km: float
    ascent_m: int
    roundtrip: bool
    warnings: list[str]


@dataclass
class DayHikeImport:
    imported: list[DayHikeReport] = field(default_factory=list)
    failed: list[tuple[int, str]] = field(default_factory=list)  # (relation id, error)
    removed: list[str] = field(default_factory=list)  # trail ids of now rejected day hikes


def import_day_hike(
    conn: psycopg.Connection,
    cand: Candidate,
    data: dict[str, Any],
    dem: ElevationProvider,
    source: Source,
) -> DayHikeReport:
    """Store one relation as a day hike (idempotent upsert). Does not commit."""
    rid = cand.osm_relation_id
    rel = next(
        (el for el in data["elements"] if el.get("type") == "relation" and el.get("id") == rid),
        None,
    )
    if rel is None:
        raise ValueError(f"relation {rid} not in Overpass response (deleted in OSM?)")
    tags = rel.get("tags") or {}
    line, warnings = relation_line(data, rid, context=f"relation {rid}", oriented=True)
    check_in_region(line, f"relation {rid}")
    name = tags.get("name") or cand.name
    if not name:
        raise ValueError(f"relation {rid} has no name")
    length_km = round(path_length_km([line]), 2)
    stats = elevation_stats(line, dem)
    roundtrip = is_roundtrip(tags, line)
    upsert_trail(
        conn,
        id=trail_id(rid),
        name=name,
        kind="day_hike",
        roundtrip=roundtrip,
        osm_relation_id=rid,
        length_km=length_km,
        ascent_m=stats.ascent_m,
        descent_m=stats.descent_m,
        profile=stats.profile,
        line=line,
        source_id=source.id,
    )
    return DayHikeReport(trail_id(rid), name, length_km, stats.ascent_m, roundtrip, warnings)


def import_day_hikes(
    conn: psycopg.Connection,
    candidates: list[Candidate],
    overpass: OverpassClient,
    dem: ElevationProvider,
    *,
    source: Source,
    batch_size: int = 25,
) -> DayHikeImport:
    """Import every candidate whose final decision is `accepted`; remove day hikes whose final
    decision is `rejected`. Each import and each delete runs in its own savepoint, so one
    failure (e.g. a photo still referencing a rejected trail) is reported with its relation
    id and the others continue. Does not commit."""
    result = DayHikeImport()
    upsert_source(conn, source)
    upsert_source(conn, elevation_source())
    accepted = sorted(
        (c for c in candidates if final_decision(c)[0] == "accepted"),
        key=lambda c: c.osm_relation_id,
    )
    for c in sorted(candidates, key=lambda c: c.osm_relation_id):
        if final_decision(c)[0] != "rejected":
            continue
        tid = trail_id(c.osm_relation_id)
        if _isolated(conn, result, c.osm_relation_id, delete_day_hike, conn, tid):
            result.removed.append(tid)
    for batch in _batches(accepted, batch_size):
        try:
            data = overpass.run(relations_query([c.osm_relation_id for c in batch]))
        except HikeAllError as e:
            result.failed.extend((c.osm_relation_id, f"{type(e).__name__}: {e}") for c in batch)
            continue
        for c in batch:
            rep = _isolated(
                conn,
                result,
                c.osm_relation_id,
                import_day_hike,
                conn,
                c,
                data,
                dem,
                source,
            )
            if rep is not None:
                result.imported.append(rep)
    return result


def _isolated[T](
    conn: psycopg.Connection,
    result: DayHikeImport,
    relation_id: int,
    step: Callable[..., T],
    *args: Any,
) -> T | None:
    """Run one relation's DB step in a savepoint; on failure roll it back, record it, None."""
    conn.execute("savepoint day_hike")
    try:
        value = step(*args)
    except (HikeAllError, ValueError, psycopg.Error) as e:
        conn.execute("rollback to savepoint day_hike")
        result.failed.append((relation_id, f"{type(e).__name__}: {e}"))
        return None
    conn.execute("release savepoint day_hike")
    return value
