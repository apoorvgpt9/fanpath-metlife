# Smart Indoor Navigation — MetLife Stadium

_Fan-facing GenAI navigation for MetLife Stadium during the FIFA World Cup 2026 final. Ask in your own words where you are and where you're going — get text directions and a schematic route map, in your language, with your accessibility needs honored._

**Live demo:** _(pending Phase 0 deploy — updated in place)_

**Status:** _(pending Phase 0 — updated in place)_

**Coverage:** _(pending Phase 2 close — updated in place)_

---

## What this is

A GenAI-enabled indoor navigation app for a real-world venue (MetLife Stadium, host of the FIFA World Cup 2026 final). Fans describe their location and destination in natural language — no dropdowns, no section-number lookup — and receive:

1. A conversational, turn-by-turn route explanation in one of five languages (English, Spanish, French, Portuguese, Arabic).
2. A schematic map of the stadium with the route highlighted, current closures marked, and origin/destination distinct.

A thin staff layer lets on-ground staff mark gates, escalators, or concourse sections as closed. Fan routes adapt in real time.

## Why this is a GenAI application, not a search bar on a map

The GenAI value is **ambiguity resolution**. A fan doesn't type "Section 128" — they say "I'm near the big Pepsi sign on the upper level, where's the closest bathroom my wheelchair can reach." That query has a vague landmark, no section number, and an embedded accessibility constraint. A dropdown can't parse it. A regex can't parse it. A language model can.

The Intent Agent resolves ambiguous landmarks against known graph zones, extracts accessibility constraints from natural language, and either (a) resolves a single origin, (b) asks a clarifying question with specific options, or (c) falls back to a deterministic dropdown when no landmark matches.

Once the origin, destination, and constraints are resolved, a **deterministic Dijkstra** computes the route. The model never invents a path. The Guide Agent explains the deterministic route in the fan's preferred language.

## Features

- **Natural-language navigation** — "how do I get to Section 128" through "we have four kids and my mother-in-law can't climb stairs, we want food before the match starts in 20 minutes."
- **Accessibility-aware routing** — wheelchair, no-stairs, stroller, and visual-impairment constraints filter the graph before pathfinding runs. Stairs-warning safety check when a fan without stated constraints is about to be sent to stairs.
- **Five-language responses** — English, Spanish, French, Portuguese, Arabic.
- **Dynamic closures** — staff mark a gate or escalator closed; the next fan navigation request routes around it. Zero staleness window.
- **Six amenity types** — restroom, food, merchandise, ATM, first aid, charging station. Amenity queries route to the nearest zone providing them.
- **Schematic route map** — server-rendered SVG on a stylized stadium outline. No frontend mapping library. Closures always shown; route highlighted.
- **Multi-turn context** — three-turn rolling window so "how do I get back to my seat from there" resolves correctly.

## Architecture at a glance

```
┌────────────┐   NL query    ┌───────────────┐   structured request   ┌────────────────┐
│ Fan browser├──────────────►│ Intent Agent  ├───────────────────────►│ Deterministic  │
│ (static)   │               │ (Gemini)      │                        │ Dijkstra       │
└────────────┘               └───────────────┘                        └────────┬───────┘
                                                                              │ RouteFound |
                                                                              │ RouteBlocked
                                                                              ▼
                             ┌───────────────┐   route + query        ┌────────────────┐
                             │ Guide Agent   │◄───────────────────────┤ Pathfinding    │
                             │ (Gemini, per- │                        │ result         │
                             │  language)    │                        └────────────────┘
                             └───────┬───────┘
                                     │
                                     ▼
                             ┌───────────────┐
                             │ Text + SVG    │
                             │ (JSON, inline │
                             │  base64 SVG)  │
                             └───────────────┘
```

**Two agents, deterministic pathfinding between them.** The model never invents a route. Pathfinding is Dijkstra on a static, hand-corrected zone graph derived from public MetLife venue maps.

