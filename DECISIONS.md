# DECISIONS.md

Locked architectural decisions for **PromptWars Challenge 4 — Smart Indoor Navigation** (MetLife Stadium, FIFA World Cup 2026).

Every entry below was pressure-tested during the pre-build grilling session and is treated as fixed unless explicitly reopened via the supersession pattern in Entry #24. If code contradicts an active entry, the code is wrong.

---

## Rules for amending this file

**Supersession pattern (from Entry #24):**

- When a decision changes, **add a new entry** — do not edit the old one in place.
- New entry begins with `**Supersedes Entry #N**`.
- Old entry gets a one-line append: `**Superseded by Entry #M**`.
- Two-way linking so anyone reading either entry knows it's stale.

**Consistency enforcement — three layers (from Entry #24):**

1. **Discipline layer** — at every phase close, grep the codebase against active entries. Skippable under pressure; weakest layer.
2. **CI layer** — `make verify-docs` extracts verifiable claims from this file and greps the codebase. Fails the build on divergence. See Phase 0 for the exact claim set.
3. **Session-exit gate** — no advisory or coding session ends without a doc-diff pass. Doc review is a session-exit gate, not "whenever we feel like it."

---

## Entry #1 — Stadium: MetLife, real venue

**Status:** Active

**Decision:** MetLife Stadium (East Rutherford, NJ) — real venue, not fictional.

**Rationale:** Hosts the FIFA World Cup 2026 final, maximizing Problem Statement Alignment. Extensive public documentation (NFL seating charts, gate maps, ADA accessibility info) means the evaluator can sanity-check the graph against a real, well-known venue.

**Framing (in README and submission notes):** The graph topology is *derived from* published venue maps with *estimated* walking distances — sourced, not measured. No NFL or FIFA venue publishes a machine-readable node-edge graph. Extension to other World Cup venues via the same schema is a design boundary, not a TODO.

---

## Entry #2 — Primary user: fan, with thin staff layer

**Status:** Active

**Decision:** Fan is the primary persona. Staff have a thin, single-capability layer for closure management only.

**Rationale:** The problem statement lists "fans, organizers, volunteers, or on-ground staff" as *alternatives*, not a checklist. CarbonSaathi scored 97.02 with a single persona — depth on one persona beats breadth across four.

**Staff scope boundary:** Staff can toggle nodes and edges open/closed. That is the *only* staff capability. No analytics, no heatmaps, no volunteer management, no dashboards. If the evaluator asks about broader organizer tooling: closure management *is* the operations layer; the architecture extends there, and the extension point in the code will be pointed to.

**Dual-alignment rationale for the thin staff layer:** Closure toggling is what makes navigation *dynamic* and delivers the "Tournament Operations" half of the problem-statement title. Fan routes adapt to closures in real time. One capability, coverage of two alignment axes.

---

## Entry #3 — Staff capability: node/edge toggle only

**Status:** Active

**Decision:** Staff can toggle a node or edge in the graph as closed or open. That is the entire staff feature surface.

**Implementation:** Single Firestore document update against `venue_state`. No new agent pipeline, no analytics, no second product hiding inside a "thin layer."

**In scope:** Close Gate B (node). Close the escalator between Level 1 and Level 2 West (edge). Reopen a previously closed concourse section.

**Explicitly out of scope:** Staff dashboards showing route-request heatmaps, volunteer assignment suggestions, crowd density analytics. Each of these is a second product, not a feature.

---

## Entry #4 — GenAI differentiation: ambiguity resolution

**Status:** Active

**Decision:** The GenAI value is resolving ambiguity from natural-language fan queries — vague landmarks, embedded constraints, implicit destinations — that a dropdown or search bar cannot handle.

**Examples of queries that justify a language model:**

- "I'm near the big Pepsi sign on the upper level, where's the closest bathroom my wheelchair can reach" — vague landmark, no section number, embedded accessibility constraint.
- "We have four kids and my mother-in-law can't climb stairs, we want food before the match starts in 20 minutes" — accessibility, amenity type, time pressure, no explicit destination (system must *recommend*, not just route).
- "How do I get back to my car in Lot K" — navigation extending beyond the stadium interior.

**Anti-pattern:** If the fan types "how do I get to Section 128" and Gemini's only job is to extract "Section 128," that is a regex with extra steps, not a GenAI application. The model must do something a deterministic system cannot.

**Output format:** Text-first natural-language directions plus a server-side rendered Level 2 schematic SVG/PNG showing the route highlighted on a simplified stadium diagram. Not an interactive map, not a frontend mapping library.

---

## Entry #5 — Location resolution: NL primary, dropdown fallback

**Status:** Active

**Decision:** Natural-language location resolution is primary. Deterministic dropdown is the fallback for the unresolvable case.

**Mechanism (candidate-set cardinality, not confidence scores):**

- Fan describes location in NL ("I'm near Gate C" / "I just came up the escalator by the Budweiser stand").
- Intent Agent resolves the description against known graph nodes and landmark aliases.
- Output is a discriminated union:
  - **Single match** → proceed with routing.
  - **Ambiguous match** (multiple plausible nodes) → Gemini asks a clarifying question with specific options.
  - **Unresolvable** (no landmarks match) → fall back to a deterministic dropdown / zone list.

**Anti-pattern rejected during grilling:** "Confidence score" phrasing. Gemini does not return a calibrated confidence number with structured output. The mechanism is candidate-set cardinality (one / many / zero matches), implemented as a discriminated union — same pattern as CarbonSaathi's Logger (`Success | Rejected | Failed`).

**QR-code option (also rejected):** Untestable by the evaluator since they are not physically at MetLife. Dead on arrival.

---

## Entry #6 — Authentication: Firebase Anonymous only

**Status:** Active

**Decision:** Firebase Anonymous Auth. No Google Sign-In, no email — device-level anonymous UID only.

**Rationale:** Avoids the CSP/auth pain CarbonSaathi hit with Google Sign-In (Bug 1 — `apis.google.com` CSP block that burned real debugging time). The onboarding interaction itself becomes a GenAI showcase (NL → structured profile extraction, same Logger pattern).

**Stated limitation (surfaced in README and SECURITY.md, not hidden):** Anonymous UIDs are device-bound and non-recoverable. Closing the browser, clearing cookies, or switching devices mid-match loses the profile. Wrong call for a production stadium product; right call for a scored challenge where the evaluator tests for 10-15 minutes and session loss will not surface. Documented deliberately as a known limitation, not a gap.

---

## Entry #7 — Fan profile fields (SUPERSEDED)

**Status:** **Superseded by Entry #25** — third profile field (`preferred_language`) added for multi-language support.

**Original decision:** Two fields — `seat_section` and `accessibility_flags`.

**Original rationale (still valid for these two fields):**

- `seat_section` — string, maps to a zone node. Used for "take me back to my seat" queries.
- `accessibility_flags` — set of flags from a fixed enum: `wheelchair | no_stairs | stroller | visual_impairment` (empty list if none). Filters edges during Dijkstra.

**Dropped: group composition.** Group size doesn't change the route or the recommendation. "Four people" and "one person" get the same path. The only group attribute that affects routing is accessibility, already covered by the flags. A profile field that never gets consumed is dead code.

**Onboarding flow (still active):** Single NL prompt ("I'm in Section 214, my mother uses a wheelchair"). Intent Agent extracts fields. Discriminated union output: `ProfileComplete | ProfileIncomplete | ProfileFailed`. If incomplete (seat given, accessibility not), the system does NOT ask a follow-up — it silently defaults to no accessibility constraints.

**Corrective safety mechanism (during routing, not onboarding — still active):** If the computed route traverses a `stairs_only` edge and the fan's profile has no accessibility flags, the Guide Agent appends: "This route includes stairs. Need a step-free alternative?" This is a deterministic check on the route output, not a Gemini call. Zero additional API cost. Catches the failure mode where a fan with a wheelchair didn't mention it during onboarding, at the exact moment it matters.

---

## Entry #8 — Graph: zone-level, 35-45 nodes

**Status:** Active

**Decision:** Zone-level nodes, approximately 35-45 total.

**Node semantics:** A navigable zone — a logical grouping of adjacent sections, a gate, a concourse junction, or an amenity cluster. NOT individual sections (~82 numbered sections — too granular). NOT gate-level only (~10-12 nodes — too coarse).

**Node metadata:** List of specific sections it contains (so "Section 128" resolves to the zone containing it), amenity availability (see Entry #11), and `x, y` coordinates for schematic rendering (approximate positions on a simplified stadium outline, not geographically precise).

**Edge semantics:** A walkable connection between two zones. Each edge carries:

- **Walk-time estimate in minutes** — constructed from map distances, not measured.
- **Accessibility classification** — enum: `stairs_only | ramp | elevator | level`. This is the field Dijkstra filters on when the fan has accessibility flags.

**Staff closure toggling operates on edges (e.g. escalator) or nodes (e.g. concourse section).**

**Storage:** Static JSON file loaded at startup. NOT in Firestore. Same pattern as CarbonSaathi's emission factor JSONs. Closures are stored in Firestore as overrides, not as modifications to the graph file.

---

## Entry #9 — Agent architecture: two agents + deterministic pathfinding

**Status:** Active (amended by Entry #25 — Guide Agent multi-language scope confirmed IN)

**Decision:** Two agents with deterministic pathfinding between them. Not three.

**Intent Agent (replaces CarbonSaathi's Logger):**

- **Input:** Fan's NL query + fan profile (seat, accessibility flags, preferred language) + last 3 conversation turns.
- **Job:** Parse into a structured navigation request — origin node (resolved/ambiguous/unresolvable), destination node or amenity type, constraints.
- **Output (discriminated union):** `ResolvedRequest | AmbiguousRequest | UnresolvableRequest`.

**Deterministic pathfinding (between the agents, inside neither):**

- Dijkstra / A\* on the graph.
- Filters edges by accessibility constraints from the profile.
- Respects staff closure overrides (closed nodes/edges excluded before pathfinding runs).
- Output: ordered list of zone nodes with cumulative walk times.
- **The model never invents a route.** Same principle as CarbonSaathi's "Coach computes the saving, never trusts the model."

**Guide Agent (replaces CarbonSaathi's Coach):**

- **Input:** Computed route (deterministic output — ordered node list with walk times), fan's original query, fan's profile.
- **Job:** Produce natural-language turn-by-turn directions. Include the stairs-warning safety check if the route traverses `stairs_only` edges and the profile has no accessibility flags.
- **Output:** Text directions in the fan's `preferred_language` (see Entry #25) + triggers deterministic SVG route rendering.

**No Analyst equivalent.** CarbonSaathi needed Analyst because there was historical data to aggregate. Navigation is stateless per query — no "your navigation history" analytics. Extension point exists if added later; not built now.

---

## Entry #10 — Conversation memory: short-window multi-turn

**Status:** Active

**Decision:** Short-memory multi-turn. Rolling window of the last 3 turns, hard cap.

**Why multi-turn is necessary (unlike CarbonSaathi):**

- Turn 1: "I'm near Gate C, need food" → nearest food zone.
- Turn 2: "Actually, somewhere closer to my seat" → must remember origin, constraint, and know the fan's seat.
- Turn 3: "How do I get back to my seat from there?" — "there" refers to the food zone from Turn 2.

**Implementation:** Last 3 turns kept in the Gemini context window. Fan profile (seat, accessibility, language) injected as system context on every request — static, small, ~50 tokens, separate from rolling history.

**Cost control:** 3-turn cap prevents context growth. Per-request context overhead is bounded and predictable.

**Storage:** Conversation history is **client-managed** — sent in every `POST /navigate` request body. No `conversations` collection in Firestore, no session ID.

---

## Entry #11 — Amenities: metadata on zones, six-value enum

**Status:** Active

**Decision:** Amenities as metadata on zone nodes, not as their own nodes. Six amenity types as a fixed enum.

**Enum:** `restroom | food | merchandise | atm | first_aid | charging_station`

**Why metadata, not nodes:** Keeps the graph at 35-45 nodes. Fans don't need turn-by-turn to a specific restroom stall — they need to reach the right zone, and signage handles the last 20 meters. Same pattern as CarbonSaathi's emission factors: static reference data attached to a structural entity.

**Zone metadata schema example:**

```json
{
  "zone_id": "lower_west_concourse_a",
  "sections": ["111", "112", "113", "114"],
  "amenities": {
    "restroom": true,
    "food": true,
    "merchandise": false,
    "atm": true,
    "first_aid": false,
    "charging_station": false
  }
}
```

**Food sub-categories dropped.** No vendor-level detail (pizza, burgers, etc.). "Where's food" routes to the nearest zone with `food: true`. Avoids sourcing vendor data that could be wrong by match day.

**Why `first_aid` and `charging_station` were kept (initially proposed for cutting):** `first_aid` has genuine urgency — accessibility and speed matter most there. Strong PS Alignment on the safety dimension. `charging_station` addresses a real, common stadium problem. Each is one more enum value — zero engineering cost.

---

## Entry #12 — Route rendering: Level 2 schematic, deterministic

**Status:** Active

**Decision:** Level 2 schematic floor plan. Deterministic rendering. No Gemini involvement.

**Three levels considered:**

- **Level 1 (rejected):** Abstract graph — circles and lines. Looks like CS homework.
- **Level 2 (selected):** Schematic floor plan — nodes positioned to roughly correspond to real locations on a simplified stadium outline. Route highlighted as a colored path. Not geographically accurate, but visually clear.
- **Level 3 (rejected):** Overlay on actual floor plan image. Requires licensing, pixel-accurate coordinate mapping, multi-floor handling. Significant manual effort for zero GenAI score.

**Rendering stack:** Node `x, y` coordinates live in the graph JSON alongside topology. Stadium outline is a static SVG shape drawn once. matplotlib or plain SVG generation on the backend draws lines between route nodes' coordinates, highlighted against the outline. Estimated 40-60 lines of rendering code, well under complexity lint thresholds.

**The renderer is deterministic.** Pathfinding returns an ordered node list → renderer draws the path. Model never draws the route, model never invents the route.

---

## Entry #13 — Tech stack (amended by Entry #25 for multi-language)

**Status:** Active — with the `preferred_language` field addition documented in Entry #25.

**Decision:** Identical stack to CarbonSaathi. Deviations only on data shape and operational discipline.

| Layer            | Decision                                            | Change from CarbonSaathi?                        |
| ---------------- | --------------------------------------------------- | ------------------------------------------------ |
| Web framework    | FastAPI                                             | No change                                        |
| Database         | Firestore                                           | No (but different data shape — see below)        |
| AI models        | Gemini 2.5 Flash (both agents at start)             | Changed — see model tier strategy                |
| Deployment       | Cloud Run                                           | No change                                        |
| Auth             | Firebase Anonymous Auth                             | Changed — anonymous only, no Google Sign-In      |
| Static data      | Graph JSON + amenity metadata loaded at startup     | Same pattern as emission factor JSONs            |
| Rendering        | Server-side SVG/PNG via matplotlib or raw SVG       | New — CarbonSaathi had no image output           |
| CI/CD            | GitHub Actions + Makefile                           | No change                                        |
| Coverage         | `--cov-fail-under=95`                               | No change                                        |
| Linting          | ruff with `C901`, `PLR0912`, `PLR0915` added        | **New — the Code Quality lever**                 |

**Firestore data shape (different from CarbonSaathi):**

- `fans` — keyed by anonymous UID; three fields per session (seat, accessibility flags, preferred language). Updated per Entry #25.
- `venue_state` — single document holding closed nodes and edges. Updated rarely, read on every navigation request.
- Graph JSON is NOT in Firestore — static, loaded at startup.

**Model tier strategy:**

- Both agents start on Flash.
- Phase 3 includes a mandatory pre-flight step: verify Pro billing/quota with a live API call.
- If Pro is confirmed working, upgrade Intent Agent to Pro (harder NLU task — landmark resolution, implicit constraint detection). Guide Agent stays on Flash (easier task — structured route in, prose out).
- Factory pattern carried over: `gemini_factory.flash()` / `.pro()`. Switching is a one-line change.
- **Lesson from CarbonSaathi Bug 3:** verify before building phases around an assumption.

**Code Quality lever (new for Challenge 4):**

- `C901` (McCabe complexity), `max-complexity = 10` in `pyproject.toml`.
- `PLR0912` (too-many-branches), `PLR0915` (too-many-statements) added to ruff's `select`.
- Function-length check via a small AST-based Python script (see Phase 0) — catches the exact `log_activity` (199 lines) failure mode from CarbonSaathi.
- All of the above lands in `pyproject.toml` and `scripts/` in Phase 0, before any application code exists.

---

## Entry #14 — Graph construction: hybrid Gemini draft + manual correction + validation script

**Status:** Active

**Decision:** Option C — hybrid with a verification script. Graph construction blocks all downstream features.

**Approach:**

1. Use Gemini to propose an initial zone decomposition from public MetLife venue maps (seating charts, concourse diagrams, ADA maps). Gemini drafts the JSON.
2. Manual review and correction — Gemini will hallucinate zone boundaries and invent amenities. The draft is a starting point, not a deliverable.
3. Write a validation script (connectivity, walk-time bounds, section-to-zone uniqueness, no orphan nodes, accessibility paths exist between all node pairs). The script guarantees internal consistency, not external correctness — it catches dead ends and unreachable zones, not wrong walk-time estimates.

**The validation script is a Code Quality signal** — engineering discipline around data integrity, same role `verify_emission_data.py` played in CarbonSaathi.

**Dependency structure:**

Parallelizable with graph construction (no graph dependency):

- `pyproject.toml` with all lint rules, coverage floor, dependencies
- FastAPI skeleton, health check, CORS, security headers, `redirect_slashes=False`
- Firebase Anonymous Auth flow
- Firestore schema for fan profiles
- CI/CD pipeline (GitHub Actions, Makefile targets)
- DECISIONS.md, PROGRESS.md, README skeleton

Blocked until graph exists:

- Pathfinding engine (needs real nodes and edges)
- Intent Agent (needs node list and landmark aliases)
- Guide Agent (needs route output format)
- Closure toggling (needs node/edge IDs)
- SVG renderer (needs node x/y coordinates)
- Every integration test

---

## Entry #15 — Firestore schema: two collections, single closure doc

**Status:** Active — reflects Entry #25 addition of `preferred_language`.

**Collection 1: `fans`** — keyed by anonymous UID.

```json
{
  "seat_section": "214",
  "accessibility_flags": ["wheelchair", "no_stairs"],
  "preferred_language": "es",
  "created_at": "2026-07-08T12:00:00Z"
}
```

Fields:

- `seat_section` — string, maps to a zone via graph metadata.
- `accessibility_flags` — list of strings from `wheelchair | no_stairs | stroller | visual_impairment` (empty list if none).
- `preferred_language` — string, one of `en | es | fr | pt | ar`, default `en`.
- `created_at` — timestamp.

**What does NOT belong here:** conversation history (in-memory, client-managed, never persisted), navigation history (out of scope), any field no feature consumes.

**Collection 2: `venue_state`** — single document.

```json
{
  "closed_nodes": ["gate_b"],
  "closed_edges": ["edge_lower_west_to_upper_west_stairs"],
  "updated_at": "2026-07-08T14:30:00Z"
}
```

Staff toggle updates the arrays. One Firestore read per navigation request to get the full closure state. Concurrent-edit risk is negligible at MVP scale (one evaluator). Documented in SECURITY.md as a known scaling limitation.

**Why single document, not one-per-closure:** One fetch vs. a collection query. Simpler to read, simpler to implement. The tradeoff doesn't materialize at evaluation scale.

---

## Entry #16 — Closure freshness: read on every request, no cache

**Status:** Active

**Decision:** Option A — read `venue_state` from Firestore on every navigation request. No cache, no TTL, no real-time listener.

**Mechanism:** Fan asks for a route → fetch `venue_state` → remove closed nodes/edges from an in-memory copy of the graph → run Dijkstra on the filtered graph. Zero staleness window.

**Why not cached with TTL:** Re-creates the exact staleness bug pattern from CarbonSaathi Bug 4 — staff close an escalator, fans get routed through it for up to N seconds. The staleness-detection system in CarbonSaathi existed to fix this class of bug. Do not reintroduce it.

**Why not a real-time Firestore listener:** Cloud Run containers are stateless, killable, cold-startable. A listener assumes a long-lived process and has an unknown-state window between cold-start and first snapshot. Adds lifecycle complexity for zero benefit at evaluation scale.

**Cost at evaluation scale:** One document fetch per navigation request. Firestore serves single-document reads in single-digit milliseconds. Negligible.

**Production note (in SECURITY.md):** At stadium scale (80,000 concurrent fans), per-request reads would need short-TTL caching or a real-time listener. Documented as a scaling consideration, not built now.

---

## Entry #17 — No-route case: text failure with explanation

**Status:** Active

**Decision:** Option B — failure with explanation and offer to relax constraints. Text only, no SVG for blocked routes.

**Pathfinding returns a discriminated union:** `RouteFound | RouteBlocked | RouteImpossible`.

- `RouteFound` — ordered node list with cumulative walk times → passed to Guide Agent + SVG renderer.
- `RouteBlocked` — carries the blocking reason (which specific closure, or which missing accessibility edge). Guide Agent turns this into a human-readable explanation: "There's no step-free route to Section 214 right now — the elevator near Gate D is currently closed. If stairs are an option, I can route you that way." No SVG generated.
- `RouteImpossible` — no path exists even without closures. Shouldn't happen in a well-formed graph (Entry #14 validation script checks connectivity), but handled defensively.

**Option C (nearest reachable alternative) documented as future enhancement.** Would require a second Dijkstra pass from the destination outward — ~10 lines of code on this graph size, but deferred to avoid scope creep. Extension point: when `RouteBlocked` is returned, optionally run `find_nearest_reachable(destination, constraints)` before passing to Guide Agent.

---

## Entry #18 — Staff auth: single shared token

**Status:** Active

**Decision:** Single shared token. `STAFF_TOKEN` environment variable, checked by a FastAPI `Depends` function.

**Implementation:** ~10 lines. One `Depends` callable that reads the `Authorization: Bearer <token>` header and compares against `os.environ["STAFF_TOKEN"]`. Applied to `POST /staff/closures` and `GET /staff/closures`. Fan endpoints use Firebase Anonymous Auth, not this mechanism.

**Why one token, not ten:** Ten hardcoded tokens give the *appearance* of per-staff identity without any actual benefit. No user record, no name mapping, no audit trail. One token prevents unauthenticated access (the actual threat model). Ten add configuration surface with zero additional security or accountability.

**The `venue_state` document has `updated_at` but no `updated_by`** — without real identity, fake attribution is worse than none.

**README tells the evaluator the staff access code.** SECURITY.md documents: "Shared-secret access control; production would use role-based auth via Firebase custom claims with per-staff identity."

---

## Entry #19 — API surface: six endpoints, pure JSON, client-managed history

**Status:** Active

**Fan endpoints (Firebase Anonymous Auth):**

- `POST /profile` — onboarding. Fan sends NL. Intent Agent extracts seat + accessibility + language. Returns structured profile.
- `GET /profile` — retrieve current fan profile.
- `POST /navigate` — core feature. Fan sends NL query + last 3 conversation turns in the request body. Intent Agent parses, pathfinding runs, Guide Agent explains. Returns JSON with text directions + base64-encoded SVG route image.

**Staff endpoints (STAFF_TOKEN):**

- `POST /staff/closures` — toggle a node or edge closed/open. Body: `{target_id, target_type: "node" | "edge", action: "close" | "open"}`.
- `GET /staff/closures` — view current closure state.

**System endpoints (no auth):**

- `GET /health` — Cloud Run health probe.

**Design decisions embedded in this surface:**

- **Conversation history is client-managed.** Rolling 3-turn window sent in every `POST /navigate` request body. Server is stateless — no `conversations` collection, no session ID. CarbonSaathi was similarly stateless per agent call.
- **SVG is inline, not a separate URL.** `POST /navigate` response: `{directions: "...", route_image: "data:image/svg+xml;base64,..."}`. One request, one response. No second round trip, no file-serving endpoint.

---

## Entry #20 — Frontend: static HTML + vanilla JS

**Status:** Active

**Decision:** Option C — static HTML + vanilla JS. Pure JSON API backend. No Jinja2, no templating engine.

**Why Option C over Option A (Jinja2, same as CarbonSaathi):** The evaluator scores Python code quality. A pure JSON API means every FastAPI route returns structured data — no `TemplateResponse`, no rendering context dictionaries, no Jinja2 dependency. Clean single-responsibility. The frontend is static files in `/static`, decoupled. Backend testable with `pytest` + `httpx` hitting JSON endpoints without HTML parsing.

**Frontend files:**

- `static/fan.html` — chat interface (input, scrolling message list, image element for SVG). `fetch('/navigate')`, append response text, set image src to base64 SVG. Estimated ~60-70 lines of JS.
- `static/staff.html` — closure toggle panel. `fetch('/staff/closures')` to load state, `fetch('/staff/closures', {method: 'POST'})` to toggle. Estimated ~40-50 lines of JS.

**Serving:** `app.mount("/static", StaticFiles(directory="static"))`. Fan at `/static/fan.html`, staff at `/static/staff.html`. No route handlers for serving pages. No template engine in dependencies.

**Accessibility proxy (per Evaluator Insights):** Sprinkle aria labels and alt text on both HTML files. Near-zero cost, satisfies the Accessibility proxy.

---

## Entry #21 — Testing: four layers, 95% coverage floor

**Status:** Active

**Decision:** Four testing layers. Coverage floor enforced at 95% via Makefile, target 98%+ in practice.

**Layer 1 — Graph validation (standalone script, not pytest):** The Entry #14 verification script. Runs as `make verify-graph`. Data-integrity equivalent of CarbonSaathi's `verify_emission_data.py`.

**Layer 2 — Pathfinding unit tests (highest value, most cases):** Small test graphs (5-8 nodes), NOT the real MetLife graph — fast, deterministic, test the algorithm not the data. Cases: shortest path, accessible-only path, path with closures, `RouteBlocked`, `RouteImpossible`. Discriminated union output contract verified here. These are deterministic and cheap — high coverage with minimal effort.

**Layer 3 — Agent contract tests:** Same pattern as CarbonSaathi's Logger/Coach tests. Mock the Gemini API, verify Intent Agent's structured output matches the discriminated union schema for known input patterns. Verify Guide Agent produces text containing expected landmarks given a known route. Test the prompt contract, not Gemini itself. At least one non-English Guide test (Entry #25).

**Layer 4 — Integration tests:** Full request through FastAPI's test client — `POST /navigate` with an NL query, verify response contains both text directions and a base64 SVG string. Firestore mocked at the client boundary. Graph is the real MetLife JSON — this is where graph data errors surface if Layer 1 missed them.

**Not built:** End-to-end tests calling real Gemini or real Firestore. CarbonSaathi didn't have them. Flakiness and cost without proportional value.

**Coverage strategy:** 95% is the safety net (CI fails below it). 98%+ is the target. The achieved number goes in the README, not the floor. CarbonSaathi enforced 95%, achieved 99.66%. Same pattern.

---

## Entry #22 — SVG rendering: two must-haves, two deferred

**Status:** Active

**Must-have — Case 1 (baseline route):** Origin and destination with intermediate nodes. Highlighted path on the stadium schematic. Origin and destination visually distinct from intermediate nodes. All nodes shown in neutral color as the base schematic.

**Must-have — Case 2 (closures in base schematic):** Closed nodes/edges rendered with a red indicator (dot, dashed line, or X) as part of the base schematic — always shown, not route-specific. Every SVG reflects the current closure state regardless of route. This lives in the base schematic renderer, not the route renderer — one place, always applied. Cost: ~3-4 lines in the edge/node rendering loop.

**Deferred — Case 3 (RouteBlocked, no valid path):** No SVG generated. Text explanation only (per Entry #17). Future enhancement: show origin, destination, and blocking closure with no path drawn.

**Deferred — Case 4 (amenity multi-marker):** SVG highlights only the route to the nearest matching amenity. Does not mark all zones with that amenity type. Future enhancement: show all matching zones so the fan can see alternatives.

---

## Entry #23 — Error contract: two categories, K_SERVICE-based detail

**Status:** Active

**Response schema (every error, every endpoint):**

```json
{
  "type": "error",
  "category": "transient | permanent",
  "message": "Fan-friendly string",
  "detail": "Raw traceback or null"
}
```

**Category mapping:**

- Gemini timeout / 500 → `transient` ("Something went wrong, please try again")
- Unresolvable location → `permanent` ("I couldn't identify that location — try describing a nearby gate or section")
- Profile not found → `permanent` ("Please set up your profile first")
- Firestore read failure → `transient`
- `RouteBlocked` → **NOT an error** — valid response handled by the Guide Agent, not the error contract
- SVG rendering failure → `transient` — serve text directions without the image rather than failing the whole request

**Environment-based detail toggling:** Cloud Run sets `K_SERVICE` automatically on every deployed container. `K_SERVICE` present → production → `detail` is `null`, fan sees friendly message only. `K_SERVICE` absent → local development → `detail` contains the raw traceback for debugging. Zero configuration, zero chance of forgetting to flip a `DEBUG` flag before submission.

**Raw errors always logged regardless of environment.** Cloud Run captures stdout/stderr into Cloud Logging. Fan gets a friendly message, developer gets the real traceback in logs.

---

## Entry #24 — DECISIONS.md governance: supersession + three-layer sync

**Status:** Active

**Structural change from CarbonSaathi:** CarbonSaathi's DECISIONS.md §15 was append-only during live coding, never reviewed for internal consistency. Entry #17 contradicted entry #31. Entries #18-#30 were missing entirely. The governance document was less reliable than the Notion page describing it.

**Change 1 — Supersession, not contradiction:** When a decision changes, the new entry explicitly marks the old one as superseded. Two-way linking. Cost: ten seconds per amendment.

**Change 2 — Pre-seeded baseline:** DECISIONS.md starts on day one with all 25 decisions from the grilling session as initial entries, already numbered. Amendments during the build reference and supersede these entries rather than starting from scratch.

**Change 3 — Three-layer doc-code sync mechanism:**

- **Layer 1 (lightest — discipline-based):** Per-phase review step baked into session handoff. At the end of every coding phase, before the next starts: read DECISIONS.md, grep the codebase for any contradicted/superseded decision, update the file. Skippable under pressure.
- **Layer 2 (enforced — CI-based):** `make verify-docs` Makefile target. A script that extracts verifiable claims from DECISIONS.md and greps the codebase to confirm they match. Runs in CI — fails the build if docs and code diverge on checkable facts. **Concrete claim set is defined in Phase 0 of PROGRESS.md.** Limited scope (can't check architectural rationale, only concrete facts).
- **Layer 3 (session rule):** When working with Copilot or in advisory sessions, the session doesn't end until markdown files have been diffed against the work done in that session. Doc review is a session-exit gate.

---

## Entry #25 — Multi-language: in scope, five languages

**Status:** Active. **Supersedes Entry #7** (fan profile now has three fields, not two). **Amends Entry #9** (Guide Agent output language is `preferred_language`; earlier "not in scope" note is superseded). **Amends Entry #13** (fan profile row in the tech stack table reflects three fields).

**Languages supported:** English (`en`), Spanish (`es`), French (`fr`), Portuguese (`pt`), Arabic (`ar`).

**Rationale for these five:** English is default. Spanish, French, Portuguese cover the three host countries (US has a large Spanish-speaking population; Canada has French; multiple World Cup qualifying nations speak Portuguese). Arabic covers high-representation World Cup fan bases.

**Implementation — near-zero engineering cost:**

- Fan profile gets a third field: `preferred_language` (enum, default `en`).
- Guide Agent's system instruction includes: "Respond in {language}." Gemini handles translation natively.
- Onboarding prompt extraction adds language detection or explicit statement ("I speak Spanish" or detected from the fan's input language).
- ~2-3 lines of code change in the Guide Agent's system instruction template.

**Testing requirement:** At least one non-English test case per Guide Agent test scenario. Not comprehensive translation validation — just verifying the response is in the requested language and contains expected landmark names.

**PS Alignment boost:** Multi-language was one of the four tracks listed in the problem statement. Implementing it as a thin layer on top of the primary track (navigation) gives partial alignment coverage across two tracks, not just one, for near-zero cost.

---

## Entry #26 — Gemini model strings updated: 2.5 → 3.5/3.1 (supersedes model names in Entry #13)

**Status:** Active. **Supersedes the model-name specifics in Entry #13** — the Flash/Pro tier *strategy* in Entry #13 is unchanged and remains active; only the literal model strings are superseded here.

**Trigger:** `gemini-2.5-flash` returned `404 NOT_FOUND` — "This model models/gemini-2.5-flash is no longer available to new users" — when pre-flight tested against the newly created GCP project on July 13, 2026. Confirmed via Google's own docs: Gemini 2.0 Flash and Flash-Lite were shut down June 1, 2026; Gemini 3.5 Flash reached GA in May 2026 and is now the model behind the `gemini-flash-latest` alias.

**Decision:**

- Flash-tier agent calls use **`gemini-3.5-flash`** (GA/stable). Verified working via a live `generateContent` call, 200 response, July 13, 2026.
- Pro-tier agent calls (if the Phase 3 pre-flight confirms availability) use **`gemini-3.1-pro-preview`**. Verified working via a live `generateContent` call, 200 response, July 13, 2026.
- **API surface stays on the legacy `generateContent` endpoint**, not the newly-GA'd Interactions API. `generateContent` remains fully supported "for the foreseeable future" per Google's own migration guidance; adopting an unfamiliar API surface mid-build under a compressed deadline is an unnecessary risk. Revisit only if `generateContent` is deprecated before submission (not expected in this window).

**Stated risk (new, not present when Entry #13 was written):** `gemini-3.1-pro-preview` is a **preview**, not GA, model. Preview models are deprecated with at least 2 weeks' notice; short-term-availability models can retire as soon as 45 days after a replacement ships. This is a real, currently low-probability, risk inside the July 19 window.

**Fallback if `gemini-3.1-pro-preview` becomes unavailable mid-build:** both agents drop to `gemini-3.5-flash`. The `gemini_factory.flash()` / `.pro()` pattern (Entry #13) makes this a one-line change per agent — no architecture change required. Document the fallback trigger, if used, as a further amendment.

**`make verify-docs` impact:** none. PROGRESS.md claim #17 checks that *a* model-tier decision is documented and that code matches it — it does not hardcode a model string, so it remains valid as written.

---

## Entry #27 — Phase 1a hard cap: 3 hours, predetermined fallback graph (amends Entry #14)

**Status:** Active. **Amends Entry #14** — the graph construction approach is unchanged; this entry adds a time-box and a predetermined fallback that Entry #14 did not specify.

**Trigger:** Timeline compression — as of July 13, 2026, 6 build days remain before the July 19 deadline (down from the original 10-day window), with zero days of Phase 0 yet complete. Phase 1a (graph construction) is explicitly the least-predictable, highest-blocking task in the Phase Plan; an open-ended correction pass is no longer affordable.

**Decision:** Phase 1a (Gemini draft → manual correction → `metlife_graph.json`) is hard-capped at **3 hours of wall-clock time**, starting from when Gemini's first draft is produced.

**Predetermined fallback (decided now, not improvised under pressure):** If the graph does not pass `make verify-graph` within the 3-hour cap, ship a coarser graph instead of continuing to correct the original:

- **~20-25 nodes** instead of 35-45.
- **Gate + concourse level only** — drop zone-within-level subdivision (e.g., collapse `lower_west_concourse_a` / `_b` / `_c` into a single `lower_west_concourse` node).
- All six amenity types and the four accessibility edge classifications are still mandatory on the coarser graph — those are cheap regardless of node count and everything downstream depends on them.
- Document the reduced fidelity as a one-line append to this entry and in the README's "Technical notes" section, framed honestly as a deliberate scope cut under time pressure, not hidden.

**Why this is an acceptable trade:** Per the Evaluator Insights analysis, Code Quality is the only gradient-scored criterion; PS Alignment (which graph fidelity feeds) is already near-ceiling for well-documented submissions regardless of node count. A working 20-25 node graph that unblocks Phases 2-4 on schedule is worth more than a stalled 35-45 node graph that blows the whole build.

**Outcome (fill in after Phase 1a closes):** _(pending)_

---

## Carryover lessons from CarbonSaathi (verified against repo, not assumed)

**Carry forward (confirmed effective):**

- Session governance: DECISIONS.md (locked spec) + PROGRESS.md (rolling state) + per-session handoff.
- Discriminated union pattern for all agent outputs (`Success | Ambiguous | Failed`, never bare strings).
- Deterministic computation between agents — the model never invents the number/route.
- Coverage floor at 95% enforced via Makefile from commit one.
- `redirect_slashes=False` + slashless routes.
- `--no-server-header` in Dockerfile.
- `_iso_z()` timestamp helper for Firestore range queries.
- Rate limiting on all endpoints from the start.
- SECURITY.md with OWASP Top 10 walkthrough.

**Carry forward with corrections:**

- DECISIONS.md amendments must be internally consistent (Entry #24 mechanism).
- Commit messages must accurately describe what the commit contains. CarbonSaathi's Phase 3 (entire emission-factor layer) was buried in a commit titled "style: black reformat" — a reviewer skimming commit history gets zero signal. Every commit message enumerates what's bundled.
- Model tier verified live before building phases around it (Phase 3 pre-flight step).
- Function length/complexity lint from day one — the exact gap that likely caused CarbonSaathi's 89/100 Code Quality score.

**Do not carry forward:**

- Local-only git SPOF. Push to origin after every commit session.
- The "hope I implemented everything" pattern. Every fix gets verified with a grep/read, not restated from memory.