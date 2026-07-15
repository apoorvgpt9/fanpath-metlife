"""Dijkstra-based pathfinding with a discriminated-union output (Entry #9, #17).

Pure function surface — no Firestore reads, no network. Closures are passed in
by the caller (the endpoint layer fetches ``venue_state`` per request per
Entry #16 and hands the resolved sets to :func:`find_route`).

Output is one of three frozen dataclasses:

* :class:`RouteFound`     — an actual path.
* :class:`RouteBlocked`   — the path is impossible under the current closures
                            or accessibility filter; the reason names the
                            specific closure or missing accessible edge.
* :class:`RouteImpossible` — no path exists even ignoring closures/filters
                            (disconnected graph or unknown zone_id).

"The model never invents a route" (Entry #9): this module is the only source
of node lists / walk times; agents downstream only read the output.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from app.graph.loader import Graph
from app.models.enums import EdgeAccessibility

_INF = float("inf")


@dataclass(frozen=True)
class RouteFound:
    origin: str
    destination: str
    nodes: tuple[str, ...]
    total_walk_time_minutes: float
    traverses_stairs_only: bool


@dataclass(frozen=True)
class RouteBlocked:
    origin: str
    destination: str
    reason: str


@dataclass(frozen=True)
class RouteImpossible:
    origin: str
    destination: str
    reason: str


RouteResult = RouteFound | RouteBlocked | RouteImpossible


def _normalize_closed_edges(closed_edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Store each closed edge as both directions so lookup is direction-agnostic."""
    out: set[tuple[str, str]] = set()
    for u, v in closed_edges:
        out.add((u, v))
        out.add((v, u))
    return out


