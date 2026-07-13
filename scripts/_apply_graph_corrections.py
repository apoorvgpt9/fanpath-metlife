"""One-off manual-correction step for the Phase 1a graph draft.

Not part of the app runtime. Documents exactly what was changed relative to
the Gemini draft so the audit trail lives in the repo.

Changes applied to data/metlife_graph.draft.json to produce metlife_graph.json:

1. Section-uniqueness fix (verify_graph would fail otherwise):
     - corona_beach_club: remove sections 207C, 208, 210, 212
       (already owned by concourse_200_east; keep as landmark aliases).
     - metlife_50_club: remove section 242C (owned by concourse_200_west).
     - coaches_club: keep only 111C-115C (C-suffix club sections unique to it).

2. Accessibility-subgraph connectivity fix:
     - Edge concourse_100_east <-> coaches_club changed from stairs_only
       to elevator. The draft made coaches_club unreachable in the
       accessibility subgraph (only edge was stairs_only).

3. Section-coverage fill (so common lower/mezzanine section numbers resolve):
     - concourse_100_east gains 116-122.
     - concourse_200_east gains 216-223.
     - concourse_200_northeast gains 207/209/211/213 (non-C variants).

Everything else in the draft is kept verbatim: 36 nodes, 51 edges, gate
plazas (A-K skipping I), three concourse levels sub-divided into 6 zones
each, premium clubs + press box + field tunnels.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "metlife_graph.draft.json"
DST = REPO_ROOT / "data" / "metlife_graph.json"

CLUBS_TO_STRIP = {
    "corona_beach_club": ["207C", "208", "210", "212"],
    "metlife_50_club": ["242C"],
}
COACHES_KEEP = ["111C", "112C", "113C", "114C", "115C"]
COACHES_EDGE_PAIR = frozenset({"concourse_100_east", "coaches_club"})
FILLS = {
    "concourse_100_east": ["116", "117", "118", "119", "120", "121", "122"],
    "concourse_200_east": ["216", "217", "218", "219", "220", "221", "222", "223"],
    "concourse_200_northeast": ["207", "209", "211", "213"],
}


def _numeric_sort_key(section: str) -> tuple[int, str]:
    digits = "".join(c for c in section if c.isdigit())
    return (int(digits) if digits else 0, section)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def apply_corrections(data: dict) -> dict:
    for node in data["nodes"]:
        zid = node["zone_id"]
        if zid in CLUBS_TO_STRIP:
            removed = CLUBS_TO_STRIP[zid]
            node["sections"] = [s for s in node["sections"] if s not in removed]
            aliases = node["landmark_aliases"] + [
                f"lounge attached to section {s}" for s in removed
            ]
            node["landmark_aliases"] = _dedupe_preserve_order(aliases)
        if zid == "coaches_club":
            node["sections"] = list(COACHES_KEEP)
        if zid in FILLS:
            combined = set(node["sections"]) | set(FILLS[zid])
            node["sections"] = sorted(combined, key=_numeric_sort_key)
    for edge in data["edges"]:
        if frozenset({edge["from"], edge["to"]}) == COACHES_EDGE_PAIR:
            edge["accessibility"] = "elevator"
    return data


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    corrected = apply_corrections(data)
    DST.write_text(json.dumps(corrected, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {DST.relative_to(REPO_ROOT)}: "
        f"{len(corrected['nodes'])} nodes, {len(corrected['edges'])} edges"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
