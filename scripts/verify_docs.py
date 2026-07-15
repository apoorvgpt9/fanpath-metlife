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

import json
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
    if "--cov-fail-under=100" in py or "--cov-fail-under=100" in mk:
        return PASS, "coverage floor --cov-fail-under=100 present"
    return FAIL, "expected --cov-fail-under=100 in pyproject.toml or Makefile"


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
    src = _read(REPO_ROOT / "app" / "firestore" / "fans.py")
    if src is None:
        return SKIP, "app/firestore/fans.py not present yet"
    required = ["seat_section", "accessibility_flags", "preferred_language"]
    missing = [name for name in required if f'"{name}"' not in src and f"'{name}'" not in src]
    if missing:
        return FAIL, f"fans.py missing profile field(s): {missing}"
    return PASS, "fans.py references seat_section, accessibility_flags, preferred_language"


def _enum_values(module_src: str, enum_name: str) -> set[str] | None:
    pattern = rf"class {enum_name}\b.*?(?=\nclass |\Z)"
    match = re.search(pattern, module_src, flags=re.DOTALL)
    if not match:
        return None
    body = match.group(0)
    return set(re.findall(r'=\s*"([^"]+)"', body))


def claim_06_amenity_enum() -> Result:
    src = _read(REPO_ROOT / "app" / "models" / "enums.py")
    if src is None:
        return SKIP, "app/models/enums.py not present yet"
    values = _enum_values(src, "AmenityType")
    expected = {"restroom", "food", "merchandise", "atm", "first_aid", "charging_station"}
    if values is None:
        return FAIL, "AmenityType enum not found in app/models/enums.py"
    if values != expected:
        return FAIL, f"AmenityType values {sorted(values)} != expected {sorted(expected)}"
    return PASS, "AmenityType has exactly the six values"


def claim_07_language_enum() -> Result:
    src = _read(REPO_ROOT / "app" / "models" / "enums.py")
    if src is None:
        return SKIP, "app/models/enums.py not present yet"
    values = _enum_values(src, "PreferredLanguage")
    expected = {"en", "es", "fr", "pt", "ar"}
    if values is None:
        return FAIL, "PreferredLanguage enum not found"
    if values != expected:
        return FAIL, f"PreferredLanguage values {sorted(values)} != expected {sorted(expected)}"
    return PASS, "PreferredLanguage has exactly the five values"


def claim_08_accessibility_flag_enum() -> Result:
    src = _read(REPO_ROOT / "app" / "models" / "enums.py")
    if src is None:
        return SKIP, "app/models/enums.py not present yet"
    values = _enum_values(src, "AccessibilityFlag")
    expected = {"wheelchair", "no_stairs", "stroller", "visual_impairment"}
    if values is None:
        return FAIL, "AccessibilityFlag enum not found"
    if values != expected:
        return FAIL, f"AccessibilityFlag values {sorted(values)} != expected {sorted(expected)}"
    return PASS, "AccessibilityFlag has exactly the four values"