def _build_filtered_adjacency(
    graph: Graph,
    accessibility_flags: list[str],
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> dict[str, list[tuple[str, float, bool]]]:
    """Return ``node_id -> [(neighbor, weight, is_stairs_only), ...]``.

    Applies (in order): node closures, edge closures, accessibility filter
    (remove ``stairs_only`` edges when any accessibility flag is set).
    """
    accessible_needed = bool(accessibility_flags)
    edges_closed = _normalize_closed_edges(closed_edges)
    adj: dict[str, list[tuple[str, float, bool]]] = {n: [] for n in graph.nodes}
    for e in graph.edges:
        if e.from_id in closed_nodes or e.to_id in closed_nodes:
            continue
        if (e.from_id, e.to_id) in edges_closed:
            continue
        is_stairs = e.accessibility == EdgeAccessibility.STAIRS_ONLY.value
        if accessible_needed and is_stairs:
            continue
        adj[e.from_id].append((e.to_id, e.walk_time_minutes, is_stairs))
        adj[e.to_id].append((e.from_id, e.walk_time_minutes, is_stairs))
    return adj


def _dijkstra(
    adj: dict[str, list[tuple[str, float, bool]]],
    origin: str,
    destination: str,
) -> tuple[list[str], float, bool] | None:
    """Run Dijkstra and return (path, total_time, traverses_stairs) or None."""
    dist: dict[str, float] = {origin: 0.0}
    prev: dict[str, tuple[str, bool]] = {}
    heap: list[tuple[float, str]] = [(0.0, origin)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == destination:
            break
        if d > dist.get(u, _INF):
            continue
        for v, w, is_stairs in adj.get(u, ()):
            nd = d + w
            if nd < dist.get(v, _INF):
                dist[v] = nd
                prev[v] = (u, is_stairs)
                heapq.heappush(heap, (nd, v))
    if destination not in dist:
        return None
    path: list[str] = [destination]
    traverses_stairs = False
    cur = destination
    while cur in prev:
        parent, is_stairs = prev[cur]
        traverses_stairs = traverses_stairs or is_stairs
        path.append(parent)
        cur = parent
    path.reverse()
    return path, dist[destination], traverses_stairs


def _accessible_closed_edges(
    graph: Graph, closed_edges: set[tuple[str, str]]
) -> list[tuple[str, str]]:
    normalized = _normalize_closed_edges(closed_edges)
    out: list[tuple[str, str]] = []
    for e in graph.edges:
        if e.accessibility == EdgeAccessibility.STAIRS_ONLY.value:
            continue
        if (e.from_id, e.to_id) in normalized:
            out.append((e.from_id, e.to_id))
    return out


def _closure_reason(
    closed_nodes: set[str], closed_edges: set[tuple[str, str]]
) -> str:
    bits: list[str] = []
    if closed_nodes:
        bits.append(f"closed nodes {sorted(closed_nodes)}")
    if closed_edges:
        bits.append(f"closed edges {sorted(closed_edges)}")
    return " and ".join(bits) if bits else "unknown closure state"


def _classify_blocked(
    graph: Graph,
    origin: str,
    destination: str,
    accessibility_flags: list[str],
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> RouteResult:
    """Attribute the block: disconnected, closures, or accessibility filter."""
    unfiltered = _build_filtered_adjacency(graph, [], set(), set())
    if _dijkstra(unfiltered, origin, destination) is None:
        return RouteImpossible(
            origin=origin,
            destination=destination,
            reason=(
                f"no path exists between '{origin}' and '{destination}' "
                "in the graph (disconnected components)"
            ),
        )
    closures_only = _build_filtered_adjacency(graph, [], closed_nodes, closed_edges)
    if _dijkstra(closures_only, origin, destination) is None:
        return RouteBlocked(
            origin=origin,
            destination=destination,
            reason=(
                f"route from '{origin}' to '{destination}' blocked by "
                f"{_closure_reason(closed_nodes, closed_edges)}"
            ),
        )
    accessible_closed = _accessible_closed_edges(graph, closed_edges)
    if accessible_closed:
        return RouteBlocked(
            origin=origin,
            destination=destination,
            reason=(
                f"no accessible route from '{origin}' to '{destination}' for flags "
                f"{sorted(accessibility_flags)}; needed accessible edge(s) are closed: "
                f"{sorted(accessible_closed)}"
            ),
        )
    return RouteBlocked(
        origin=origin,
        destination=destination,
        reason=(
            f"no accessible route from '{origin}' to '{destination}' for flags "
            f"{sorted(accessibility_flags)} — every remaining path requires "
            "stairs_only edges"
        ),
    )


def find_route(
    graph: Graph,
    origin: str,
    destination: str,
    accessibility_flags: list[str],
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> RouteResult:
    """Resolve a route request into one of three discriminated union variants."""
    if origin not in graph.nodes or destination not in graph.nodes:
        return RouteImpossible(
            origin=origin,
            destination=destination,
            reason=(
                f"unknown zone_id(s): origin={origin!r}, destination={destination!r}"
            ),
        )
    if origin == destination:
        return RouteFound(
            origin=origin,
            destination=destination,
            nodes=(origin,),
            total_walk_time_minutes=0.0,
            traverses_stairs_only=False,
        )
    adj = _build_filtered_adjacency(
        graph, accessibility_flags, closed_nodes, closed_edges
    )
    result = _dijkstra(adj, origin, destination)
    if result is None:
        return _classify_blocked(
            graph, origin, destination, accessibility_flags, closed_nodes, closed_edges
        )
    path, total, traverses_stairs = result
    return RouteFound(
        origin=origin,
        destination=destination,
        nodes=tuple(path),
        total_walk_time_minutes=total,
        traverses_stairs_only=traverses_stairs,
    )


def _candidate_zones_for_amenity(graph: Graph, amenity_type: str) -> list[str]:
    return [
        zone_id
        for zone_id, node in graph.nodes.items()
        if node.amenities.get(amenity_type)
    ]


def _select_best_amenity_result(
    origin: str,
    amenity_type: str,
    candidate_results: list[RouteResult],
) -> RouteResult:
    """Pick the lowest-walk-time RouteFound; else the most informative blocker."""
    found = [r for r in candidate_results if isinstance(r, RouteFound)]
    if found:
        best = min(found, key=lambda r: r.total_walk_time_minutes)
        return best
    blocked = [r for r in candidate_results if isinstance(r, RouteBlocked)]
    if blocked:
        first = blocked[0]
        return RouteBlocked(
            origin=origin,
            destination=first.destination,
            reason=(
                f"no reachable '{amenity_type}' amenity from '{origin}': "
                f"nearest candidate blocked — {first.reason}"
            ),
        )
    return RouteImpossible(
        origin=origin,
        destination="",
        reason=(
            f"no reachable '{amenity_type}' amenity from '{origin}' "
            "under current graph state"
        ),
    )


def find_nearest_amenity(
    graph: Graph,
    origin: str,
    amenity_type: str,
    accessibility_flags: list[str],
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> RouteResult:
    """Resolve an amenity-type destination to the nearest amenity-bearing zone.

    Loops over zones with ``amenities[amenity_type] == True``, calls
    :func:`find_route` to each, returns the lowest-walk-time :class:`RouteFound`.
    36-node graph — a linear scan is plenty (Entry #28). If no candidate is
    reachable, returns the most informative failure (prefers ``RouteBlocked``
    with a real reason over generic ``RouteImpossible``).
    """
    if origin not in graph.nodes:
        return RouteImpossible(
            origin=origin,
            destination="",
            reason=f"unknown origin zone_id: {origin!r}",
        )
    candidates = _candidate_zones_for_amenity(graph, amenity_type)
    if not candidates:
        return RouteImpossible(
            origin=origin,
            destination="",
            reason=(
                f"no zone in the graph offers amenity '{amenity_type}'"
            ),
        )
    results: list[RouteResult] = [
        find_route(
            graph,
            origin=origin,
            destination=candidate,
            accessibility_flags=accessibility_flags,
            closed_nodes=closed_nodes,
            closed_edges=closed_edges,
        )
        for candidate in candidates
    ]
    return _select_best_amenity_result(origin, amenity_type, results)
