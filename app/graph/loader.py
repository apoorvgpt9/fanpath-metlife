"""Load ``data/metlife_graph.json`` (or any conformant file) into memory.

Pure loader: reads a static JSON file from disk and returns a frozen
:class:`Graph`. No Firestore, no network, no closure application — closures are
applied at pathfinding time (Entry #16), not here.

The default path points at the real MetLife graph, but :func:`load_graph`
accepts an arbitrary path so Layer-2 unit tests can load small synthetic
fixtures (Entry #21) instead of the 36-node production graph. This module is
NOT yet wired into ``app/main.py``; that happens in Phase 4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_GRAPH_PATH = REPO_ROOT / "data" / "metlife_graph.json"


@dataclass(frozen=True)
class Node:
    """A navigable zone in the stadium graph (Entry #8)."""

    zone_id: str
    sections: tuple[str, ...]
    amenities: dict[str, bool]
    landmark_aliases: tuple[str, ...]
    x: float
    y: float


@dataclass(frozen=True)
class Edge:
    """An undirected, weighted, accessibility-classified connection (Entry #8)."""

    from_id: str
    to_id: str
    walk_time_minutes: float
    accessibility: str


@dataclass(frozen=True)
class Graph:
    """In-memory view of the static graph JSON."""

    nodes: dict[str, Node]
    edges: tuple[Edge, ...]


def _node_from_dict(raw: dict[str, Any]) -> Node:
    """Build a :class:`Node` from a decoded JSON dict."""
    return Node(
        zone_id=raw["zone_id"],
        sections=tuple(raw.get("sections", [])),
        amenities=dict(raw.get("amenities", {})),
        landmark_aliases=tuple(raw.get("landmark_aliases", [])),
        x=float(raw.get("x", 0)),
        y=float(raw.get("y", 0)),
    )


def _edge_from_dict(raw: dict[str, Any]) -> Edge:
    """Build an :class:`Edge` from a decoded JSON dict."""
    return Edge(
        from_id=raw["from"],
        to_id=raw["to"],
        walk_time_minutes=float(raw["walk_time_minutes"]),
        accessibility=raw["accessibility"],
    )


def load_graph(path: str | Path) -> Graph:
    """Load a graph from an arbitrary JSON path (Entry #8).

    Raises ``FileNotFoundError`` if the file is missing, ``ValueError`` if the
    JSON is missing top-level ``nodes`` / ``edges`` keys or contains a
    duplicate ``zone_id``. All other malformed-shape errors propagate as the
    underlying :class:`KeyError` / :class:`json.JSONDecodeError` — the Layer-1
    ``verify_graph`` script is the deep validator; this loader assumes the
    file has already been verified.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "nodes" not in data or "edges" not in data:
        raise ValueError(f"{p}: missing top-level 'nodes'/'edges' keys")

    nodes: dict[str, Node] = {}
    for raw in data["nodes"]:
        node = _node_from_dict(raw)
        if node.zone_id in nodes:
            raise ValueError(f"{p}: duplicate zone_id '{node.zone_id}'")
        nodes[node.zone_id] = node

    edges = tuple(_edge_from_dict(raw) for raw in data["edges"])
    return Graph(nodes=nodes, edges=edges)


def load_default_graph() -> Graph:
    """Load the production MetLife graph from ``DEFAULT_GRAPH_PATH``."""
    return load_graph(DEFAULT_GRAPH_PATH)