def claim_09_edge_accessibility_enum() -> Result:
    src = _read(REPO_ROOT / "app" / "models" / "enums.py")
    if src is None:
        return SKIP, "app/models/enums.py not present yet"
    values = _enum_values(src, "EdgeAccessibility")
    expected = {"stairs_only", "ramp", "elevator", "level"}
    if values is None:
        return FAIL, "EdgeAccessibility enum not found"
    if values != expected:
        return FAIL, f"EdgeAccessibility values {sorted(values)} != expected {sorted(expected)}"
    # Spot-check graph edges use only these values, if the graph exists.
    graph_path = REPO_ROOT / "data" / "metlife_graph.json"
    if graph_path.exists():
        try:
            data = json.loads(graph_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return FAIL, f"metlife_graph.json unreadable: {exc}"
        stray = {e.get("accessibility") for e in data.get("edges", [])} - expected
        if stray:
            return FAIL, f"graph edges contain unknown accessibility values: {sorted(stray)}"
    return PASS, "EdgeAccessibility has exactly the four values; graph edges conform"


def claim_10_pathfinding_union() -> Result:
    engine = _read(REPO_ROOT / "app" / "pathfinding" / "engine.py")
    if engine is None:
        return SKIP, "app/pathfinding/engine.py not present yet"
    required = ["RouteFound", "RouteBlocked", "RouteImpossible"]
    missing = [name for name in required if name not in engine]
    if missing:
        return FAIL, f"pathfinding/engine.py missing union member(s): {missing}"
    return PASS, "engine.py defines RouteFound | RouteBlocked | RouteImpossible"


def claim_11_intent_agent_union() -> Result:
    schemas = _read(REPO_ROOT / "app" / "agents" / "schemas.py")
    if schemas is None:
        return SKIP, "app/agents/schemas.py not present yet"
    required = ["ResolvedRequest", "AmbiguousRequest", "UnresolvableRequest"]
    missing = [name for name in required if name not in schemas]
    if missing:
        return FAIL, f"schemas.py missing Intent-Agent union member(s): {missing}"
    return PASS, "schemas.py defines ResolvedRequest | AmbiguousRequest | UnresolvableRequest"


def claim_12_six_endpoints() -> Result:
    routes = _read(REPO_ROOT / "app" / "routes.py")
    main_py = _read(REPO_ROOT / "app" / "main.py")
    if routes is None or main_py is None:
        return SKIP, "endpoints not yet declared"
    expected = [
        ('@router.post("/profile")', routes),
        ('@router.get("/profile")', routes),
        ('@router.post("/navigate")', routes),
        ('@router.post("/staff/closures")', routes),
        ('@router.get("/staff/closures")', routes),
        ('@app.get("/health")', main_py),
    ]
    missing = [needle for needle, source in expected if needle not in source]
    if missing:
        return FAIL, f"expected endpoint declarations missing: {missing}"
    return PASS, "six endpoints declared per Entry #19"


def claim_13_fan_auth() -> Result:
    routes = _read(REPO_ROOT / "app" / "routes.py")
    if routes is None:
        return SKIP, "app/routes.py not present yet"
    if "verify_fan_token" not in routes or "FanUid" not in routes:
        return FAIL, "fan endpoints do not depend on verify_fan_token / FanUid"
    return PASS, "fan endpoints depend on verify_fan_token (Firebase Anonymous)"


def claim_14_staff_auth() -> Result:
    staff = _read(REPO_ROOT / "app" / "auth" / "staff.py")
    routes = _read(REPO_ROOT / "app" / "routes.py")
    if staff is None or routes is None:
        return SKIP, "staff auth not yet present"
    if 'os.environ.get("STAFF_TOKEN")' not in staff and "os.environ['STAFF_TOKEN']" not in staff:
        return FAIL, "staff auth does not read STAFF_TOKEN env var"
    if "hmac.compare_digest" not in staff:
        return FAIL, "staff token comparison is not constant-time (hmac.compare_digest)"
    if "verify_staff_token" not in routes:
        return FAIL, "staff endpoints do not depend on verify_staff_token"
    return PASS, "staff endpoints use STAFF_TOKEN with constant-time compare"


def claim_17_model_tier() -> Result:
    factory = _read(REPO_ROOT / "app" / "agents" / "gemini_factory.py")
    if factory is None:
        return SKIP, "app/agents/gemini_factory.py not present yet"
    if "gemini-3.5-flash" not in factory:
        return FAIL, "gemini_factory.py missing gemini-3.5-flash model string"
    if "def flash" not in factory or "def pro" not in factory:
        return FAIL, "gemini_factory.py missing flash() / pro() factory functions"
    return PASS, "gemini_factory.py exposes flash() + pro() with model-tier decision documented"


def claim_18_graph_static_load() -> Result:
    main_py = _read(REPO_ROOT / "app" / "main.py")
    if main_py is None:
        return SKIP, "app/main.py not present yet"
    if "load_default_graph()" not in main_py:
        return FAIL, "app/main.py does not call load_default_graph() at startup"
    if "app.state.graph" not in main_py:
        return FAIL, "app/main.py does not stash the graph on app.state.graph"
    return PASS, "graph loaded once at startup and stashed on app.state.graph"


def claim_19_venue_state_per_request() -> Result:
    routes = _read(REPO_ROOT / "app" / "routes.py")
    if routes is None:
        return SKIP, "app/routes.py not present yet"
    nav_match = re.search(
        r"def post_navigate\b.*?(?=\ndef |\Z)", routes, flags=re.DOTALL
    )
    if not nav_match:
        return FAIL, "post_navigate handler not found in app/routes.py"
    if "venue_repo.read_state" not in nav_match.group(0):
        return FAIL, "post_navigate does not call venue_repo.read_state on every request"
    return PASS, "post_navigate reads venue_state fresh via read_state each call"


def claim_20_k_service_error_detail() -> Result:
    errors = _read(REPO_ROOT / "app" / "errors.py")
    if errors is None:
        return SKIP, "app/errors.py not present yet"
    if 'os.environ.get("K_SERVICE")' not in errors and "os.environ['K_SERVICE']" not in errors:
        return FAIL, "app/errors.py does not gate detail on the K_SERVICE env var"
    if '"type": "error"' not in errors or '"category"' not in errors:
        return FAIL, "app/errors.py does not emit the Entry #23 error shape"
    return PASS, "errors.py gates detail on K_SERVICE and emits Entry #23 shape"


def claim_21_static_frontend() -> Result:
    """Entry #20: frontend is static HTML + vanilla JS. No Jinja2, no TemplateResponse."""
    static_dir = REPO_ROOT / "static"
    required_files = ["fan.html", "fan.js", "staff.html", "staff.js", "style.css"]
    missing = [f for f in required_files if not (static_dir / f).exists()]
    if missing:
        return FAIL, f"static/ missing frontend file(s): {missing}"
    # No Jinja2 / TemplateResponse leaked into app/
    for py in (REPO_ROOT / "app").rglob("*.py"):
        text = _read(py) or ""
        if "TemplateResponse" in text or "Jinja2Templates" in text or "from jinja2" in text:
            return FAIL, f"Entry #20 violated: templating usage in {py.relative_to(REPO_ROOT)}"
    main_py = _read(REPO_ROOT / "app" / "main.py") or ""
    if 'StaticFiles(directory=' not in main_py:
        return FAIL, "app/main.py does not mount StaticFiles"
    return PASS, "frontend is static (fan.html, staff.html, JS, CSS) with no server templating"


def claim_22_svg_renderer_deterministic() -> Result:
    """Entry #12: SVG rendering is deterministic — no Gemini involvement."""
    renderer = _read(REPO_ROOT / "app" / "rendering" / "svg_renderer.py")
    if renderer is None:
        return FAIL, "app/rendering/svg_renderer.py missing"
    banned = ["gemini_factory", "google.genai", "GeminiClient", "explain_route"]
    hit = [name for name in banned if name in renderer]
    if hit:
        return FAIL, f"svg_renderer.py references model-side symbols: {hit}"
    if "def render_route" not in renderer:
        return FAIL, "svg_renderer.py does not define render_route()"
    routes = _read(REPO_ROOT / "app" / "routes.py") or ""
    if "render_route" not in routes:
        return FAIL, "app/routes.py does not call render_route"
    return PASS, "svg_renderer.py is Gemini-free; wired into /navigate via routes.py"


def claim_23_amenity_resolution() -> Result:
    """Entry #28: amenity-type destination resolution.

    ``destination_amenity_type`` must be a field on ``ResolvedRequest`` (mutually
    exclusive with ``destination``), and ``find_nearest_amenity`` must exist in
    the pathfinding engine and be wired into ``app/routes.py``.
    """
    schemas = _read(REPO_ROOT / "app" / "agents" / "schemas.py") or ""
    if "destination_amenity_type" not in schemas:
        return FAIL, "app/agents/schemas.py missing destination_amenity_type on ResolvedRequest"
    if "@model_validator" not in schemas:
        return FAIL, "schemas.py missing @model_validator enforcing mutual exclusion"
    engine = _read(REPO_ROOT / "app" / "pathfinding" / "engine.py") or ""
    if "def find_nearest_amenity" not in engine:
        return FAIL, "pathfinding/engine.py missing find_nearest_amenity"
    routes = _read(REPO_ROOT / "app" / "routes.py") or ""
    if "find_nearest_amenity" not in routes:
        return FAIL, "app/routes.py does not call find_nearest_amenity"
    return PASS, "amenity-type destinations resolved via find_nearest_amenity (Entry #28)"


CLAIMS: list[tuple[int, str, Callable[[], Result]]] = [
    (1, "coverage floor is 100%", claim_01_coverage_floor),
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
    (21, "frontend is static HTML + vanilla JS (Entry #20)", claim_21_static_frontend),
    (22, "SVG rendering is deterministic (Entry #12)", claim_22_svg_renderer_deterministic),
    (23, "amenity-type destination resolution (Entry #28)", claim_23_amenity_resolution),
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
