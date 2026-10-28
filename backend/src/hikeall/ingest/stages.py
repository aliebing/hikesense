"""Cut an assembled trail line into the official stages."""

from __future__ import annotations

from pathlib import Path

import yaml

from hikeall.errors import StageOffsetError
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


def cut_stages(
    line: list[Point], specs: list[StageSpec], max_offset_m: float = 500
) -> list[list[Point]]:
    """Split `line` at the vertices nearest to each stage's start and end point."""
    parts: list[list[Point]] = []
    for spec in specs:
        i0, d0 = locate(line, spec.start)
        if d0 > max_offset_m:
            raise StageOffsetError(spec.seq, spec.start_name, d0)
        i1, d1 = locate(line, spec.end)
        if d1 > max_offset_m:
            raise StageOffsetError(spec.seq, spec.end_name, d1)
        parts.append(list(line[min(i0, i1) : max(i0, i1) + 1]))
    return parts
