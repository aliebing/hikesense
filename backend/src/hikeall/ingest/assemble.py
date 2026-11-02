"""Connect the unordered, arbitrarily oriented ways of an OSM relation into one line."""

from __future__ import annotations

import heapq
from typing import NamedTuple

from hikeall.errors import GapError
from hikeall.geo import Point, distance_point_to_path_km, haversine_km, locate, path_length_km


class Assembly(NamedTuple):
    line: list[Point]
    dropped_count: int  # leftover segments thrown away (see assemble_with_report)
    dropped_m: float  # their total length


def assemble(segments: list[list[Point]], max_gap_m: float = 200) -> list[Point]:
    """The assembled line only; see `assemble_with_report`."""
    return assemble_with_report(segments, max_gap_m).line


def assemble_with_report(segments: list[list[Point]], max_gap_m: float = 200) -> Assembly:
    """Greedy chaining: start at the segment end farthest from all other ends, then
    repeatedly append the remaining segment whose start or end is nearest the chain end.

    Raises GapError if the nearest candidate is farther than `max_gap_m`. The one exception
    is small debris: if the remaining segments together are at most `max_gap_m` long and lie
    entirely within `max_gap_m` of the chain (a tiny spur or a closed outline such as a
    shelter tagged as a route member), they are dropped and counted in the result so the
    caller can report them. Longer leftovers (a return leg, a second carriageway) always raise.
    Nothing is ever bridged across a gap.

    If that fails, one retry assembles the segments as a graph: they are split where another
    way's endpoint touches their interior (a T-junction without a shared end vertex), and the
    shortest path between the two free ends that lie farthest apart is walked. Dead-end spurs
    and the longer side of parallel variants are dropped and counted. The Pfälzer Waldpfad
    relation needs this; a path that does not exist (a real gap) still raises the first error."""
    try:
        return _assemble_greedy(segments, max_gap_m)
    except GapError as first:
        res = _assemble_graph(_split_at_junctions(segments))
        if res is None:
            raise first from None
        return res


def _assemble_graph(segs: list[list[Point]]) -> Assembly | None:
    """Shortest path between the two farthest-apart free ends of one connected graph; else None."""
    adj: dict[Point, list[tuple[int, Point]]] = {}
    for i, sg in enumerate(segs):
        adj.setdefault(sg[0], []).append((i, sg[-1]))
        adj.setdefault(sg[-1], []).append((i, sg[0]))
    free = [p for p, edges in adj.items() if len(edges) == 1]
    if len(free) < 2:
        return None
    seen, todo = {free[0]}, [free[0]]
    while todo:
        for _, other in adj[todo.pop()]:
            if other not in seen:
                seen.add(other)
                todo.append(other)
    if len(seen) != len(adj):  # disconnected pieces are a real gap, never dropped
        return None
    src, dst = max(
        ((p, q) for i, p in enumerate(free) for q in free[i + 1 :]),
        key=lambda pq: haversine_km(*pq),
    )
    lengths = [path_length_km([sg]) for sg in segs]
    dist = {src: 0.0}
    prev: dict[Point, tuple[Point, int]] = {}
    heap = [(0.0, src)]
    while heap:
        d, node = heapq.heappop(heap)
        if node == dst:
            break
        if d > dist.get(node, float("inf")):
            continue
        for i, other in adj[node]:
            nd = d + lengths[i]
            if nd < dist.get(other, float("inf")):
                dist[other] = nd
                prev[other] = (node, i)
                heapq.heappush(heap, (nd, other))
    if dst not in prev:
        return None
    used: list[int] = []
    node = dst
    while node != src:
        node, i = prev[node]
        used.append(i)
    used.reverse()
    line: list[Point] = []
    node = src
    for i in used:
        sg = segs[i] if segs[i][0] == node else segs[i][::-1]
        line.extend(sg if not line else sg[1:])
        node = line[-1]
    left = [sg for i, sg in enumerate(segs) if i not in set(used)]
    return Assembly(line, len(left), round(path_length_km(left) * 1000, 1) if left else 0.0)


def _split_at_junctions(segments: list[list[Point]]) -> list[list[Point]]:
    """Cut each segment at interior vertices that coincide with an endpoint of another one."""
    segs = [s for s in segments if s]
    ends = {p for s in segs for p in (s[0], s[-1])}
    out: list[list[Point]] = []
    for s in segs:
        cuts = [i for i in range(1, len(s) - 1) if s[i] in ends]
        prev = 0
        for i in cuts:
            out.append(s[prev : i + 1])
            prev = i
        out.append(s[prev:])
    return out


def _assemble_greedy(segments: list[list[Point]], max_gap_m: float) -> Assembly:
    segs = [list(s) for s in segments if s]
    if not segs:
        raise ValueError("no segments to assemble")
    if len(segs) == 1:
        return Assembly(segs[0], 0, 0.0)

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
            left_m = path_length_km(segs) * 1000
            if left_m <= max_gap_m and _all_near(segs, chain, max_gap_m):
                return Assembly(chain, len(segs), round(left_m, 1))
            raise GapError(dist * 1000, tail)
        nxt = segs.pop(k)
        if rev:
            nxt = nxt[::-1]
        chain.extend(nxt[1:] if dist == 0 else nxt)
    return Assembly(chain, 0, 0.0)


def _all_near(segs: list[list[Point]], chain: list[Point], max_gap_m: float) -> bool:
    return all(distance_point_to_path_km(p, [chain]) * 1000 <= max_gap_m for s in segs for p in s)


CLOSED_M = 1.0  # a line whose ends are this close is a closed loop that can be rotated


def orient_by_members(line: list[Point], segments: list[list[Point]]) -> list[Point]:
    """Orient an assembled line in OSM member order (the first member way is walked first).

    `assemble` picks its start by geometry only, so a route can come out backwards. A closed
    loop is also rotated to start at the end of the first member that does not touch the
    second one (the trailhead, by OSM convention). With fewer than two members the line is
    returned unchanged: a single way's drawing direction says nothing about walking order."""
    out = list(line)
    if len(segments) < 2 or len(out) < 3:
        return out
    first, second = segments[0], segments[1]
    if haversine_km(out[0], out[-1]) * 1000 <= CLOSED_M:
        ends2 = (second[0], second[-1])
        start = max((first[0], first[-1]), key=lambda e: min(haversine_km(e, o) for o in ends2))
        k, _ = locate(out, start)
        out = out[k:] + out[1 : k + 1]
    if _position(out, first) > _position(out, second):
        out.reverse()
    return out


def _position(line: list[Point], seg: list[Point]) -> float:
    """Mean index of the line vertices nearest to (up to ten of) the segment's vertices."""
    n = min(len(seg), 10)
    pts = [seg[round(i * (len(seg) - 1) / (n - 1))] for i in range(n)] if n > 1 else seg
    return sum(locate(line, p)[0] for p in pts) / len(pts)
