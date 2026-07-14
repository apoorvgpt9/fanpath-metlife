"""Static + runtime checks on static/fan.js's route-image alt-text logic
and conversation-history role names.

The route SVG's internal <title> is invisible to screen readers when the
SVG is delivered as ``<img src="data:...">`` — the browser does not expose
an embedded SVG's accessibility tree through <img>. So the alt attribute
must be derived from the Guide-Agent ``directions`` string, not the old
hardcoded generic label. This test enforces that contract.

The ``pushHistory`` role checks ensure that the roles sent to the backend
match ``ConversationTurn.role`` (``Literal["fan", "guide"]``), not generic
"user"/"assistant" values that would cause a 422 validation error on the
second navigate call.

The static-source checks always run. The behavioural check that actually
executes ``buildAltText`` is skipped if ``node`` is not on ``PATH`` (kept
CI-portable — GH Actions ubuntu-latest ships node preinstalled).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FAN_JS = Path(__file__).resolve().parents[2] / "static" / "fan.js"


def _read_fan_js() -> str:
    return FAN_JS.read_text(encoding="utf-8")


def test_alt_is_derived_from_directions_not_hardcoded() -> None:
    src = _read_fan_js()
    assert "img.alt = buildAltText(" in src, (
        "expected fan.js to build alt via buildAltText(text) — the alt must "
        "come from the actual Guide-Agent directions, not a fixed label"
    )
    hardcoded_assignment = (
        'img.alt = "Schematic map of the route through MetLife Stadium.";'
    )
    assert hardcoded_assignment not in src, (
        "the old hardcoded generic alt assignment must be gone; the string "
        "may only appear as the empty/invalid-input fallback constant"
    )


def test_build_alt_text_helper_is_defined() -> None:
    src = _read_fan_js()
    assert "function buildAltText(directions)" in src


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node not on PATH")
@pytest.mark.parametrize(
    ("directions", "expect_prefix", "expect_max_len", "must_not_equal_fallback"),
    [
        (
            "Head south on the plaza walkway to Gate C.",
            "Route map: ",
            141,
            True,
        ),
        (
            (
                "Head south on the plaza walkway, pass the merchandise stand on "
                "your right, take the ramp up to the 100 level, and continue "
                "along the concourse until you reach Section 128 on your left."
            ),
            "Route map: ",
            141,
            True,
        ),
        ("   ", None, None, False),
        ("", None, None, False),
    ],
)
def test_build_alt_text_runtime_behaviour(
    directions: str,
    expect_prefix: str | None,
    expect_max_len: int | None,
    must_not_equal_fallback: bool,
) -> None:
    """Extract buildAltText from fan.js and execute it via node."""
    src = _read_fan_js()
    marker = "function buildAltText(directions) {"
    start = src.index(marker)
    depth = 0
    end = None
    for i, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    assert end is not None, "could not find end of buildAltText function"
    fn_source = src[start:end]

    fallback = 'Schematic map of the route through MetLife Stadium.'
    script = (
        f"const ALT_MAX = 140;\n"
        f'const ALT_PREFIX = "Route map: ";\n'
        f"const ALT_FALLBACK = {json.dumps(fallback)};\n"
        f"{fn_source}\n"
        f"const input = {json.dumps(directions)};\n"
        f"process.stdout.write(buildAltText(input));\n"
    )
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    out = result.stdout
    if expect_prefix is not None:
        assert out.startswith(expect_prefix)
    if expect_max_len is not None:
        assert len(out) <= expect_max_len
    if must_not_equal_fallback:
        assert out != fallback
    else:
        assert out == fallback


# ---------------------------------------------------------------------------
# pushHistory role-name checks
# ---------------------------------------------------------------------------


def test_push_history_uses_fan_guide_roles() -> None:
    """pushHistory must push role:"fan" and role:"guide", not "user"/"assistant"."""
    src = _read_fan_js()
    assert 'role: "fan"' in src, (
        "pushHistory must use role:'fan' to match ConversationTurn schema"
    )
    assert 'role: "guide"' in src, (
        "pushHistory must use role:'guide' to match ConversationTurn schema"
    )


def test_push_history_does_not_use_user_assistant_roles() -> None:
    """Regression: the old "user"/"assistant" roles cause 422 validation errors."""
    src = _read_fan_js()
    assert 'role: "user"' not in src, (
        "fan.js must not push role:'user' — ConversationTurn only accepts 'fan'/'guide'"
    )
    assert 'role: "assistant"' not in src, (
        "fan.js must not push role:'assistant' — ConversationTurn only accepts 'fan'/'guide'"
    )
