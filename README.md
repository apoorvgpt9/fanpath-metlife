# Smart Indoor Navigation — MetLife Stadium

_Fan-facing GenAI navigation for MetLife Stadium during the FIFA World Cup 2026 final. Ask in your own words where you are and where you're going — get text directions and a schematic route map, in your language, with your accessibility needs honored._

**Live demo:** <https://fanpath-metlife-973486326780.asia-south1.run.app> — the full JSON API is live (`/health`, `/profile`, `/navigate`, `/staff/closures`) and the static fan/staff web pages are served under `/static/`.

**Status:** Phase 6 of 6 complete (skeleton, MetLife zone graph, Firebase Auth, Firestore schema, deterministic pathfinding, Intent Agent + Guide Agent with Gemini, six-endpoint API surface with closures/rate limiting/error contract, deterministic SVG route renderer, static fan chat + staff closure panel, CSP header, amenity-type destination resolution, `GET /` redirect to the fan UI, presentation pass with OWASP Top 10 walkthrough and pip-audit in CI, final gauntlet verified, deployed). All four manual-browser checks (sign-in/UI load, route+map rendering, accessibility rerouting, staff toggle round trip) confirmed by human tester. Ready for submission.

**Coverage:** 100.00% across 193 tests (`app/`, floor enforced at 100%)

---

## Evaluation criteria map

