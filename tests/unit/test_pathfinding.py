"""Layer-2 unit tests for the pathfinding engine (DECISIONS.md Entry #21).

Uses the synthetic 8-node graph at ``tests/fixtures/small_graph.json`` — small,
deterministic, and constructed so each required test case (Entry #21's five)
is observable in isolation. Do NOT switch these tests to the real MetLife
graph; the whole point of Layer 2 is testing the algorithm, not the data.

The five required cases from the Phase 2 spec:

* :func:`test_basic_shortest_path`         — case 1
* :func:`test_accessible_only_path`        — case 2 (also exercises the
  ``traverses_stairs_only=False`` branch)
* :func:`test_path_with_closures_reroutes` — case 3 (also exercises the
  ``traverses_stairs_only=True`` branch)
* :func:`test_route_blocked_by_closure_under_accessibility` — case 4
* :func:`test_route_impossible_when_disconnected`           — case 5
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.graph.loader import (
    DEFAULT_GRAPH_PATH,
    Edge,
    Graph,
    Node,
    load_default_graph,
    load_graph,
)
from app.pathfinding.engine import (
    RouteBlocked,
    RouteFound,
    RouteImpossible,
    find_route,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "small_graph.json"


@pytest.fixture(scope="module")
def small_graph() -> Graph:
    return load_graph(FIXTURE_PATH)


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------


def test_loader_reads_small_fixture(small_graph: Graph) -> None:
    assert isinstance(small_graph, Graph)
    assert set(small_graph.nodes.keys()) == {
        "a", "b", "c", "d", "e", "f", "g", "island",
    }
    assert len(small_graph.edges) == 9
    a = small_graph.nodes["a"]
    assert isinstance(a, Node)
    assert a.landmark_aliases == ("A entrance",)
    assert a.x == 0.0 and a.y == 0.0
    assert isinstance(small_graph.edges[0], Edge)


def test_load_default_graph_matches_disk() -> None:
    g = load_default_graph()
    raw = json.loads(DEFAULT_GRAPH_PATH.read_text(encoding="utf-8"))
    assert len(g.nodes) == len(raw["nodes"])
    assert len(g.edges) == len(raw["edges"])


def test_loader_rejects_missing_top_level_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing top-level"):
        load_graph(bad)


def test_loader_rejects_duplicate_zone_id(tmp_path: Path) -> None:
    dup = {
        "nodes": [
            {"zone_id": "x", "sections": [], "amenities": {}, "landmark_aliases": ["X"], "x": 0, "y": 0},  # noqa: E501
            {"zone_id": "x", "sections": [], "amenities": {}, "landmark_aliases": ["X2"], "x": 1, "y": 1},  # noqa: E501
        ],
        "edges": [],
    }
    p = tmp_path / "dup.json"
    p.write_text(json.dumps(dup), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate zone_id"):
        load_graph(p)


def test_loader_rejects_non_dict_root(tmp_path: Path) -> None:
    p = tmp_path / "list.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="missing top-level"):
        load_graph(p)


# ---------------------------------------------------------------------------
# Layer-2 required cases (Entry #21)
# ---------------------------------------------------------------------------


def test_basic_shortest_path(small_graph: Graph) -> None:
    """Case 1 — no constraints, no closures. Shortest path uses the c-g
    stairs_only shortcut (a→b→c→g, total 7)."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=[],
        closed_nodes=set(),
        closed_edges=set(),
    )
    assert isinstance(result, RouteFound)
    assert result.nodes == ("a", "b", "c", "g")
    assert result.total_walk_time_minutes == 7.0
    assert result.traverses_stairs_only is True


def test_accessible_only_path(small_graph: Graph) -> None:
    """Case 2 — accessibility flag set. Must skip the stairs_only shortcuts
    (b-e, c-g) and take a→b→c→f→g via elevator (total 11)."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=["wheelchair"],
        closed_nodes=set(),
        closed_edges=set(),
    )
    assert isinstance(result, RouteFound)
    assert result.nodes == ("a", "b", "c", "f", "g")
    assert result.total_walk_time_minutes == 11.0
    assert result.traverses_stairs_only is False


def test_path_with_closures_reroutes(small_graph: Graph) -> None:
    """Case 3 — close the shortest edge c-g. Unconstrained fan reroutes via
    the b-e stairs_only shortcut: a→b→e→f→g (total 10, traverses stairs)."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=[],
        closed_nodes=set(),
        closed_edges={("c", "g")},
    )
    assert isinstance(result, RouteFound)
    assert result.nodes == ("a", "b", "e", "f", "g")
    assert result.total_walk_time_minutes == 10.0
    assert result.traverses_stairs_only is True


