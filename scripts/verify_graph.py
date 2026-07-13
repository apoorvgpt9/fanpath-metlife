"""Layer-1 graph data-integrity check for data/metlife_graph.json.

Enforces the schema and connectivity guarantees required by DECISIONS.md
Entry #8 (zone-level graph, edge accessibility filtering), Entry #11 (six
amenity types), and Entry #14 (validation script guarantees internal
consistency, not external correctness).

Hard failures (exit 1):
    - graph file exists but is malformed / missing top-level keys
    - non-empty ``sections`` per node; no section number in >1 zone
    - ``landmark_aliases`` per node must be a non-empty list of strings
      (Phase 3 Intent Agent depends on this field; no fallback exists)
    - orphan nodes (no incident edges)
    - self-loop edges
    - full graph is not connected
    - accessibility subgraph (edges where accessibility != stairs_only)
      is not connected
    - amenity keys do not match the six-value enum exactly
    - edge ``accessibility`` value not in the four-value enum
    - ``walk_time_minutes`` missing or <= 0
    - duplicate zone_ids
    - edge references a zone_id that does not exist

Soft warnings (print but do not fail the build):
    - single edge with walk_time_minutes > 15

If the graph file does not exist, exit 0 with a "skipping" message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = REPO_ROOT / "data" / "metlife_graph.json"

AMENITY_KEYS = frozenset(
    {"restroom", "food", "merchandise", "atm", "first_aid", "charging_station"}
)
EDGE_ACCESSIBILITY_VALUES = frozenset(
    {"stairs_only", "ramp", "elevator", "level"}
)
WALK_TIME_WARN_THRESHOLD = 15


def _load(path: Path) -> tuple[list[dict], list[dict]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: {path.name} could not be parsed: {exc}")
        return None
    if not isinstance(data, dict) or "nodes" not in data or "edges" not in data:
        print(f"FAIL: {path.name} missing top-level 'nodes'/'edges'")
        return None
    return data["nodes"], data["edges"]


def _check_nodes(nodes: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    section_owners: dict[str, list[str]] = {}
    for i, node in enumerate(nodes):
        zid = node.get("zone_id")
        if not zid:
            errors.append(f"node[{i}] missing zone_id")
            continue
        if zid in seen_ids:
            errors.append(f"duplicate zone_id: {zid}")
        seen_ids.add(zid)
        sections = node.get("sections", [])
        if not isinstance(sections, list):
            errors.append(f"{zid}: sections must be a list")
        else:
            for s in sections:
                section_owners.setdefault(s, []).append(zid)
        amenities = node.get("amenities", {})
        if not isinstance(amenities, dict) or set(amenities.keys()) != AMENITY_KEYS:
            got = sorted(amenities.keys()) if isinstance(amenities, dict) else amenities
            errors.append(
                f"{zid}: amenity keys must equal exactly {sorted(AMENITY_KEYS)}; got {got}"
            )
        aliases = node.get("landmark_aliases")
        if (
            not isinstance(aliases, list)
            or not aliases
            or not all(isinstance(a, str) and a.strip() for a in aliases)
        ):
            errors.append(
                f"{zid}: landmark_aliases must be a non-empty list of non-empty strings"
            )
    for section, owners in section_owners.items():
        if len(owners) > 1:
            errors.append(
                f"section '{section}' appears in multiple zones: {sorted(owners)}"
            )
    return errors


def _check_edges(edges: list[dict], node_ids: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, edge in enumerate(edges):
        u = edge.get("from")
        v = edge.get("to")
        acc = edge.get("accessibility")
        wt = edge.get("walk_time_minutes")
        if u not in node_ids:
            errors.append(f"edge[{i}] from='{u}' is not a known zone_id")
        if v not in node_ids:
            errors.append(f"edge[{i}] to='{v}' is not a known zone_id")
        if u is not None and u == v:
            errors.append(f"edge[{i}] self-loop on '{u}'")
        if acc not in EDGE_ACCESSIBILITY_VALUES:
            errors.append(
                f"edge[{i}] {u}<->{v} accessibility='{acc}' "
                f"not in {sorted(EDGE_ACCESSIBILITY_VALUES)}"
            )
        if not isinstance(wt, (int, float)) or wt <= 0:
            errors.append(
                f"edge[{i}] {u}<->{v} walk_time_minutes must be positive; got {wt!r}"
            )
        elif wt > WALK_TIME_WARN_THRESHOLD:
            warnings.append(
                f"edge {u}<->{v} walk_time_minutes={wt} exceeds soft threshold "
                f"{WALK_TIME_WARN_THRESHOLD}"
            )
    return errors, warnings


def _connected(node_ids: set[str], adjacency: dict[str, set[str]]) -> set[str]:
    if not node_ids:
        return set()
    start = next(iter(node_ids))
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in adjacency[u]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def _check_connectivity(nodes: list[dict], edges: list[dict]) -> list[str]:
    node_ids = {n["zone_id"] for n in nodes if n.get("zone_id")}
    full_adj: dict[str, set[str]] = {n: set() for n in node_ids}
    acc_adj: dict[str, set[str]] = {n: set() for n in node_ids}
    for edge in edges:
        u, v = edge.get("from"), edge.get("to")
        if u not in node_ids or v not in node_ids:
            continue
        full_adj[u].add(v)
        full_adj[v].add(u)
        if edge.get("accessibility") != "stairs_only":
            acc_adj[u].add(v)
            acc_adj[v].add(u)

    errors: list[str] = []
    orphans = [n for n in node_ids if not full_adj[n]]
    if orphans:
        errors.append(f"orphan nodes (no edges): {sorted(orphans)}")
    unreached_full = sorted(node_ids - _connected(node_ids, full_adj))
    if unreached_full:
        errors.append(f"full graph is not connected; unreachable: {unreached_full}")
    unreached_acc = sorted(node_ids - _connected(node_ids, acc_adj))
    if unreached_acc:
        errors.append(
            "accessibility subgraph (edges != stairs_only) is not connected; "
            f"unreachable: {unreached_acc}"
        )
    return errors


def main() -> int:
    if not GRAPH_PATH.exists():
        print(f"No graph yet (Phase 1) — skipping ({GRAPH_PATH.relative_to(REPO_ROOT)} absent)")
        return 0

    loaded = _load(GRAPH_PATH)
    if loaded is None:
        return 1
    nodes, edges = loaded

    errors: list[str] = []
    errors.extend(_check_nodes(nodes))
    node_ids = {n["zone_id"] for n in nodes if n.get("zone_id")}
    edge_errors, edge_warnings = _check_edges(edges, node_ids)
    errors.extend(edge_errors)
    errors.extend(_check_connectivity(nodes, edges))

    for w in edge_warnings:
        print(f"WARN: {w}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"\n{len(errors)} hard failure(s); {len(edge_warnings)} warning(s)")
        return 1

    print(
        f"OK: {len(nodes)} nodes, {len(edges)} edges; "
        f"{len(edge_warnings)} warning(s); "
        "full + accessibility subgraphs connected; sections unique"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
