"""Cut an assembled trail line into the official stages."""

from __future__ import annotations

from pathlib import Path

import yaml

from hikeall.errors import StageOffsetError, StageOrderError
from hikeall.geo import Point, locate
from hikeall.models import Source, StageSpec, TrailSpec


def load_trail_specs(path: Path) -> list[TrailSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = {s["id"]: Source(**s) for s in data["sources"]}
    return [
        TrailSpec(
            id=t["id"],
            name=t["name"],
            kind=t["kind"],
            osm_relation_ids=t["osm_relation_ids"],
            source=sources[t["source"]],
            stages=[
                StageSpec(
                    seq=s["seq"],
                    start_name=s["start"]["name"],
                    end_name=s["end"]["name"],
                    start=(s["start"]["lat"], s["start"]["lon"]),
                    end=(s["end"]["lat"], s["end"]["lon"]),
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


def cut_stages(
    line: list[Point], specs: list[StageSpec], max_offset_m: float = 500
) -> list[list[Point]]:
    """Split `line` at the vertices nearest to each stage's start and end point.

    Stages must follow the line in order: each search runs forward from the previous cut.
    """
    parts: list[list[Point]] = []
    prev_end = 0
    for spec in specs:
        i0 = _locate_forward(line, spec.start, prev_end, spec.seq, spec.start_name, max_offset_m)
        i1 = _locate_forward(line, spec.end, i0, spec.seq, spec.end_name, max_offset_m)
        if i1 == i0:
            raise StageOrderError(spec.seq, spec.end_name, "ends where the stage starts")
        parts.append(list(line[i0 : i1 + 1]))
        prev_end = i1
    return parts
