"""One-off Gemini draft generator for the MetLife zone graph.

NOT part of the app. NOT wired into the Makefile. Run manually to produce
``data/metlife_graph.draft.json`` for the Phase 1a manual-correction step.

Usage:
    export GEMINI_API_KEY=...
    python scripts/draft_graph.py

Per DECISIONS.md Entry #14 (hybrid draft + manual correction + validation)
and Entry #26 (Gemini model strings: gemini-3.5-flash is the Flash-tier GA
model as of 2026-07-13). Entry #27's 3-hour cap on Phase 1a starts from the
moment this script produces its first draft.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from google import genai

REPO_ROOT = Path(__file__).resolve().parent.parent
DRAFT_PATH = REPO_ROOT / "data" / "metlife_graph.draft.json"
MODEL = "gemini-3.5-flash"

PROMPT = """You are drafting a NAVIGABLE ZONE GRAPH for MetLife Stadium
(East Rutherford, NJ; capacity ~82,500; U-shape/oval; host of the FIFA
World Cup 2026 final). This draft will be manually corrected by a human
before it is used, so err on the side of covering real public landmarks
even if you are not 100% sure of exact adjacency.

Return STRICT JSON matching this schema exactly (no markdown fences, no
prose). Target 35-45 nodes.

{
  "nodes": [
    {
      "zone_id": "snake_case_identifier",
      "sections": ["<numbered section strings from MetLife's public 100/200/300 seating chart>"],
      "amenities": {
        "restroom": true|false,
        "food": true|false,
        "merchandise": true|false,
        "atm": true|false,
        "first_aid": true|false,
        "charging_station": true|false
      },
      "landmark_aliases": ["human phrase 1", "human phrase 2"],
      "x": <int 0..800>,
      "y": <int 0..600>
    }
  ],
  "edges": [
    {
      "from": "<zone_id>",
      "to": "<zone_id>",
      "walk_time_minutes": <1..10 integer>,
      "accessibility": "stairs_only" | "ramp" | "elevator" | "level"
    }
  ]
}

REQUIREMENTS:
- MetLife has ~10 gates on the exterior (Gate A through K skipping I). Include
  each as its own zone.
- Three seating levels: lower bowl (sections 100-149), mezzanine (200s),
  upper bowl (300s). Subdivide each level's concourse into 3-4 zones
  (west/east/north/south sides).
- Include the field-level tunnel/premium clubs, the outdoor plazas outside
  the main gates, and named premium clubs (MetLife Gate/Verizon Gate area,
  Coaches Club, Commissioner's Club) where publicly known.
- Every zone MUST have landmark_aliases with at least 2 human-friendly
  phrases a fan might say ("near the big Pepsi sign", "west concourse by
  gate C", "upper deck south side", etc.).
- Amenity distribution should be realistic: restrooms and food nearly
  everywhere on concourses; ATMs and merchandise only in a subset;
  first_aid at every level (1-2 per level); charging_stations rare.
- Edges: use "level" for flat concourse walks, "ramp" for ADA ramps,
  "elevator" for the vertical shafts between levels, "stairs_only" for
  stair-only vertical connections. Every level MUST have at least one
  elevator or ramp edge connecting it to the level above.
- Walk times: 1-3 minutes for adjacent concourse zones on the same level,
  2-5 minutes for a level change via elevator, 3-7 minutes for gate-to-seat.
- Coordinates: place gates around the perimeter of an 800x600 canvas,
  lower-bowl zones inside the perimeter, upper-bowl zones toward the
  center (or offset per level so they don't stack). Do not stack multiple
  nodes on identical (x, y).

Output ONLY the JSON object. No commentary.
"""


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now(UTC).isoformat(timespec="seconds")
    print(f"[{started}] Drafting graph via {MODEL} ...")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=PROMPT,
        config={"response_mime_type": "application/json"},
    )
    raw = response.text or ""
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    print(f"[{finished}] Response received ({len(raw)} chars). Parsing...")

    # Validate JSON, then re-serialize pretty for diffable manual correction.
    parsed = json.loads(raw)
    DRAFT_PATH.write_text(json.dumps(parsed, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    node_count = len(parsed.get("nodes", []))
    edge_count = len(parsed.get("edges", []))
    print(f"Wrote {DRAFT_PATH.relative_to(REPO_ROOT)}: {node_count} nodes, {edge_count} edges")
    print(f"PHASE 1A CAP STARTED AT: {started} (3 hours per DECISIONS.md Entry #27)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
