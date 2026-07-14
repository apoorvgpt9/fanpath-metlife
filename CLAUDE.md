# CLAUDE.md

Guidance for Claude Code when working in this repo. This file is a map to the
governing docs, not a replacement for them — when in doubt, read the source.

## Read these first, in this order

1. **DECISIONS.md** — locked architectural decisions. If code contradicts an
   active entry here, the code is wrong. Entries use a supersession pattern
   (new entry supersedes old, two-way linked) — never edit a decision in
   place.
2. **DESIGN.md** — locked frontend visual/interaction rules for
   `static/fan.html`, `static/staff.html`, and the route SVG. Same
   governance model as DECISIONS.md (numbered amendments, no in-place edits).
3. **PROGRESS.md** — rolling build log: phase status, the `make verify-docs`
   claim table, and the running log of what actually shipped. This file wins
   over the Notion tracker; DECISIONS.md wins over this file on architecture.
4. **SECURITY.md** — OWASP Top 10 walkthrough and documented, deliberate
   limitations (e.g. anonymous-auth session loss, single staff token).

**Session-exit rule (Entry #24):** no coding session ends without diffing
DECISIONS.md / PROGRESS.md against what actually got built. If you change
something that contradicts a locked entry, either don't, or add a proper
superseding entry and update PROGRESS.md's running log — don't leave the
docs stale.

## What this project is

PromptWars Challenge 4 — Smart Indoor Navigation for MetLife Stadium (FIFA
World Cup 2026). A fan-facing NL chat that resolves ambiguous location
descriptions and gives routed, accessibility-aware directions with a
server-rendered schematic SVG. A thin staff layer toggles node/edge closures.
Deadline: **July 19, 2026**. Live URL and repo are listed at the top of
PROGRESS.md.

The FastAPI app under `app/` implements the six endpoints, the two agents,
Dijkstra pathfinding, and the deterministic SVG renderer at
`app/rendering/svg_renderer.py` (Entry #12 — Gemini has no involvement in
SVG generation). The `static/` directory holds the entire frontend as flat
files — `fan.html` + `fan.js` for the fan chat, `staff.html` + `staff.js`
for the closure panel, `style.css` for the DESIGN.md-locked dark-mode
palette, and `firebase-config.js` for the public Firebase Auth web config.
`app/main.py` mounts this directory at `/static/` via `StaticFiles` — no
route handlers serve HTML (Entry #20).

## Non-negotiable architectural rules

These are the decisions most likely to matter for any change — see the
corresponding DECISIONS.md entry for full rationale before deviating.

- **Two agents, deterministic pathfinding between them** (Entry #9). Intent
  Agent → Dijkstra/A* on the graph → Guide Agent. **The model never invents
  a route.** Don't let an agent produce coordinates, node lists, or paths —
  that's the pathfinding layer's job only.
- **All agent outputs are discriminated unions**, never bare strings or
  optional fields standing in for state: `ResolvedRequest | AmbiguousRequest
  | UnresolvableRequest` (Intent), `RouteFound | RouteBlocked |
  RouteImpossible` (pathfinding). Preserve this pattern for any new agent
  output.
- **Graph is a static JSON file loaded at startup** (`data/metlife_graph.json`,
  36 nodes / 54 edges), not Firestore. Closures are Firestore *overrides* on
  top of the static graph, never modifications to the graph file itself.
- **`venue_state` is read fresh on every `/navigate` request** — no cache,
  no TTL, no real-time listener (Entry #16). Do not add caching here; it
  reintroduces the exact staleness bug this decision exists to prevent.
- **Auth is two separate mechanisms, don't cross them**: fan endpoints use
  Firebase Anonymous Auth (`app/auth/firebase.py`); staff endpoints
  (`POST/GET /staff/closures`) use a single shared `STAFF_TOKEN` env var
  (Entry #18). No per-staff identity, no `updated_by` — documented as
  deliberate, not a gap.
- **Conversation history is client-managed**, sent in every `POST /navigate`
  body (last 3 turns). No `conversations` collection, no session ID
  (Entry #10, #19).
- **Fan profile has exactly three fields**: `seat_section`,
  `accessibility_flags`, `preferred_language` (Entry #25, supersedes
  Entry #7). Don't add fields a feature doesn't consume.
- **Six endpoints only** (Entry #19): `POST/GET /profile`, `POST /navigate`,
  `POST/GET /staff/closures`, `GET /health`. SVG is returned inline as
  base64 in the `/navigate` response — no separate image-serving route.
- **Route rendering is deterministic** (Entry #12) — the renderer draws
  whatever pathfinding returns; Gemini has no involvement in SVG generation.
  Follow DESIGN.md's SVG rendering rules (node radii, colors, closed-edge
  dashing) exactly.
- **Frontend is static HTML + vanilla JS**, no templating engine, no
  frontend framework (Entry #20). No `TemplateResponse`, no Jinja2. Served
  via `StaticFiles`, not route handlers.
- **Error contract** (Entry #23): every error is
  `{type, category: "transient"|"permanent", message, detail}`. `detail` is
  populated only when `K_SERVICE` env var is absent (local dev); Cloud Run
  sets it automatically in production. `RouteBlocked` is a valid response,
  not an error.
- **Enums are fixed** — don't add values without a superseding DECISIONS.md
  entry: `AccessibilityFlag` (4), `PreferredLanguage` (5), `AmenityType` (6),
  `EdgeAccessibility` (4). See `app/models/enums.py`.
- **Gemini model strings**: Flash-tier is `gemini-3.5-flash`; Pro-tier (if
  pre-flight confirms) is `gemini-3.1-pro-preview` — a preview model, so
  check DECISIONS.md Entry #26 for the fallback plan if it becomes
  unavailable. Use the `gemini_factory.flash()` / `.pro()` pattern, not
  hardcoded model strings, for any new agent call.

## Code quality bar (enforced, not aspirational)

- **Coverage floor 95%**, target 98%+ (`--cov-fail-under=95` in
  `pyproject.toml`/Makefile). Don't drop below the floor; don't celebrate
  hitting exactly the floor.
- **ruff** with `C901`, `PLR0912`, `PLR0915` selected, `max-complexity = 10`.
  Keep functions simple and short — decompose rather than suppress.
- **Function-length cap: 80 lines**, enforced by
  `scripts/check_function_length.py` (AST-based). This exists specifically
  to catch the CarbonSaathi `log_activity` failure mode (a 199-line
  function that slipped through). Don't write a long function and plan to
  refactor later.
- **Commit messages must enumerate everything bundled in the commit.** A
  prior project buried an entire feature layer in a commit titled "style:
  black reformat" — don't repeat that.
- Run `make lint` and `make test` before considering a change done.
  `make verify-graph` after any graph data change. `make verify-docs` after
  any change touching a claim in PROGRESS.md's claim table.

## Testing layers (Entry #21)

1. `scripts/verify_graph.py` (`make verify-graph`) — graph data integrity:
   connectivity, section uniqueness, no orphans, enum conformance,
   non-empty `landmark_aliases` per node.
2. Pathfinding unit tests — small synthetic graphs (5-8 nodes), not the real
   MetLife graph. Fast, deterministic, tests the algorithm.
3. Agent contract tests — mock the Gemini API, verify structured output
   matches the discriminated union schema. At least one non-English Guide
   Agent test case.
4. Integration tests — full FastAPI test client requests against the real
   graph JSON, Firestore mocked at the client boundary.

No end-to-end tests against real Gemini or real Firestore — deliberate, per
Entry #21.

## `make verify-docs`

CI-enforced sync between DECISIONS.md claims and actual code (Entry #24,
Layer 2). The full claim table lives in PROGRESS.md. When you make a change
that affects a claim (new endpoint, enum value, auth mechanism, etc.), check
whether an existing claim needs its verification updated or a new claim
needs adding — don't let this table go stale silently.

## Common commands

```
make lint          # ruff + function-length check
make test           # pytest, 95% coverage floor
make verify-graph   # graph data integrity script
make verify-docs    # DECISIONS.md claim table vs. code
make run            # uvicorn --reload, port 8080
make deploy         # gcloud run deploy (asia-south1)
```

## When a decision needs to change

Don't edit DECISIONS.md or DESIGN.md entries in place. Add a new numbered
entry beginning `**Supersedes Entry #N**`, and append
`**Superseded by Entry #M**` to the old entry. Then log the change in
PROGRESS.md's running log and deviation tracker.
