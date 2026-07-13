# PROGRESS.md

Rolling build state for **PromptWars Challenge 4 — Smart Indoor Navigation**.

DECISIONS.md is the constitutional spec. This file is the running log of what actually got built and validated. When they drift, this file wins over the Notion Progress Tracker (which mirrors this file), and DECISIONS.md wins over this file on architectural claims.

**Deadline:** July 19, 2026.

**Live URL:** <https://fanpath-metlife-973486326780.asia-south1.run.app>

**Repo:** <https://github.com/apoorvgpt9/fanpath-metlife>

---

## Phase status

| Phase | Description                                          | Status              | Machine validation | Intent validation | Notes                                             |
| ----- | ---------------------------------------------------- | ------------------- | ------------------ | ----------------- | ------------------------------------------------- |
| 0     | Skeleton, config, Day-1 deploy                       | DONE                | 2026-07-13         | 2026-07-13        | Live URL green; commit c81776d; intent validation passed with 3 non-blocking notes |
| 1     | Graph (blocker) + auth + schema                      | DONE                | 2026-07-13         | 2026-07-13         | 36 nodes, 54 edges (post-patch); intent validation passed for main build + patch; 11 PASS/9 SKIP/0 FAIL |
| 2     | Pathfinding + Layer-2 tests                          | MACHINE-VALIDATED | 2026-07-13         | —                 | 19 pathfinding tests; engine 99%, loader 100%; 12 PASS/8 SKIP/0 FAIL |
| 3     | Intent + Guide agents + Gemini pre-flight            | NOT STARTED  | —                  | —                 | Pre-flight before agent logic                     |
| 4     | Endpoints + frontend + renderer + closures           | NOT STARTED  | —                  | —                 | Full app on live URL                              |
| 5     | Presentation pass                                    | NOT STARTED  | —                  | —                 | Cheap-signal proxies                              |
| 6     | Final gauntlet + submit                              | NOT STARTED  | —                  | —                 | No new features; submit once                      |

**Status values:** `NOT STARTED` / `IN PROGRESS` / `MACHINE-VALIDATED` / `INTENT-VALIDATED` / `DONE`.

---

## Revised schedule (as of July 13, 2026 — compressed from 10 days to 6 build days + submission day)

