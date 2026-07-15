# PROGRESS.md

Rolling build state for **PromptWars Challenge 4 — Smart Indoor Navigation**.

DECISIONS.md is the constitutional spec. This file is the current-state snapshot: phase status, the `make verify-docs` claim table, and the latest test/coverage numbers. When they drift, this file wins over the Notion Progress Tracker (which mirrors this file), and DECISIONS.md wins over this file on architectural claims.

**Full build history and hotfix log:** see [`docs/BUILD-LOG.md`](docs/BUILD-LOG.md) — the phase-by-phase running log, deviation tracker, live URL health log, rubric self-assessment, and Phase 6 hotfix log all live there verbatim.

**Deadline:** July 19, 2026.

**Live URL:** <https://fanpath-metlife-973486326780.asia-south1.run.app>

**Repo:** <https://github.com/apoorvgpt9/fanpath-metlife>

---

## Phase status

| Phase | Description                                          | Status              | Machine validation | Intent validation | Notes                                             |
| ----- | ---------------------------------------------------- | ------------------- | ------------------ | ----------------- | ------------------------------------------------- |
| 0     | Skeleton, config, Day-1 deploy                       | DONE                | 2026-07-13         | 2026-07-13        | Live URL green; commit c81776d; intent validation passed with 3 non-blocking notes |
| 1     | Graph (blocker) + auth + schema                      | DONE                | 2026-07-13         | 2026-07-13         | 36 nodes, 54 edges (post-patch); intent validation passed for main build + patch; 11 PASS/9 SKIP/0 FAIL |
| 2     | Pathfinding + Layer-2 tests                          | DONE              | 2026-07-13         | 2026-07-13         | 19 pathfinding tests; engine 99%, loader 100%; 12 PASS/8 SKIP/0 FAIL; CI green, /health 200 confirmed |
| 3     | Intent + Guide agents + Gemini pre-flight            | DONE                | 2026-07-14         | 2026-07-14        | 38 new tests (19 intent, 8 guide, 11 factory); coverage 98.88%; 14 PASS/6 SKIP/0 FAIL; preflight pass (flash 200, pro 200). Built on Copilot. |
| 4     | Endpoints + frontend + renderer + closures           | DONE | 2026-07-14 (4A+4B+closeout+gap-close) | 2026-07-14                 | 4A+4B+closeout+gap-closing pass (Entry #28 amenity resolution, `GET /` redirect) all green. Current state (189 tests, 98.95% cov, 23/0/0 verify-docs) reflects Phases 5-6's additions on top, live at revision `fanpath-metlife-00011-7td`. Flipped to DONE — all four manual-browser checks (sign-in/UI load, route+map rendering, accessibility rerouting, staff toggle round trip) confirmed by human tester on 2026-07-14, resolving the earlier Phase 4/Phase 6 status inconsistency. |
| 5     | Presentation pass                                    | DONE  | 2026-07-14                  | 2026-07-14                 | Docstrings on all public functions/models; Gemini JSON-parse retry; OWASP Top 10 complete in SECURITY.md; pip-audit in CI; 186 tests, 98.95% cov, 23/0/0 verify-docs; deployed revision `fanpath-metlife-00009-tnh` |
| 6     | Final gauntlet + submit                              | DONE  | 2026-07-14                  | 2026-07-14                 | Machine gauntlet green (189 tests, 98.95% cov, 23/0/0 verify-docs, pip-audit clean); live-URL gauntlet green; docs frozen; history role-mismatch bug found and fixed same day. All four manual-browser checks (sign-in/UI, route+map rendering, staff toggle round trip, accessibility rerouting comparison) confirmed by human tester on 2026-07-14 — see `docs/BUILD-LOG.md`'s running log for the STAFF_TOKEN reconciliation that was needed to complete the staff check. |

**Status values:** `NOT STARTED` / `IN PROGRESS` / `MACHINE-VALIDATED` / `INTENT-VALIDATED` / `DONE`.

---

## Current state (as of 2026-07-15)

- **Tests:** 193 passed, **100.00%** coverage (`app/`, floor enforced at 100%)
- **`make verify-docs`:** 23 PASS / 0 SKIP / 0 FAIL
- **`make verify-graph`:** OK — 36 nodes, 54 edges
- **Live URL:** deployed revision `fanpath-metlife-00018-9s4`, `/health` returns 200

Full deploy-by-deploy history: `docs/BUILD-LOG.md`'s Live URL health log.

---

## `make verify-docs` — verifiable claim set

Per DECISIONS.md Entry #24, Layer 2 requires an explicit set of claims the CI script checks. This is that set. Add to it as new claims appear; do not delete claims once added (mark them "retired" instead, with a rationale).

Each row is: claim from DECISIONS.md → the grep or file check that verifies it.

| # | Claim                                                                               | Verification                                                                                              |
| - | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 1 | Coverage floor is 100% (Entry #13, #21)                                             | `pyproject.toml` contains `--cov-fail-under=100` OR Makefile `test` target has `--cov-fail-under=100`     |
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
| 21| Frontend is static HTML + vanilla JS (Entry #20)                                    | `static/` contains `fan.html`, `fan.js`, `staff.html`, `staff.js`, `style.css`; no `TemplateResponse`/`Jinja2Templates`/`from jinja2` anywhere under `app/`; `app/main.py` mounts `StaticFiles(directory=...)` |
| 22| SVG rendering is deterministic (Entry #12)                                          | `app/rendering/svg_renderer.py` exists, defines `render_route`, contains no reference to `gemini_factory`/`google.genai`/`GeminiClient`/`explain_route`; `app/routes.py` calls `render_route`                |
| 23| Amenity-type destination resolution (Entry #28)                                     | `app/agents/schemas.py` has `destination_amenity_type` on `ResolvedRequest` with a `@model_validator` enforcing mutual exclusion; `app/pathfinding/engine.py` defines `find_nearest_amenity`; `app/routes.py` calls it |

**Retired claims:** _(none yet)_

**Notes for the script author (Phase 0 sub-task):**

- Machine-check the file-existence and grep claims first. Enum-value claims can be checked either by grep or by importing the enum in the script and comparing sets.
- Do NOT try to check architectural rationale ("staff can only toggle closures"). That belongs to the intent-validation gate, not the CI script.
- The script should print per-claim pass/fail so a failure is diagnosable.
- Wire the script into `make verify-docs` and into CI.

---

Full build history and hotfix log: see [`docs/BUILD-LOG.md`](docs/BUILD-LOG.md).

