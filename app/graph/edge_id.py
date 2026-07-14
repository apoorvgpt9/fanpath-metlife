"""Canonical, direction-agnostic edge identifiers.

Phase 4A resolves the gap noted in Phase 1: ``venue_state.closed_edges`` is
stored as a flat list of strings, but ``pathfinding.engine.find_route``
consumes ``set[tuple[str, str]]``. This module is the one-way encoding
between the two representations.

Encoding: ``f"{a}__{b}"`` where ``(a, b) = sorted((from_id, to_id))``.
Because the tuple is sorted, ``edge_id("a", "b") == edge_id("b", "a")`` — the
graph edges are undirected (Entry #8), so closures must be too.
"""

from __future__ import annotations

_SEPARATOR = "__"


def edge_id(from_id: str, to_id: str) -> str:
    """Encode an undirected edge as a canonical string."""
    if not from_id or not to_id:
        raise ValueError("edge endpoints must be non-empty")
    if _SEPARATOR in from_id or _SEPARATOR in to_id:
        raise ValueError(f"zone_id must not contain the reserved separator {_SEPARATOR!r}")
    a, b = sorted((from_id, to_id))
    return f"{a}{_SEPARATOR}{b}"


def parse_edge_id(value: str) -> tuple[str, str]:
    """Decode an edge id back into its ``(a, b)`` pair. Round-trips ``edge_id``."""
    if not isinstance(value, str) or _SEPARATOR not in value:
        raise ValueError(f"not a valid edge id: {value!r}")
    parts = value.split(_SEPARATOR)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"not a valid edge id: {value!r}")
    return parts[0], parts[1]


__all__ = ["edge_id", "parse_edge_id"]
