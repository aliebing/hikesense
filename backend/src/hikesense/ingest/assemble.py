"""Connect the unordered, arbitrarily oriented ways of an OSM relation into one line."""

from __future__ import annotations

import heapq
from typing import NamedTuple

from hikesense.errors import GapError
from hikesense.geo import Point, distance_point_to_path_km, haversine_km, locate, path_length_km


class Assembly(NamedTuple):
    line: list[Point]
    dropped_count: int  # leftover segments thrown away (see assemble_with_report)
    dropped_m: float  # their total length


def assemble(segments: list[list[Point]], max_gap_m: float = 200) -> list[Point]:
    """The assembled line only; see `assemble_with_report`."""
    return assemble_with_report(segments, max_gap_m).line


GRAPH_MAX_DROPPED_M = 1000.0


def assemble_with_report(
    segments: list[list[Point]], max_gap_m: float = 200, graph_fallback: bool = False
) -> Assembly:
    """Greedy chaining: start at the segment end farthest from all other ends, then
    repeatedly append the remaining segment whose start or end is nearest the chain end.

    Raises GapError if the nearest candidate is farther than `max_gap_m`. The one exception
    is small debris: if the remaining segments together are at most `max_gap_m` long and lie
    entirely within `max_gap_m` of the chain (a tiny spur or a closed outline such as a
    shelter tagged as a route member), they are dropped and counted in the result so the
    caller can report them. Longer leftovers (a return leg, a second carriageway) always raise.
    Nothing is ever bridged across a gap.

    With `graph_fallback` (opt-in per curated trail, never for day hikes), a failed greedy run
    is retried on the segments as a graph: they are split where another way's endpoint touches
    their interior (a T-junction without a shared end vertex), and the shortest path between
    the two free ends that lie farthest apart is walked. Loops and spurs that hang off the path
    at one vertex are walked out and back; the rest (the longer side of parallel variants) is
    dropped and counted. If more than GRAPH_MAX_DROPPED_M would be dropped, or no connected
    path exists, the first GapError is raised."""
    try:
        return _assemble_greedy(segments, max_gap_m)
    except GapError as first:
        res = _assemble_graph(_split_at_junctions(segments)) if graph_fallback else None
        if res is None or res.dropped_m > GRAPH_MAX_DROPPED_M:
            raise first from None
        return res


def _splice_hanging(
    line: list[Point], left: list[list[Point]], on_path: set[Point]
) -> tuple[list[Point], list[list[Point]]]:
    """Walk leftover components that touch the path at exactly one vertex and contain a cycle
    (a loop, a lollipop) out and back; plain dead-end spurs stay dropped; returns the new line and what is still left over.

    A component is walked as an Euler circuit from its attachment vertex; if exactly two
    vertices have odd degree, the shortest connection between them is walked twice."""
    parent = list(range(len(left)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[Point, int] = {}
    for i, sg in enumerate(left):
        for p in (sg[0], sg[-1]):
            if p in on_path:
                continue
            if p in owner:
                parent[find(i)] = find(owner[p])
            else:
                owner[p] = i
    comps: dict[int, list[int]] = {}
    for i in range(len(left)):
        comps.setdefault(find(i), []).append(i)

    rest: list[list[Point]] = []
    for idxs in comps.values():
        segs = [left[i] for i in idxs]
        attach = {p for sg in segs for p in (sg[0], sg[-1]) if p in on_path}
        nodes = {p for sg in segs for p in (sg[0], sg[-1])}
        has_cycle = len(segs) >= len(nodes)  # a tree (plain spur) has one segment fewer
        walk = _euler_walk(segs, next(iter(attach))) if len(attach) == 1 and has_cycle else None
        if walk is None:
            rest.extend(segs)
            continue
        k = line.index(walk[0])
        line = line[: k + 1] + walk[1:] + line[k + 1 :]
    return line, rest


def _euler_walk(segs: list[list[Point]], start: Point) -> list[Point] | None:
    """Closed walk from `start` over every segment (Hierholzer), or None if not possible."""
    edges = list(range(len(segs)))
    deg: dict[Point, int] = {}
    for sg in segs:
        for p in (sg[0], sg[-1]):
            deg[p] = deg.get(p, 0) + 1
    odd = [p for p, n in deg.items() if n % 2]
    if len(odd) not in (0, 2):
        return None
    if odd:
        # Dijkstra over the component's own segments between the two odd vertices.
        a, b = odd
        dist = {a: 0.0}
        prev: dict[Point, tuple[Point, int]] = {}
        heap = [(0.0, a)]
        while heap:
            d, node = heapq.heappop(heap)
            if node == b:
                break
            if d > dist.get(node, float("inf")):
                continue
            for i, sg in enumerate(segs):
                if node in (sg[0], sg[-1]):
                    other = sg[-1] if node == sg[0] else sg[0]
                    nd = d + path_length_km([sg])
                    if nd < dist.get(other, float("inf")):
                        dist[other] = nd
                        prev[other] = (node, i)
                        heapq.heappush(heap, (nd, other))
        if b not in prev:
            return None
        node = b
        while node != a:
            node, i = prev[node]
            edges.append(i)  # walked a second time
    adj: dict[Point, list[int]] = {}
    for n, i in enumerate(edges):
        adj.setdefault(segs[i][0], []).append(n)
        adj.setdefault(segs[i][-1], []).append(n)
    used = [False] * len(edges)
    circuit: list[list[Point]] = []
    # Iterative Hierholzer; each stack item carries the points of the edge walked to reach it.
    path_stack: list[tuple[Point, list[Point] | None]] = [(start, None)]
    while path_stack:
        node, via = path_stack[-1]
        while adj.get(node) and used[adj[node][-1]]:
            adj[node].pop()
        if adj.get(node):
            n = adj[node].pop()
            used[n] = True
            sg = segs[edges[n]]
            pts = sg if sg[0] == node else sg[::-1]
            path_stack.append((pts[-1], pts))
        else:
            path_stack.pop()
            if via is not None:
                circuit.append(via)
    out: list[Point] = [start]
    for pts in reversed(circuit):
        out.extend(pts[1:])
    return out if len(out) > 1 and out[-1] == start else None


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
    used_set = set(used)
    left = [sg for i, sg in enumerate(segs) if i not in used_set]
    line, left = _splice_hanging(line, left, set(line))
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
