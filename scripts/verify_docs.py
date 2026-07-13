"""DECISIONS.md <-> code sync check.

Implements the 20-claim table from PROGRESS.md ("make verify-docs — verifiable
claim set"). Each claim is a function returning (state, message) where state
is one of "PASS", "FAIL", "SKIP".

SKIP means the file/module a claim checks does not yet exist. That is not a
failure — it is expected during early phases. FAIL means the file exists but
contradicts the claim.

Exit code 1 only if any claim is FAIL. PASS and SKIP both exit 0.

Phase 0 implements real checks for claims 1-4, 15, 16. The remaining claims
are stubbed as SKIP with the phase that will implement them.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

Result = tuple[str, str]


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Real Phase-0 checks
# ---------------------------------------------------------------------------

def claim_01_coverage_floor() -> Result:
    py = _read(REPO_ROOT / "pyproject.toml") or ""
    mk = _read(REPO_ROOT / "Makefile") or ""
    if "--cov-fail-under=95" in py or "--cov-fail-under=95" in mk:
        return PASS, "coverage floor --cov-fail-under=95 present"
    return FAIL, "expected --cov-fail-under=95 in pyproject.toml or Makefile"


def claim_02_ruff_select() -> Result:
    py = _read(REPO_ROOT / "pyproject.toml")
    if py is None:
        return FAIL, "pyproject.toml missing"
    required = ['"C901"', '"PLR0912"', '"PLR0915"']
    missing = [r for r in required if r not in py]
    if missing:
        return FAIL, f"ruff select missing: {', '.join(missing)}"
    return PASS, "ruff select contains C901, PLR0912, PLR0915"


def claim_03_max_complexity() -> Result:
    py = _read(REPO_ROOT / "pyproject.toml")
    if py is None:
        return FAIL, "pyproject.toml missing"
    if re.search(r"max-complexity\s*=\s*10", py):
        return PASS, "mccabe max-complexity = 10"
    return FAIL, "expected max-complexity = 10 in [tool.ruff.lint.mccabe]"


def claim_04_function_length() -> Result:
    script = _read(REPO_ROOT / "scripts" / "check_function_length.py")
    if script is None:
        return FAIL, "scripts/check_function_length.py missing"
    if re.search(r"MAX_FUNCTION_LINES\s*=\s*80", script):
        return PASS, "MAX_FUNCTION_LINES = 80"
    return FAIL, "expected MAX_FUNCTION_LINES = 80 in check_function_length.py"


def claim_15_redirect_slashes() -> Result:
    main_py = _read(REPO_ROOT / "app" / "main.py")
    if main_py is None:
        return SKIP, "app/main.py not present yet (Phase 0 target)"
    if "redirect_slashes=False" in main_py:
        return PASS, "FastAPI initialized with redirect_slashes=False"
    return FAIL, "expected redirect_slashes=False in app/main.py"


def claim_16_no_server_header() -> Result:
    dockerfile = _read(REPO_ROOT / "Dockerfile")
    if dockerfile is None:
        return SKIP, "Dockerfile not present yet"
    if "--no-server-header" in dockerfile:
        return PASS, "Dockerfile uses --no-server-header"
    return FAIL, "expected --no-server-header in Dockerfile"


# ---------------------------------------------------------------------------
# Stubs — implemented in later phases
# ---------------------------------------------------------------------------

def claim_05_fan_profile_fields() -> Result:
    return SKIP, "not yet applicable — Phase 1c (Firestore schema)"


def claim_06_amenity_enum() -> Result:
    return SKIP, "not yet applicable — Phase 1a (graph) / Phase 1c (schema)"


def claim_07_language_enum() -> Result:
    return SKIP, "not yet applicable — Phase 1c (Firestore schema)"


def claim_08_accessibility_flag_enum() -> Result:
    return SKIP, "not yet applicable — Phase 1c (Firestore schema)"


def claim_09_edge_accessibility_enum() -> Result:
    return SKIP, "not yet applicable — Phase 1a (graph)"


def claim_10_pathfinding_union() -> Result:
    return SKIP, "not yet applicable — Phase 2 (pathfinding)"


def claim_11_intent_agent_union() -> Result:
    return SKIP, "not yet applicable — Phase 3 (Intent Agent)"


def claim_12_six_endpoints() -> Result:
    return SKIP, "not yet applicable — Phase 4 (endpoints)"


def claim_13_fan_auth() -> Result:
    return SKIP, "not yet applicable — Phase 1d (auth) / Phase 4 (endpoints)"


def claim_14_staff_auth() -> Result:
    return SKIP, "not yet applicable — Phase 1d (auth) / Phase 4 (endpoints)"


def claim_17_model_tier() -> Result:
    return SKIP, "not yet applicable — Phase 3 (Gemini pre-flight)"


def claim_18_graph_static_load() -> Result:
    return SKIP, "not yet applicable — Phase 1a/1b (graph loader)"


def claim_19_venue_state_per_request() -> Result:
    return SKIP, "not yet applicable — Phase 4 (navigate handler)"


def claim_20_k_service_error_detail() -> Result:
    return SKIP, "not yet applicable — Phase 4 (error contract)"


CLAIMS: list[tuple[int, str, Callable[[], Result]]] = [
    (1, "coverage floor is 95%", claim_01_coverage_floor),
    (2, "ruff select includes C901, PLR0912, PLR0915", claim_02_ruff_select),
    (3, "ruff max-complexity = 10", claim_03_max_complexity),
    (4, "function-length threshold is 80", claim_04_function_length),
    (5, "fan profile has three fields", claim_05_fan_profile_fields),
    (6, "amenity enum has six values", claim_06_amenity_enum),
    (7, "language enum has five values", claim_07_language_enum),
    (8, "accessibility flag enum has four values", claim_08_accessibility_flag_enum),
    (9, "edge accessibility enum has four values", claim_09_edge_accessibility_enum),
    (10, "pathfinding output is a discriminated union", claim_10_pathfinding_union),
    (11, "Intent Agent output is a discriminated union", claim_11_intent_agent_union),
    (12, "six endpoints exist", claim_12_six_endpoints),
    (13, "fan endpoints use Firebase Anonymous Auth", claim_13_fan_auth),
    (14, "staff endpoints use STAFF_TOKEN", claim_14_staff_auth),
    (15, "FastAPI initialized with redirect_slashes=False", claim_15_redirect_slashes),
    (16, "Dockerfile uses --no-server-header", claim_16_no_server_header),
    (17, "model tier decision is documented", claim_17_model_tier),
    (18, "graph JSON is loaded at startup, not from Firestore", claim_18_graph_static_load),
    (19, "venue_state is read on every navigate request", claim_19_venue_state_per_request),
    (20, "error contract uses K_SERVICE for detail toggling", claim_20_k_service_error_detail),
]


def main() -> int:
    fail_count = 0
    pass_count = 0
    skip_count = 0
    for number, title, fn in CLAIMS:
        state, message = fn()
        print(f"[{state}] claim {number}: {title} — {message}")
        if state == FAIL:
            fail_count += 1
        elif state == PASS:
            pass_count += 1
        else:
            skip_count += 1
    print(
        f"\nSummary: {pass_count} PASS, {skip_count} SKIP, {fail_count} FAIL "
        f"(total {len(CLAIMS)})"
    )
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
