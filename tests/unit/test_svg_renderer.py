"""Layer-2 unit tests for the SVG renderer (DECISIONS.md Entry #12, #22).

Uses the same synthetic 8-node fixture the pathfinding tests use — small,
deterministic, and the coordinate values are whole numbers so tests can
match them exactly.

The route ``a -> b -> c -> f -> g`` is fixed across tests; individual cases
vary the closed-nodes and closed-edges sets.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

from app.graph.loader import Graph, load_graph
from app.pathfinding.engine import RouteFound
from app.rendering.svg_renderer import render_route

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "small_graph.json"

_ACCENT = "#22D3EE"
_WARN = "#F87171"
_SURFACE = "#1E293B"
_TEXT = "#F1F5F9"


@pytest.fixture(scope="module")
def small_graph() -> Graph:
    return load_graph(FIXTURE_PATH)


def _route() -> RouteFound:
    return RouteFound(
        origin="a",
        destination="g",
        nodes=("a", "b", "c", "f", "g"),
        total_walk_time_minutes=11.0,
        traverses_stairs_only=False,
    )


def _decode(data_uri: str) -> str:
    assert data_uri.startswith("data:image/svg+xml;base64,")
    payload = data_uri.split(",", 1)[1]
    return base64.b64decode(payload).decode("utf-8")


# ---------------------------------------------------------------------------
# Data URI + title
# ---------------------------------------------------------------------------


def test_returns_data_uri_prefix(small_graph: Graph) -> None:
    out = render_route(_route(), small_graph, set(), set())
    assert out.startswith("data:image/svg+xml;base64,")


def test_title_is_first_child_of_svg(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    m = re.search(r"<svg[^>]*>(<title>[^<]*</title>)", svg)
    assert m is not None, "The <title> element must be the first child of <svg>"


def test_title_names_origin_and_destination(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    assert "<title>Route from a to g" in svg


# ---------------------------------------------------------------------------
# Base schematic — every node present
# ---------------------------------------------------------------------------


def test_base_schematic_includes_all_nodes(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    for node in small_graph.nodes.values():
        assert re.search(
            rf'<circle cx="{node.x:g}" cy="{node.y:g}" r="6"[^>]*fill="{_SURFACE}"',
            svg,
        ) is not None, f"missing base circle for {node.zone_id}"


# ---------------------------------------------------------------------------
# Route edges
# ---------------------------------------------------------------------------


def test_route_edges_use_accent_and_3px(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    accent_3px = re.findall(
        rf'<line[^>]*stroke="{_ACCENT}"[^>]*stroke-width="3"[^>]*/>', svg
    )
    # Route has 5 nodes → 4 edges.
    assert len(accent_3px) == 4


# ---------------------------------------------------------------------------
# Non-route, non-closed edges are NOT drawn
# ---------------------------------------------------------------------------


def test_non_route_non_closed_edges_not_drawn(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    # (a, d): a(0,0) -> d(0,100). Off-route, not closed. Should NOT appear.
    assert not re.search(r'x1="0"\s+y1="0"\s+x2="0"\s+y2="100"', svg)
    # (d, e): d(0,100) -> e(100,100). Same story.
    assert not re.search(r'x1="0"\s+y1="100"\s+x2="100"\s+y2="100"', svg)


# ---------------------------------------------------------------------------
# Closed node overlay
# ---------------------------------------------------------------------------


def test_closed_node_renders_warn_and_x_marker(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, {"d"}, set()))
    # d at (0, 100): warn-fill circle overlay.
    assert re.search(
        rf'<circle cx="0" cy="100" r="6" fill="{_WARN}"',
        svg,
    ) is not None
    # X marker: two crossing lines centered at (0, 100).
    assert 'x1="-4" y1="96" x2="4" y2="104"' in svg
    assert 'x1="-4" y1="104" x2="4" y2="96"' in svg


def test_closed_node_wins_over_intermediate_role(small_graph: Graph) -> None:
    """Closed always beats route-intermediate rendering — defensive precedence."""
    svg = _decode(render_route(_route(), small_graph, {"b"}, set()))
    # b at (100, 0). If precedence held, we see warn-fill r=6, NOT accent r=7.
    assert re.search(rf'<circle cx="100" cy="0" r="6" fill="{_WARN}"', svg) is not None
    # No accent-fill r=7 circle at that coord.
    assert not re.search(rf'<circle cx="100" cy="0" r="7" fill="{_ACCENT}"', svg)


# ---------------------------------------------------------------------------
# Closed edge overlay
# ---------------------------------------------------------------------------


def test_closed_edge_renders_dashed_warn(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), {("b", "e")}))
    assert re.search(
        rf'<line[^>]*stroke="{_WARN}"[^>]*stroke-width="2"[^>]*stroke-dasharray="4 4"',
        svg,
    ) is not None


def test_closed_edge_lookup_is_direction_agnostic(small_graph: Graph) -> None:
    """(b, e) and (e, b) must both match the same graph edge."""
    forward = _decode(render_route(_route(), small_graph, set(), {("b", "e")}))
    reverse = _decode(render_route(_route(), small_graph, set(), {("e", "b")}))
    pattern = rf'<line[^>]*stroke="{_WARN}"[^>]*stroke-dasharray="4 4"'
    assert re.search(pattern, forward) is not None
    assert re.search(pattern, reverse) is not None


def test_closures_render_when_not_on_route(small_graph: Graph) -> None:
    """Closures always draw — even when they don't intersect the route."""
    svg = _decode(render_route(_route(), small_graph, set(), {("a", "d")}))
    # (a, d) is off-route (route is a-b-c-f-g), but the dashed warn edge is still there.
    assert re.search(
        rf'<line[^>]*stroke="{_WARN}"[^>]*stroke-dasharray="4 4"', svg
    ) is not None


# ---------------------------------------------------------------------------
# Overlay role sanity
# ---------------------------------------------------------------------------


def test_origin_node_uses_accent_r8(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    # a at (0, 0). Origin: r=8 accent fill.
    assert re.search(rf'<circle cx="0" cy="0" r="8" fill="{_ACCENT}"', svg) is not None
    assert "You are here" in svg


def test_destination_node_uses_text_fill(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    # g at (300, 50). Destination: r=8, fill = text color, stroke = accent.
    assert re.search(
        rf'<circle cx="300" cy="50" r="8" fill="{_TEXT}"[^>]*stroke="{_ACCENT}"', svg
    ) is not None


def test_intermediate_node_uses_accent_r7(small_graph: Graph) -> None:
    svg = _decode(render_route(_route(), small_graph, set(), set()))
    # b at (100, 0), an intermediate. r=7 accent fill.
    assert re.search(
        rf'<circle cx="100" cy="0" r="7" fill="{_ACCENT}"', svg
    ) is not None
