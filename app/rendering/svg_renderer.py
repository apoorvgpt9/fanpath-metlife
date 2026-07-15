"""Server-side SVG renderer for the ``/navigate`` response (Entry #12, #22).

The renderer draws whatever pathfinding produced — Gemini has no involvement
in SVG generation. The palette is inlined as literal hex values from
DESIGN.md because the SVG ships as a base64 data URI without a stylesheet
context that could resolve CSS custom properties.

Layer order (bottom to top):

1. Background fill + stadium outline (bounding rectangle).
2. Closed edges (always drawn, direction-agnostic).
3. Route edges (accent, 3px).
4. Nodes: base circle for every node, then role-specific overlay.

Node role precedence: closed > origin > destination > intermediate > base.
Closed always wins so fans can never mistake a closed zone for an open
waypoint even when the pathfinder's output includes it (defensive; the
pathfinder normally excludes closed nodes before Dijkstra).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from app.graph.loader import Graph, Node
from app.pathfinding.engine import RouteFound

# DESIGN.md palette, inlined (SVG data URI has no CSS custom property scope).
_COLOR_BG = "#0F172A"
_COLOR_SURFACE = "#1E293B"
_COLOR_TEXT = "#F1F5F9"
_COLOR_MUTED = "#94A3B8"
_COLOR_ACCENT = "#22D3EE"
_COLOR_WARN = "#F87171"

_MARGIN = 16  # --space-md from DESIGN.md
_LABEL_OFFSET_Y = 18


def _canon(a: str, b: str) -> tuple[str, str]:
    """Return the canonical (sorted) direction-agnostic edge key for ``(a, b)``."""
    return (a, b) if a < b else (b, a)


def _n(v: float) -> str:
    """Compact numeric formatting: whole numbers render without a decimal."""
    return f"{v:g}"


def _viewbox(graph: Graph) -> tuple[float, float, float, float]:
    """Return an ``(x, y, w, h)`` SVG viewBox that fits every node with a margin."""
    xs = [n.x for n in graph.nodes.values()]
    ys = [n.y for n in graph.nodes.values()]
    min_x, min_y = min(xs), min(ys)
    span_x = max(xs) - min_x
    span_y = max(ys) - min_y
    return (min_x - _MARGIN, min_y - _MARGIN, span_x + 2 * _MARGIN, span_y + 2 * _MARGIN)


def _stadium_outline(vb: tuple[float, float, float, float]) -> str:
    """Render the muted rounded rectangle framing the venue schematic."""
    x, y, w, h = vb
    inner_x = x + _MARGIN / 2
    inner_y = y + _MARGIN / 2
    inner_w = w - _MARGIN
    inner_h = h - _MARGIN
    return (
        f'<rect x="{_n(inner_x)}" y="{_n(inner_y)}" '
        f'width="{_n(inner_w)}" height="{_n(inner_h)}" '
        f'rx="12" fill="none" stroke="{_COLOR_MUTED}" stroke-width="1" />'
    )


def _line(u: Node, v: Node, stroke: str, width: str, extra: str = "") -> str:
    """Render a single ``<line>`` element between two nodes."""
    return (
        f'<line x1="{_n(u.x)}" y1="{_n(u.y)}" x2="{_n(v.x)}" y2="{_n(v.y)}" '
        f'stroke="{stroke}" stroke-width="{width}"{extra} />'
    )


def _closed_edges_layer(graph: Graph, closed_edges: set[tuple[str, str]]) -> str:
    """Render every currently-closed edge as a dashed warning line (Entry #22)."""
    if not closed_edges:
        return ""
    canonical = {_canon(a, b) for a, b in closed_edges}
    parts: list[str] = []
    for e in graph.edges:
        if _canon(e.from_id, e.to_id) not in canonical:
            continue
        u = graph.nodes[e.from_id]
        v = graph.nodes[e.to_id]
        parts.append(_line(u, v, _COLOR_WARN, "2", ' stroke-dasharray="4 4"'))
    return "".join(parts)


def _route_layer(route: RouteFound, graph: Graph) -> str:
    """Render the accent-colored polyline connecting the resolved route nodes."""
    parts: list[str] = []
    for a, b in zip(route.nodes, route.nodes[1:], strict=False):
        parts.append(_line(graph.nodes[a], graph.nodes[b], _COLOR_ACCENT, "3"))
    return "".join(parts)


def _zone_label(node: Node, text: str) -> str:
    """Render a muted centered text label positioned just below ``node``."""
    return (
        f'<text x="{_n(node.x)}" y="{_n(node.y + _LABEL_OFFSET_Y)}" '
        f'font-size="10" fill="{_COLOR_MUTED}" text-anchor="middle">'
        f"{text}</text>"
    )


def _base_node(node: Node) -> str:
    """Render the neutral base circle drawn under every node overlay."""
    return (
        f'<circle cx="{_n(node.x)}" cy="{_n(node.y)}" r="6" '
        f'fill="{_COLOR_SURFACE}" stroke="{_COLOR_MUTED}" stroke-width="1" />'
    )


def _closed_node(node: Node) -> str:
    """Render the warning-red X overlay used for closed nodes."""
    x, y = node.x, node.y
    return (
        f'<circle cx="{_n(x)}" cy="{_n(y)}" r="6" '
        f'fill="{_COLOR_WARN}" stroke="{_COLOR_TEXT}" stroke-width="1" />'
        f'<line x1="{_n(x - 4)}" y1="{_n(y - 4)}" '
        f'x2="{_n(x + 4)}" y2="{_n(y + 4)}" '
        f'stroke="{_COLOR_TEXT}" stroke-width="1.5" />'
        f'<line x1="{_n(x - 4)}" y1="{_n(y + 4)}" '
        f'x2="{_n(x + 4)}" y2="{_n(y - 4)}" '
        f'stroke="{_COLOR_TEXT}" stroke-width="1.5" />'
    )


def _origin_node(node: Node) -> str:
    """Render the accent-filled origin marker with a "You are here" label."""
    return (
        f'<circle cx="{_n(node.x)}" cy="{_n(node.y)}" r="8" '
        f'fill="{_COLOR_ACCENT}" stroke="{_COLOR_TEXT}" stroke-width="2" />'
        + _zone_label(node, "You are here")
    )


def _destination_node(node: Node) -> str:
    """Render the text-filled destination marker with the zone_id label."""
    return (
        f'<circle cx="{_n(node.x)}" cy="{_n(node.y)}" r="8" '
        f'fill="{_COLOR_TEXT}" stroke="{_COLOR_ACCENT}" stroke-width="2" />'
        + _zone_label(node, node.zone_id)
    )


def _intermediate_node(node: Node) -> str:
    """Render a small accent-filled marker for a waypoint on the route."""
    return (
        f'<circle cx="{_n(node.x)}" cy="{_n(node.y)}" r="7" '
        f'fill="{_COLOR_ACCENT}" stroke="none" />'
    )


@dataclass(frozen=True)
class _NodeRoles:
    """Node-role lookup passed to :func:`_render_node` for overlay selection."""

    origin: str
    destination: str
    intermediates: frozenset[str]
    closed: frozenset[str]


def _render_node(node: Node, roles: _NodeRoles) -> str:
    """Render a node with the highest-precedence role overlay it qualifies for."""
    base = _base_node(node)
    if node.zone_id in roles.closed:
        return base + _closed_node(node)
    if node.zone_id == roles.origin:
        return base + _origin_node(node)
    if node.zone_id == roles.destination:
        return base + _destination_node(node)
    if node.zone_id in roles.intermediates:
        return base + _intermediate_node(node)
    return base


def _nodes_layer(graph: Graph, roles: _NodeRoles) -> str:
    """Render every node in the graph with its role-appropriate overlay."""
    return "".join(_render_node(n, roles) for n in graph.nodes.values())


def _summary_title(
    route: RouteFound,
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> str:
    """Build the ``<title>`` / ``aria-label`` string summarizing the schematic."""
    parts = [
        f"Route from {route.origin} to {route.destination}",
        f"{route.total_walk_time_minutes:.1f} minutes",
    ]
    if closed_nodes or closed_edges:
        parts.append(
            f"{len(closed_nodes)} closed zone(s), {len(closed_edges)} closed edge(s)"
        )
    return "; ".join(parts) + "."


def _build_svg(
    graph: Graph,
    route: RouteFound,
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> str:
    """Assemble the full SVG document string for ``route`` on ``graph``."""
    intermediates = frozenset(route.nodes[1:-1]) if len(route.nodes) > 2 else frozenset()
    roles = _NodeRoles(
        origin=route.origin,
        destination=route.destination,
        intermediates=intermediates,
        closed=frozenset(closed_nodes),
    )
    vb = _viewbox(graph)
    vx, vy, vw, vh = vb
    title = _summary_title(route, closed_nodes, closed_edges)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{_n(vx)} {_n(vy)} {_n(vw)} {_n(vh)}" '
        f'role="img" aria-label="{title}">'
        f"<title>{title}</title>"
        f'<rect x="{_n(vx)}" y="{_n(vy)}" '
        f'width="{_n(vw)}" height="{_n(vh)}" fill="{_COLOR_BG}" />'
        f"{_stadium_outline(vb)}"
        f"{_closed_edges_layer(graph, closed_edges)}"
        f"{_route_layer(route, graph)}"
        f"{_nodes_layer(graph, roles)}"
        f"</svg>"
    )


def _to_data_uri(svg: str) -> str:
    """Wrap raw SVG markup in a ``data:image/svg+xml;base64,...`` URI."""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def render_route(
    route: RouteFound,
    graph: Graph,
    closed_nodes: set[str],
    closed_edges: set[tuple[str, str]],
) -> str:
    """Return a ``data:image/svg+xml;base64,...`` URI for the given route.

    Closures render regardless of whether they intersect the route (Entry
    #22) — fans see the full venue closure picture, not only closures on
    their path.
    """
    svg = _build_svg(graph, route, closed_nodes, closed_edges)
    return _to_data_uri(svg)


__all__ = ["render_route"]