| Criterion | How it's addressed | Where to verify |
| --- | --- | --- |
| **Code Quality** | ruff (`C901`/`PLR0912`/`PLR0915` selected, `max-complexity = 10`, plus `N`/`UP`/`C4`/`SIM`/`RUF`/`BLE001`/pydocstyle rules) + an AST-based 80-line function cap + `mypy` strict + `interrogate` docstring coverage, all wired as separate CI gates. 100% test coverage floor (not just measured — enforced, `--cov-fail-under=100`). | [pyproject.toml](pyproject.toml) (`[tool.ruff]`, `[project.optional-dependencies]`), [Makefile](Makefile) (`lint`, `typecheck`, `docstrings`, `test` targets), [scripts/check_function_length.py](scripts/check_function_length.py) |
| **Problem Statement Alignment** | Every "hard case" surfaced during the pre-build grilling session is logged in DECISIONS.md and traced to a real test or an explicit, documented scope boundary (e.g. Lot K parking navigation, called out as out of scope rather than silently unhandled). | [DECISIONS.md](DECISIONS.md) (grilling-session entries, e.g. Entry #4), README's ["What's out of scope"](README.md#whats-out-of-scope-deliberate-design-boundaries) section below, [tests/contract/](tests/contract/) and [tests/integration/](tests/integration/) |
| **Security** | Full OWASP Top 10 walkthrough (A01–A10) written against the actual auth/data/dependency posture, not generic advice. A same-origin CSP with no `unsafe-inline` is enforced on every response via middleware. | [SECURITY.md](SECURITY.md) (`## OWASP Top 10 walkthrough`), [app/main.py](app/main.py) (`_CSP` + `SecurityHeadersMiddleware`) |
| **Efficiency** | Routing itself is a deterministic Dijkstra over a static in-memory graph — no LLM call sits on the pathfinding critical path, only on NL parsing/explanation either side of it. Both Gemini tiers run on Flash (Entry #29) with an output-token cap. Fan/staff rate limits bound request volume per client. | Live demo URL at the top of this file, [app/pathfinding/engine.py](app/pathfinding/engine.py) (`find_route`/`find_nearest_amenity`, no `agents` import), [app/rate_limit.py](app/rate_limit.py) (`FAN_LIMIT`/`STAFF_LIMIT`), [docs/BUILD-LOG.md](docs/BUILD-LOG.md) (efficiency remediation running-log entry) |
| **Testing** | 193 tests across four independent layers — graph data integrity, small-synthetic-graph pathfinding units, Gemini-mocked agent contract tests, and full-endpoint integration tests against the real graph with Firestore mocked at the boundary. 100.00% coverage on `app/`. | [tests/unit/](tests/unit/), [tests/contract/](tests/contract/), [tests/integration/](tests/integration/), [scripts/verify_graph.py](scripts/verify_graph.py), [CLAUDE.md](CLAUDE.md) (`## Testing layers`) |
| **Accessibility** | Both static pages use skip links, semantic landmarks, `aria-live` regions for async updates, visually-hidden `<label>`s on every input, and `role="alert"` error messaging — governed by a locked, rule-based accessibility section rather than ad hoc effort. | [static/fan.html](static/fan.html), [static/staff.html](static/staff.html), [DESIGN.md](DESIGN.md) (`## Accessibility (enforced by rule, not aspiration)`) |

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
├── DECISIONS.md          # The 28 locked architectural decisions (constitutional doc)
├── DESIGN.md             # Frontend design constitution (palette, type, spacing, tone) — Phase 4B
├── PROGRESS.md           # Current-state snapshot: phase status + verifiable claim set for `make verify-docs`
├── docs/
│   └── BUILD-LOG.md      # Full phase-by-phase running log, deviation tracker, health log, hotfix log (split from PROGRESS.md)
├── SECURITY.md           # OWASP walkthrough, threat model, known limitations
├── README.md             # This file
├── CLAUDE.md             # Map to the governing docs, for any Claude Code session in this repo
├── Makefile              # lint, test, verify-graph, verify-docs, run, deploy
├── pyproject.toml        # Dependencies + ruff config + coverage floor
├── Dockerfile            # Cloud Run image (--no-server-header, copies app/ + data/ + static/)
├── app/                  # FastAPI application
│   ├── main.py           # App assembly: middleware, exception handlers, startup graph load
│   ├── routes.py         # The six endpoint handlers (Entry #19)
│   ├── schemas.py        # HTTP-boundary Pydantic request/response models
│   ├── errors.py         # Two-category error contract (Entry #23)
│   ├── rate_limit.py     # slowapi Limiter, fan/staff rate limits
│   ├── agents/           # Intent Agent, Guide Agent, Gemini client factory
│   ├── pathfinding/      # Deterministic Dijkstra, discriminated union output
│   ├── graph/            # Static graph loader + edge-id encoding
│   ├── rendering/        # Server-side SVG route rendering (deterministic, Gemini-free)
│   ├── auth/             # Firebase Anonymous (fan) + STAFF_TOKEN (staff)
│   ├── firestore/        # fans, venue_state
│   └── models/           # Shared enums (AccessibilityFlag, PreferredLanguage, etc.)
├── static/               # Static frontend: fan.html, fan.js, staff.html, staff.js, style.css, firebase-config.js
├── data/
│   └── metlife_graph.json  # Static zone graph (36 nodes, 54 edges)
├── scripts/
│   ├── verify_graph.py       # Layer-1 data-integrity check
│   ├── verify_docs.py        # DECISIONS.md ↔ code sync check
│   ├── check_function_length.py  # AST-based max-function-length check
│   └── gemini_preflight.py   # Re-runnable live check that both model tiers respond
└── tests/
    ├── unit/             # Layer-2 pathfinding/helper tests (small test graphs)
    ├── contract/         # Layer-3 agent contract tests (Gemini mocked)
    └── integration/      # Layer-4 full-endpoint tests (Firestore mocked, real graph)
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
make test            # pytest with 100% coverage floor
make verify-graph    # Layer-1 graph data integrity
make verify-docs     # DECISIONS.md ↔ code sync

# Serve
make run             # uvicorn app.main:app --reload
```

Fan interface: <http://localhost:8080/static/fan.html>
Staff interface: <http://localhost:8080/static/staff.html>

## Staff access

Staff endpoints (`POST /staff/closures`, `GET /staff/closures`) require a shared bearer token. **The evaluator token is shared privately (not committed to this public repo) — see submission notes for the value.**

See SECURITY.md for the auth rationale and the production-hardening path.

## Technical notes

- **Graph is sourced, not measured.** Zone topology is derived from published MetLife venue maps (seating charts, ADA maps, concourse diagrams). Walk-time estimates are constructed from map distances, not observed. Every section maps to exactly one zone; `make verify-graph` enforces connectivity and accessibility-path existence.
- **The graph is a design boundary, not a TODO.** The same schema extends to any other World Cup venue.
- **Anonymous auth is intentional** — the CSP/auth pain of a full Google Sign-In flow is not worth the trade at evaluation scale. Documented limitation: closing the browser or clearing cookies loses the profile.
- **Coverage: 100% floor enforced in CI, actual achieved number reported here at submission.**

## What's out of scope (deliberate design boundaries)

- Wayfinding beyond the stadium interior (parking lot navigation is a known extension point, not built).
- Group-composition profile fields (group size doesn't change routes — dead code).
- Staff dashboards, heatmaps, volunteer assignment, crowd analytics (Entry #2 in DECISIONS.md).
- Vendor-level food detail (routing to nearest food zone, not to a specific pizza vendor).
- End-to-end tests against real Gemini or real Firestore (flakiness > value).

See DECISIONS.md Entry #17 and Entry #22 for future-enhancement extension points.

## License

MIT — see [LICENSE](LICENSE).