## Structure walkthrough

```
.
├── DECISIONS.md          # The 25 locked architectural decisions (constitutional doc)
├── DESIGN.md             # Frontend design constitution (palette, type, spacing, tone)
├── PROGRESS.md           # Rolling build log + verifiable claim set for `make verify-docs`
├── SECURITY.md           # OWASP walkthrough, threat model, known limitations
├── README.md             # This file
├── Makefile              # lint, test, verify-graph, verify-docs, run, deploy
├── pyproject.toml        # Dependencies + ruff config + coverage floor
├── Dockerfile            # Cloud Run image (--no-server-header, etc.)
├── app/                  # FastAPI application
│   ├── main.py           # App initialization (redirect_slashes=False, CORS, headers)
│   ├── agents/           # Intent Agent, Guide Agent
│   ├── pathfinding/      # Deterministic Dijkstra, discriminated union output
│   ├── graph/            # Static graph loader, validation
│   ├── rendering/        # Server-side SVG route rendering
│   ├── auth/             # Firebase Anonymous + STAFF_TOKEN
│   ├── firestore/        # fans, venue_state
│   └── errors/           # Two-category error contract
├── static/               # Static frontend (fan.html, staff.html, style.css)
├── data/
│   └── metlife_graph.json  # Static zone graph (35-45 nodes)
├── scripts/
│   ├── verify_graph.py       # Layer-1 data-integrity check
│   ├── verify_docs.py        # DECISIONS.md ↔ code sync check
│   └── check_function_length.py  # AST-based max-function-length check
└── tests/
    ├── unit/             # Layer-2 pathfinding tests (small test graphs)
    ├── contract/         # Layer-3 agent contract tests (Gemini mocked)
    └── integration/      # Layer-4 full-endpoint tests
```

## Running locally

```bash
# One-time setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Set env vars (see .env.example)
export GEMINI_API_KEY=...
export STAFF_TOKEN=...
export FIREBASE_PROJECT_ID=...

# Run all quality gates
make lint            # ruff + function-length check
make test            # pytest with 95% coverage floor
make verify-graph    # Layer-1 graph data integrity
make verify-docs     # DECISIONS.md ↔ code sync

# Serve
make run             # uvicorn app.main:app --reload
```

Fan interface: <http://localhost:8080/static/fan.html>
Staff interface: <http://localhost:8080/static/staff.html>

## Staff access

Staff endpoints (`POST /staff/closures`, `GET /staff/closures`) require a shared bearer token. **For evaluator access to this demo, use the token: `_(added at Phase 0 deploy)_`**

See SECURITY.md for the auth rationale and the production-hardening path.

## Technical notes

- **Graph is sourced, not measured.** Zone topology is derived from published MetLife venue maps (seating charts, ADA maps, concourse diagrams). Walk-time estimates are constructed from map distances, not observed. Every section maps to exactly one zone; `make verify-graph` enforces connectivity and accessibility-path existence.
- **The graph is a design boundary, not a TODO.** The same schema extends to any other World Cup venue.
- **Anonymous auth is intentional** — the CSP/auth pain of a full Google Sign-In flow is not worth the trade at evaluation scale. Documented limitation: closing the browser or clearing cookies loses the profile.
- **Coverage: 95% floor enforced in CI, actual achieved number reported here at submission.**

## What's out of scope (deliberate design boundaries)

- Wayfinding beyond the stadium interior (parking lot navigation is a known extension point, not built).
- Group-composition profile fields (group size doesn't change routes — dead code).
- Staff dashboards, heatmaps, volunteer assignment, crowd analytics (Entry #2 in DECISIONS.md).
- Vendor-level food detail (routing to nearest food zone, not to a specific pizza vendor).
- End-to-end tests against real Gemini or real Firestore (flakiness > value).

See DECISIONS.md Entry #17 and Entry #22 for future-enhancement extension points.

## License

_(added at Phase 5)_