def test_route_blocked_by_closure_under_accessibility(small_graph: Graph) -> None:
    """Case 4 — accessibility fan; close the f-g elevator. b-e and c-g are
    stairs_only (already excluded), so f-g was the only accessible edge into
    'g'. Result: RouteBlocked, reason names the specific closed accessible
    edge (f, g) — not a generic 'no route' message."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=["wheelchair"],
        closed_nodes=set(),
        closed_edges={("f", "g")},
    )
    assert isinstance(result, RouteBlocked)
    assert "f" in result.reason and "g" in result.reason
    assert "accessible" in result.reason
    assert result.origin == "a" and result.destination == "g"


def test_route_impossible_when_disconnected(small_graph: Graph) -> None:
    """Case 5 — 'island' has no edges. No path exists even ignoring closures
    and accessibility. Must return RouteImpossible, not raise."""
    result = find_route(
        small_graph,
        origin="a",
        destination="island",
        accessibility_flags=[],
        closed_nodes=set(),
        closed_edges=set(),
    )
    assert isinstance(result, RouteImpossible)
    assert "disconnected" in result.reason or "no path" in result.reason


# ---------------------------------------------------------------------------
# Additional coverage — traverses_stairs_only flag, defensive branches
# ---------------------------------------------------------------------------


def test_traverses_stairs_only_true_on_shortcut(small_graph: Graph) -> None:
    """Direct assertion of the stairs flag when the route DOES use stairs."""
    result = find_route(
        small_graph, "a", "g", [], set(), set()
    )
    assert isinstance(result, RouteFound)
    assert result.traverses_stairs_only is True


def test_traverses_stairs_only_false_on_accessible_route(
    small_graph: Graph,
) -> None:
    """And when the route does NOT — Phase 3's Guide Agent depends on this."""
    result = find_route(
        small_graph, "a", "g", ["no_stairs"], set(), set()
    )
    assert isinstance(result, RouteFound)
    assert result.traverses_stairs_only is False


def test_origin_equals_destination_returns_zero_length_route(
    small_graph: Graph,
) -> None:
    result = find_route(small_graph, "a", "a", [], set(), set())
    assert isinstance(result, RouteFound)
    assert result.nodes == ("a",)
    assert result.total_walk_time_minutes == 0.0
    assert result.traverses_stairs_only is False


def test_unknown_zone_ids_are_route_impossible(small_graph: Graph) -> None:
    r1 = find_route(small_graph, "does_not_exist", "g", [], set(), set())
    assert isinstance(r1, RouteImpossible)
    r2 = find_route(small_graph, "a", "also_missing", [], set(), set())
    assert isinstance(r2, RouteImpossible)


def test_closed_node_on_path_is_reported(small_graph: Graph) -> None:
    """Close intermediate node 'c'. Rerouting is still possible (via b-e),
    so we expect RouteFound, not RouteBlocked."""
    result = find_route(
        small_graph, "a", "g", [], closed_nodes={"c"}, closed_edges=set()
    )
    assert isinstance(result, RouteFound)
    assert "c" not in result.nodes


def test_route_blocked_by_closures_names_the_closure(
    small_graph: Graph,
) -> None:
    """Close both edges out of 'g' (c-g and f-g). No accessibility filter.
    Nothing else leads to 'g'. Reason must name a closure, not be generic."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=[],
        closed_nodes=set(),
        closed_edges={("c", "g"), ("f", "g")},
    )
    assert isinstance(result, RouteBlocked)
    assert "closed edges" in result.reason
    assert "'c'" in result.reason or "c" in result.reason
    assert "'g'" in result.reason or "g" in result.reason


def test_route_blocked_by_closed_node(small_graph: Graph) -> None:
    """Close the destination node itself. Must be RouteBlocked and name it."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=[],
        closed_nodes={"g"},
        closed_edges=set(),
    )
    assert isinstance(result, RouteBlocked)
    assert "closed nodes" in result.reason
    assert "'g'" in result.reason


def test_route_blocked_accessibility_only_stairs_remaining(
    small_graph: Graph,
) -> None:
    """Accessibility fan, no closures — but construct a case where the only
    remaining edges are stairs_only by mutating the fixture in-memory."""
    stripped = Graph(
        nodes=dict(small_graph.nodes),
        edges=tuple(
            e for e in small_graph.edges
            if not (e.from_id == "f" and e.to_id == "g")
            and not (e.from_id == "c" and e.to_id == "f")
            and not (e.from_id == "e" and e.to_id == "f")
        ),
    )
    result = find_route(
        stripped,
        origin="a",
        destination="g",
        accessibility_flags=["wheelchair"],
        closed_nodes=set(),
        closed_edges=set(),
    )
    assert isinstance(result, RouteBlocked)
    assert "stairs_only" in result.reason
    assert "accessible" in result.reason


def test_closed_edge_direction_agnostic(small_graph: Graph) -> None:
    """Fixture stores edge as (c, g). Closing (g, c) must still work."""
    result = find_route(
        small_graph,
        origin="a",
        destination="g",
        accessibility_flags=[],
        closed_nodes=set(),
        closed_edges={("g", "c")},
    )
    assert isinstance(result, RouteFound)
    pairs = list(zip(result.nodes, result.nodes[1:], strict=False))
    assert ("c", "g") not in pairs
    assert ("g", "c") not in pairs
