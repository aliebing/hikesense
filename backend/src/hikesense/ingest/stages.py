"""Cut an assembled trail line into the official stages."""

from __future__ import annotations

from pathlib import Path

import yaml

from hikesense.errors import StageOffsetError, StageOrderError
from hikesense.geo import Point, locate
from hikesense.models import Source, StageSpec, TrailSpec


def load_trail_sources(path: Path) -> dict[str, Source]:
    """The `sources` list of trails.yaml by id (e.g. `osm` for OSM geometry, ODbL)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {s["id"]: Source(**s) for s in data["sources"]}


def load_trail_specs(path: Path) -> list[TrailSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = load_trail_sources(path)

    def source(trail: dict, key: str) -> Source:
        try:
            return sources[trail[key]]
        except KeyError:
            raise ValueError(
                f"trail {trail.get('id')!r}: {key} {trail.get(key)!r} is not listed under sources"
            ) from None

    return [
        TrailSpec(
            id=t["id"],
            name=t["name"],
            kind=t["kind"],
            osm_relation_ids=t["osm_relation_ids"],
            source=source(t, "source"),
            geometry_source=source(t, "geometry_source"),
            assemble=t.get("assemble", "greedy"),
            trim=t.get("trim", False),
            stages=[
                StageSpec(
                    seq=s["seq"],
                    start_name=s["start"]["name"],
                    end_name=s["end"]["name"],
                    start=(s["start"]["lat"], s["start"]["lon"]),
                    end=(s["end"]["lat"], s["end"]["lon"]),
                    official_km=s.get("km"),
                )
                for s in t["stages"]
            ],
        )
        for t in data["trails"]
    ]


def _locate_forward(
    line: list[Point], p: Point, start: int, seq: int, name: str, max_offset_m: float
) -> int:
    """Nearest vertex at or after `start`; a place that only lies behind it is an order error."""
    idx, dist = locate(line, p, start)
    if dist <= max_offset_m:
        return idx
    back, back_dist = locate(line, p)
    if back_dist <= max_offset_m and back < start:
        raise StageOrderError(seq, name, "lies before the previous point of the trail")
    raise StageOffsetError(seq, name, dist)


def cut_indices(
    line: list[Point], specs: list[StageSpec], max_offset_m: float = 500
) -> list[tuple[int, int]]:
    """Vertex index pair (start, end) per stage: the vertices nearest to each stage's start
    and end point. Stages must follow the line in order: each search runs forward from the
    previous cut."""
    cuts: list[tuple[int, int]] = []
    prev_end = 0
    for spec in specs:
        i0 = _locate_forward(line, spec.start, prev_end, spec.seq, spec.start_name, max_offset_m)
        i1 = _locate_forward(line, spec.end, i0, spec.seq, spec.end_name, max_offset_m)
        if i1 == i0:
            raise StageOrderError(spec.seq, spec.end_name, "ends where the stage starts")
        cuts.append((i0, i1))
        prev_end = i1
    return cuts


def cut_stages(
    line: list[Point], specs: list[StageSpec], max_offset_m: float = 500
) -> list[list[Point]]:
    """Split `line` at the vertices nearest to each stage's start and end point."""
    return [list(line[i0 : i1 + 1]) for i0, i1 in cut_indices(line, specs, max_offset_m)]


def trim_to_stages(
    line: list[Point], specs: list[StageSpec], max_offset_m: float = 500
) -> list[Point]:
    """The part of `line` between the first stage's start and the last stage's end.

    Some OSM relations run beyond the official trail (e.g. the Pfälzer Waldpfad starts in
    Kaiserslautern, ~14 km before Schopp); the trail length is the sum of its stages."""
    if not specs:
        return list(line)
    cuts = cut_indices(line, specs, max_offset_m)
    return list(line[cuts[0][0] : cuts[-1][1] + 1])
