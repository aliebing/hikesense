"""Surface and way-type shares of a trail, weighted by the length of its member ways.

Sets and logic follow HikeAI (ingest/routes.py), copied rather than shared."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from hikesense.adapters.overpass import OverpassClient
from hikesense.errors import HikeSenseError
from hikesense.geo import path_length_km
from hikesense.ingest.trails import ROUTE_ROLES, relations_query

PAVED = frozenset({"asphalt", "paved", "concrete", "concrete:plates", "concrete:lanes",
                   "paving_stones", "sett", "cobblestone"})
GRAVEL = frozenset({"gravel", "fine_gravel", "compacted", "pebblestone"})
UNPAVED = frozenset({"unpaved", "dirt", "earth", "ground", "grass", "mud", "sand", "rock",
                     "wood", "woodchips"})
PATH_TYPES = frozenset({"path", "footway", "bridleway", "steps"})
ROAD_TYPES = frozenset({"residential", "unclassified", "tertiary", "secondary", "primary",
                        "trunk", "service", "living_street", "road"})
UNKNOWN_WARN_SHARE = 0.5


def way_tags_query(relation_ids: list[int]) -> str:
    ids = ",".join(str(i) for i in relation_ids)
    return f"[out:json][timeout:180];\nrelation(id:{ids});\nway(r);\nout tags;"


def parse_way_tags(data: dict[str, Any]) -> dict[int, dict[str, str]]:
    return {
        int(el["id"]): {str(k): str(v) for k, v in (el.get("tags") or {}).items()}
        for el in data.get("elements", [])
        if el.get("type") == "way"
    }


def fetch_way_tags(overpass: OverpassClient, relation_ids: list[int]) -> dict[int, dict[str, str]]:
    return parse_way_tags(overpass.run(way_tags_query(relation_ids)))


def classify_surface(tags: dict[str, str]) -> str:
    surface = tags.get("surface")
    if surface in PAVED:
        return "paved"
    if surface in GRAVEL:
        return "gravel"
    if surface in UNPAVED:
        return "unpaved"
    return "unknown"


def classify_way_type(tags: dict[str, str]) -> str:
    highway = tags.get("highway")
    if highway is None:
        return "unknown"
    if highway in PATH_TYPES:
        return "path"
    if highway == "track":
        return "track"
    if highway in ROAD_TYPES:
        return "road"
    if highway == "cycleway":
        return "cycleway"
    return "other"


def compute_shares(
    way_lengths: list[tuple[int, float]], way_tags: dict[int, dict[str, str]]
) -> tuple[dict[str, float], dict[str, float]]:
    total = sum(length for _, length in way_lengths)
    if total <= 0:
        return {}, {}
    surface: dict[str, float] = defaultdict(float)
    way_type: dict[str, float] = defaultdict(float)
    for way_id, length in way_lengths:
        tags = way_tags.get(way_id, {})
        surface[classify_surface(tags)] += length
        way_type[classify_way_type(tags)] += length
    return (
        {k: round(v / total, 3) for k, v in surface.items()},
        {k: round(v / total, 3) for k, v in way_type.items()},
    )


def member_way_lengths(data: dict[str, Any], relation_id: int) -> list[tuple[int, float]]:
    """(way id, km) of the route members of one relation in an `out geom` response."""
    rel = next(
        (
            el
            for el in data.get("elements", [])
            if el.get("type") == "relation" and el.get("id") == relation_id
        ),
        None,
    )
    if rel is None:
        raise ValueError(f"relation {relation_id} not in Overpass response")
    out: list[tuple[int, float]] = []
    for m in rel.get("members") or []:
        if m.get("type") != "way" or m.get("role", "") not in ROUTE_ROLES:
            continue
        geom = [(g["lat"], g["lon"]) for g in (m.get("geometry") or []) if g]
        if len(geom) >= 2:
            out.append((int(m["ref"]), path_length_km([geom])))
    return out


def trail_shares(
    data: dict[str, Any], relation_ids: Iterable[int], way_tags: dict[int, dict[str, str]]
) -> tuple[dict[str, float] | None, dict[str, float] | None]:
    """Shares over all given relations; (None, None) if they have no measurable way."""
    lengths: list[tuple[int, float]] = []
    for rid in relation_ids:
        lengths.extend(member_way_lengths(data, rid))
    surface, way_type = compute_shares(lengths, way_tags)
    return surface or None, way_type or None


# --- import-shares -------------------------------------------------------------------------


@dataclass
class SharesReport:
    updated: dict[str, dict[str, float]] = field(default_factory=dict)  # trail id -> surface
    failed: list[tuple[str, str]] = field(default_factory=list)  # (trail id, error)

    def mostly_unknown(self) -> list[tuple[str, float]]:
        return sorted(
            (tid, s["unknown"])
            for tid, s in self.updated.items()
            if s.get("unknown", 0) > UNKNOWN_WARN_SHARE
        )


def import_shares(
    conn: psycopg.Connection,
    overpass: OverpassClient,
    targets: dict[str, list[int]],
    batch_size: int = 10,
) -> SharesReport:
    """Compute and store the shares of the given trails (trail id -> relation ids); only the
    two share columns are written. An Overpass failure fails that batch's trails, others go
    on. Does not commit."""
    report = SharesReport()
    items = sorted(targets.items())
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        ids = sorted({r for _, rids in batch for r in rids})
        try:
            data = overpass.run(relations_query(ids))
            way_tags = fetch_way_tags(overpass, ids)
        except HikeSenseError as e:
            report.failed.extend((tid, f"{type(e).__name__}: {e}") for tid, _ in batch)
            continue
        for tid, rids in batch:
            try:
                surface, way_type = trail_shares(data, rids, way_tags)
            except ValueError as e:
                report.failed.append((tid, f"ValueError: {e}"))
                continue
            if surface is None or way_type is None:
                report.failed.append((tid, "keine messbaren Wege in der Relation"))
                continue
            conn.execute(
                "update trails set surface_shares = %s, way_type_shares = %s where id = %s",
                [Jsonb(surface), Jsonb(way_type), tid],
            )
            report.updated[tid] = surface
    return report
