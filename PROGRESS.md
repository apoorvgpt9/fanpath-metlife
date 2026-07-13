# PROGRESS.md

Rolling build state for **PromptWars Challenge 4 — Smart Indoor Navigation**.

DECISIONS.md is the constitutional spec. This file is the running log of what actually got built and validated. When they drift, this file wins over the Notion Progress Tracker (which mirrors this file), and DECISIONS.md wins over this file on architectural claims.

**Deadline:** July 19, 2026.

**Live URL:** _(added at Phase 0 close)_

**Repo:** _(added at Phase 0 close)_

---

## Phase status

| Phase | Description                                          | Status       | Machine validation | Intent validation | Notes                                             |
| ----- | ---------------------------------------------------- | ------------ | ------------------ | ----------------- | ------------------------------------------------- |
| 0     | Skeleton, config, Day-1 deploy                       | NOT STARTED  | —                  | —                 | Live URL must be green before this closes         |
| 1     | Graph (blocker) + auth + schema                      | NOT STARTED  | —                  | —                 | 1a+1b block all downstream; 4-hour cap on 1a      |
| 2     | Pathfinding + Layer-2 tests                          | NOT STARTED  | —                  | —                 | Highest-value tests                               |
| 3     | Intent + Guide agents + Gemini pre-flight            | NOT STARTED  | —                  | —                 | Pre-flight before agent logic                     |
| 4     | Endpoints + frontend + renderer + closures           | NOT STARTED  | —                  | —                 | Full app on live URL                              |
| 5     | Presentation pass                                    | NOT STARTED  | —                  | —                 | Cheap-signal proxies                              |
| 6     | Final gauntlet + submit                              | NOT STARTED  | —                  | —                 | No new features; submit once                      |

**Status values:** `NOT STARTED` / `IN PROGRESS` / `MACHINE-VALIDATED` / `INTENT-VALIDATED` / `DONE`.

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

- **[Not yet started]** — Build begins with Phase 0.

---

## Deviation tracker

Any place the build diverged from the 25 locked decisions or the phase plan. Each entry: what changed, why, and whether DECISIONS.md was updated with a supersession.

- _(none yet)_

---

## Live URL health log

Every deploy is logged with a timestamp and a `curl` result. This is the Efficiency probe defense: never a mystery about when the live URL last returned 200.

| Timestamp (UTC) | Commit SHA | `curl /health` result | Deploy source (phase) |
| --------------- | ---------- | --------------------- | --------------------- |
| _(pending Phase 0)_ | —          | —                     | —                     |
