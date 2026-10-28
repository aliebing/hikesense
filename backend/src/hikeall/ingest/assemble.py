"""Connect the unordered, arbitrarily oriented ways of an OSM relation into one line."""

from __future__ import annotations

from hikeall.errors import GapError
from hikeall.geo import Point, haversine_km


def assemble(segments: list[list[Point]], max_gap_m: float = 200) -> list[Point]:
    """Greedy chaining: start at the segment end farthest from all other ends, then
    repeatedly append the remaining segment whose start or end is nearest the chain end.
    Raises GapError if the nearest candidate is farther than `max_gap_m`."""
    segs = [list(s) for s in segments if s]
    if not segs:
        raise ValueError("no segments to assemble")
    if len(segs) == 1:
        return segs[0]

    # Start: the endpoint whose nearest endpoint of any other segment is farthest away.
    best_i, best_flip, best_d = 0, False, -1.0
    for i, seg in enumerate(segs):
        others = [p for j, s in enumerate(segs) if j != i for p in (s[0], s[-1])]
        for flip, end in ((False, seg[0]), (True, seg[-1])):
            d = min(haversine_km(end, o) for o in others)
            if d > best_d:
                best_i, best_flip, best_d = i, flip, d
    first = segs.pop(best_i)
    # The free end must lead the chain: reverse if it is the segment's last point.
    chain = first[::-1] if best_flip else first

    while segs:
        tail = chain[-1]
        k, rev, dist = 0, False, float("inf")
        for idx, s in enumerate(segs):
            for r, end in ((False, s[0]), (True, s[-1])):
                d = haversine_km(tail, end)
                if d < dist:
                    k, rev, dist = idx, r, d
        if dist * 1000 > max_gap_m:
            raise GapError(dist * 1000, tail)
        nxt = segs.pop(k)
        if rev:
            nxt = nxt[::-1]
        chain.extend(nxt[1:] if dist == 0 else nxt)
    return chain
