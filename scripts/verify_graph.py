"""Layer-1 graph data-integrity check.

In Phase 0 this is a placeholder: it exits 0 if the graph JSON does not yet
exist, so CI does not fail on a Phase 1 deliverable that has not been built.

Phase 1b will replace the placeholder with real validation:
    - every zone has non-empty ``sections`` (uniqueness across zones)
    - node coordinates present and within stadium bounds
    - graph is connected under the union of all edges
    - accessibility-aware subgraph (edges with acc != stairs_only) is connected
    - walk-time estimates fall within a plausible bound
    - amenity enum values match the six-value spec
    - no orphan nodes; no self-loops
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = REPO_ROOT / "data" / "metlife_graph.json"


def main() -> int:
    if not GRAPH_PATH.exists():
        print(f"No graph yet (Phase 1) — skipping ({GRAPH_PATH.relative_to(REPO_ROOT)} absent)")
        return 0

    # TODO: Phase 1b — real validation logic goes here.
    print(f"Graph present at {GRAPH_PATH.relative_to(REPO_ROOT)}; validation not yet implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