**Why this changed:** the original Phase Plan assumed a 10-day window at 2-3 hrs/day starting ~July 8. As of July 13, Phase 0 has not yet closed and only 6 build days remain before the July 19 deadline. Working capacity increased to 4-5 hrs/day to compensate, giving ~24-30 hours against ~25-26 hours of planned Phase 0-5 work — feasible, but with effectively zero slack. Two decisions were locked in to protect that margin: a hard 3-hour cap with a predetermined fallback on Phase 1a graph construction (DECISIONS.md Entry #27), and a tool-allocation change routing Phases 2 and 3 to Claude Code instead of Copilot, since a Copilot drift/redo cycle on the discriminated-union contracts in those phases is not recoverable inside this schedule.

| Day | Date | Phase | Budgeted hours | Tool |
| --- | --- | --- | --- | --- |
| 1 | Jul 13 | Phase 0 — skeleton, config, Day-1 deploy | ~3 | Copilot |
| 2 | Jul 14 | Phase 1 — graph (3hr cap, Entry #27) + auth + Firestore schema | ~4.5-5 | Copilot (1b-1d); graph draft via Gemini |
| 3 | Jul 15 | Phase 2 — pathfinding engine + Layer-2 unit tests | ~4-5 | **Claude Code** |
| 4 | Jul 16 | Phase 3 — Intent + Guide agents + Gemini pre-flight + contract tests | ~4-5 | **Claude Code** |
| 5 | Jul 17 | Phase 4 — endpoints + frontend + renderer + closures + integration + full deploy | ~4-5 | Copilot |
| 6 | Jul 18 | Phase 5 (compressed, ~2hr) + contingency buffer for spillover | ~4-5 | — |
| 7 | Jul 19 | Phase 6 — final gauntlet + submit. No new features. | ~1-2 | — |

**Contingency logic:** Day 6's buffer is sized to absorb spillover from the two most likely sources — Phase 1a (graph, despite the cap) and Phase 3 (agent behavior, given the just-discovered Gemini model migration in Entry #26 is untested against real prompts yet). Phase 5 compresses cleanly because Evaluator Insights already established presentation as a cleared floor, not a differentiator, for this rubric.

**Open item:** confirm the exact submission portal close time on July 19 — determines whether Day 7 has real working hours or the effective deadline is end-of-Day-6.

---

## `make verify-docs` — verifiable claim set

Per DECISIONS.md Entry #24, Layer 2 requires an explicit set of claims the CI script checks. This is that set. Add to it as new claims appear; do not delete claims once added (mark them "retired" instead, with a rationale).

Each row is: claim from DECISIONS.md → the grep or file check that verifies it.

| # | Claim                                                                               | Verification                                                                                              |
| - | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 1 | Coverage floor is 95% (Entry #13, #21)                                              | `pyproject.toml` contains `--cov-fail-under=95` OR Makefile `test` target has `--cov-fail-under=95`       |
| 2 | ruff has C901, PLR0912, PLR0915 in `select` (Entry #13)                             | `pyproject.toml` `[tool.ruff]` `select` list contains `"C901"`, `"PLR0912"`, `"PLR0915"`                  |
| 3 | ruff `max-complexity = 10` (Entry #13)                                              | `pyproject.toml` `[tool.ruff.lint.mccabe]` `max-complexity = 10`                                          |
| 4 | Function-length threshold is 80 lines (Phase 0 detail)                              | `scripts/check_function_length.py` contains `MAX_FUNCTION_LINES = 80` (or equivalent constant)            |
| 5 | Fan profile has three fields (Entry #25 supersedes #7)                              | Firestore write path in code writes exactly `seat_section`, `accessibility_flags`, `preferred_language`   |
| 6 | Amenity enum has six values (Entry #11)                                             | Enum definition contains exactly `restroom`, `food`, `merchandise`, `atm`, `first_aid`, `charging_station`|
| 7 | Language enum has five values (Entry #25)                                           | Enum definition contains exactly `en`, `es`, `fr`, `pt`, `ar`                                             |
| 8 | Accessibility flag enum has four values (Entry #7)                                  | Enum definition contains exactly `wheelchair`, `no_stairs`, `stroller`, `visual_impairment`               |
| 9 | Edge accessibility enum has four values (Entry #8)                                  | Enum definition contains exactly `stairs_only`, `ramp`, `elevator`, `level`                               |
| 10| Pathfinding output is a discriminated union (Entry #17)                             | Grep for `RouteFound`, `RouteBlocked`, `RouteImpossible` in the pathfinding module                        |
| 11| Intent Agent output is a discriminated union (Entry #9)                             | Grep for `ResolvedRequest`, `AmbiguousRequest`, `UnresolvableRequest` in the intent module                |
| 12| Six endpoints exist (Entry #19)                                                     | FastAPI app registers exactly `POST /profile`, `GET /profile`, `POST /navigate`, `POST /staff/closures`, `GET /staff/closures`, `GET /health` |
| 13| Fan endpoints use Firebase Anonymous Auth (Entry #6, #19)                           | Auth dependency in code is applied to the three fan endpoints                                             |
| 14| Staff endpoints use STAFF_TOKEN (Entry #18)                                         | Auth dependency in code is applied to the two staff endpoints; reads `STAFF_TOKEN` env var                |
| 15| FastAPI is initialized with `redirect_slashes=False` (Entry #13 carryover)          | Grep for `redirect_slashes=False` in the app initialization file                                          |
| 16| Dockerfile uses `--no-server-header` (Entry #13 carryover)                          | Grep for `--no-server-header` in the Dockerfile                                                            |
| 17| Model tier decision is documented (Entry #13)                                       | DECISIONS.md contains an amendment recording the Phase 3 pre-flight outcome; code's factory calls match   |
| 18| Graph JSON is loaded at startup, not from Firestore (Entry #8)                      | Grep confirms `metlife_graph.json` is read via file I/O; no Firestore call fetches graph topology         |
| 19| `venue_state` is read on every navigate request (Entry #16)                         | Navigate handler contains a `venue_state` fetch; no cache decorator applied                               |
| 20| Error contract uses `K_SERVICE` for detail toggling (Entry #23)                     | Error handler code contains a check on `os.environ.get("K_SERVICE")`                                     |

**Retired claims:** _(none yet)_

**Notes for the script author (Phase 0 sub-task):**

- Machine-check the file-existence and grep claims first. Enum-value claims can be checked either by grep or by importing the enum in the script and comparing sets.
- Do NOT try to check architectural rationale ("staff can only toggle closures"). That belongs to the intent-validation gate, not the CI script.
- The script should print per-claim pass/fail so a failure is diagnosable.
- Wire the script into `make verify-docs` and into CI.

---

## Running log

Append an entry at each phase close: date, what shipped, validation command outputs, deviations from plan, decisions amended in DECISIONS.md.

- **2026-07-13 — Phase 0 (MACHINE-VALIDATED, awaiting intent validation).** Shipped: `pyproject.toml` (ruff select E/F/W/C901/PLR0912/PLR0915/I/B, max-complexity=10, `--cov-fail-under=95`), Makefile (lint/test/verify-graph/verify-docs/run/deploy), `scripts/check_function_length.py` (AST-based, MAX_FUNCTION_LINES=80), `scripts/verify_graph.py` (placeholder — skips until data/metlife_graph.json exists), `scripts/verify_docs.py` (6 real PASS: claims 1-4, 15, 16 / 14 SKIP for later phases / 0 FAIL), `app/main.py` (FastAPI `redirect_slashes=False`, CORS from `ALLOWED_ORIGIN`, security-headers middleware, `GET /health`), `Dockerfile` (python:3.12-slim + `--no-server-header`), `.github/workflows/ci.yml`, `.env.example`, `.gitignore`, `tests/test_main.py` (7 tests, 100% app coverage). Pre-flight: gcloud project=`promptwars-c4-metlife`, billing enabled, Firebase Anonymous Auth enabled. Deploy: `gcloud run deploy` to `asia-south1`; required IAM roles granted to compute default SA (`roles/cloudbuild.builds.builder`, `roles/storage.objectViewer`, `roles/artifactregistry.writer`, `roles/logging.logWriter`). Live URL returns `{"status":"ok"}` with HTTP 200. Commit `c81776d` pushed to origin/main. No DECISIONS.md amendments this phase.
- **2026-07-13 — Phase 0 intent validation passed → DONE.** Three non-blocking notes: (1) `.env.example` had a real project id (`promptwars-c4-metlife`) as the placeholder for `FIREBASE_PROJECT_ID` — not a secret, but bad hygiene in an example file; fixed to `your-firebase-project-id-here` before starting Phase 1. (2) Dockerfile hardcodes port 8080 rather than reading `$PORT` per Cloud Run's contract — works today because Cloud Run defaults to 8080, deferred to Phase 5 presentation pass. (3) Local venv is Python 3.13, CI and the deployed container are Python 3.12; both satisfy `requires-python = ">=3.12"`, no risk.
- **2026-07-13 — Phase 1 (MACHINE-VALIDATED, awaiting intent validation).** Shipped: **1a** `scripts/draft_graph.py` (Gemini 3.5-flash draft generator; Entry #26 model string), `data/metlife_graph.draft.json` (36 nodes, 51 edges), `scripts/_apply_graph_corrections.py` (auditable manual-correction record: section-uniqueness fixes for premium clubs, `coaches_club` edge `stairs_only`→`elevator`, filled 100/200-east section gaps), `data/metlife_graph.json` (final: 36 nodes, 51 edges). Entry #27 3-hour cap NOT hit — draft 16:44:08Z, verify-graph green ~17:04Z (~20 min). **1b** `scripts/verify_graph.py` now enforces: schema, section uniqueness, orphans, self-loops, full-graph connectivity, accessibility-subgraph connectivity, amenity/edge-accessibility enum conformance, positive walk-time; soft warning for edges >15 min. **1c** `app/auth/firebase.py` (`verify_fan_token` dep, Entry #23-shaped 401 payload with `K_SERVICE`-gated detail, idempotent Firebase init) + 13 auth tests. **1d** `app/models/enums.py` (`AccessibilityFlag`/`PreferredLanguage`/`AmenityType`/`EdgeAccessibility`), `app/firestore/fans.py` (Entry #15 schema, enum validation on write, `FanProfile` dataclass), `app/firestore/venue_state.py` (single `current` doc, sorted-deduped writes) + 12 unit tests. `scripts/verify_docs.py` claims 5–9 now real; claims 13/14/18 SKIP messages refined. Machine validation: `make lint` clean (9 files), `make test` 36 passed, coverage 98.43% (floor 95), `make verify-graph` OK, `make verify-docs` 11 PASS/9 SKIP/0 FAIL, live URL still 200. DECISIONS.md amended: Entry #27 Outcome recorded.
- **2026-07-13 — Phase 1 patch (caught during intent validation, before Phase 2 started).** Three related fixes bundled: (1) corrected graph had zero `stairs_only` edges, making Entry #7's stairs-warning + Entry #9's accessibility Dijkstra observationally identical to unfiltered routing — added 3 parallel `stairs_only` edges (100↔200 north/west, 200↔300 north) at 2 min each vs. the accessible 4–5 min alternatives, so accessibility filtering now produces a visible difference; graph now 36 nodes / 54 edges. (2) `scripts/verify_graph.py` gained a hard check that every node has a non-empty `landmark_aliases` list of non-empty strings (Phase 3 Intent Agent depends on this; existed in the data but was never validated). (3) `python-dotenv` was a listed dependency with no import site — wired `load_dotenv()` into `app/main.py` (safe no-op when no `.env`; confirmed dotenv 1.2.2 returns `False` without raising) and added `test_module_imports_without_env_file` proving the import path is `.env`-optional. Would have surfaced only during Phase 4 integration testing per Entry #21 if not caught here. DECISIONS.md amended: Entry #27 Outcome appended (no new numbered entry — this is a data-quality correction, not an architectural change).
- **2026-07-13 — Phase 2 (MACHINE-VALIDATED, awaiting intent validation).** Shipped: `app/graph/loader.py` (Node/Edge/Graph frozen dataclasses; `load_graph(path)` for arbitrary fixture files and `load_default_graph()` for the real MetLife JSON; rejects duplicate zone_ids and missing top-level keys; NOT yet wired into `app/main.py` — Phase 4). `app/pathfinding/engine.py` (Dijkstra with node/edge/accessibility filtering; discriminated union `RouteFound | RouteBlocked | RouteImpossible` per Entry #17; `RouteFound.traverses_stairs_only` flag for Entry #7's stairs-warning safety check; `_classify_blocked` distinguishes disconnected graph from closure-blocked from accessibility-blocked and names the specific closed node/edge or closed accessible edge in the reason string, not generic "no route"; module split into `_build_filtered_adjacency`/`_dijkstra`/`_accessible_closed_edges`/`_closure_reason`/`_classify_blocked`/`find_route` per Entry #13 Code Quality lever, all under the 80-line cap with max complexity 10). `tests/fixtures/small_graph.json` (8-node synthetic graph — not the real MetLife graph per Entry #21 Layer 2; includes `island` for RouteImpossible and stairs_only shortcuts b-e and c-g for accessibility observability). `tests/unit/test_pathfinding.py` (19 tests: all five Entry #21 required cases named explicitly — `test_basic_shortest_path`, `test_accessible_only_path`, `test_path_with_closures_reroutes`, `test_route_blocked_by_closure_under_accessibility`, `test_route_impossible_when_disconnected` — plus direct assertions of the `traverses_stairs_only` flag both ways, direction-agnostic edge closures, closed-node handling, unknown zone_ids, origin==destination, and loader error paths). `scripts/verify_docs.py` claim #10 upgraded to a real PASS check (greps engine.py for the three union members); claim #18 SKIP message refined per Phase 2 spec. Machine validation: `make lint` clean (13 files), `make test` 56 passed, coverage 98.75% (app/graph/loader.py 100%, app/pathfinding/engine.py 99%, floor 95), `make verify-graph` OK (36 nodes / 54 edges), `make verify-docs` 12 PASS / 8 SKIP / 0 FAIL, live URL `/health` HTTP 200. No DECISIONS.md amendments — Phase 2 implements Entry #9/#17 as already specified.

---

## Deviation tracker

Any place the build diverged from the 25 locked decisions or the phase plan. Each entry: what changed, why, and whether DECISIONS.md was updated with a supersession.

- _(none yet)_

---

## Live URL health log

Every deploy is logged with a timestamp and a `curl` result. This is the Efficiency probe defense: never a mystery about when the live URL last returned 200.

| Timestamp (UTC) | Commit SHA | `curl /health` result | Deploy source (phase) |
| --------------- | ---------- | --------------------- | --------------------- |
| 2026-07-13T16:30:35Z | c81776d | `{"status":"ok"}` — HTTP 200 | Phase 0 (skeleton) |