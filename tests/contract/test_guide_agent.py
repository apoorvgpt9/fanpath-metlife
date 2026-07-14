"""Contract tests for the Guide Agent (DECISIONS.md Entry #21 Layer 3).

Mocks the Gemini API boundary — ``app.agents.gemini_factory.flash`` — not the
agent function. Covers Entry #17 (RouteBlocked prose) and Entry #25
(non-English response).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.guide import STAIRS_WARNING, explain_route
from app.firestore.fans import FanProfile
from app.models.enums import AccessibilityFlag, PreferredLanguage
from app.pathfinding.engine import RouteBlocked, RouteFound


def _mock_client(response_text: str) -> MagicMock:
    client = MagicMock()
    client.generate_content.return_value = response_text
    return client


def _fan(
    *,
    lang: PreferredLanguage = PreferredLanguage.EN,
    flags: tuple[AccessibilityFlag, ...] = (),
) -> FanProfile:
    return FanProfile(
        uid="u1",
        seat_section="a",
        accessibility_flags=flags,
        preferred_language=lang,
        created_at="2026-07-14T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# RouteFound: expected zone names appear in output
# ---------------------------------------------------------------------------


@patch("app.agents.guide.flash")
def test_route_found_returns_directions_with_zone_names(mock_flash):
    canned = "Head from zone_a through zone_b to zone_g. Total walk 6 minutes."
    mock_flash.return_value = _mock_client(canned)
    result = RouteFound(
        origin="zone_a",
        destination="zone_g",
        nodes=("zone_a", "zone_b", "zone_g"),
        total_walk_time_minutes=6.0,
        traverses_stairs_only=False,
    )
    text = explain_route(result, "how do I get to zone_g?", _fan())
    assert "zone_a" in text
    assert "zone_g" in text
    # Prompt sent to Gemini must contain every zone_id in order.
    prompt = mock_flash.return_value.generate_content.call_args.args[0]
    assert "zone_a" in prompt
    assert "zone_b" in prompt
    assert "zone_g" in prompt


# ---------------------------------------------------------------------------
# Stairs-warning safety check (Entry #7)
# ---------------------------------------------------------------------------


@patch("app.agents.guide.flash")
def test_stairs_warning_appended_when_stairs_and_no_flags(mock_flash):
    mock_flash.return_value = _mock_client("Head over to gate G. It's a 4 minute walk.")
    result = RouteFound(
        origin="a",
        destination="g",
        nodes=("a", "b", "e", "g"),
        total_walk_time_minutes=4.0,
        traverses_stairs_only=True,
    )
    text = explain_route(result, "go to G", _fan())
    assert STAIRS_WARNING["en"] in text


@patch("app.agents.guide.flash")
def test_stairs_warning_omitted_when_flags_present(mock_flash):
    """A fan with accessibility flags already had stairs filtered out (Entry #9),
    so the warning is unnecessary and would be alarming."""
    mock_flash.return_value = _mock_client("Head over to gate G.")
    result = RouteFound(
        origin="a",
        destination="g",
        nodes=("a", "g"),
        total_walk_time_minutes=4.0,
        traverses_stairs_only=True,  # deliberately absurd; the guard is the flag check
    )
    text = explain_route(
        result, "go to G", _fan(flags=(AccessibilityFlag.WHEELCHAIR,))
    )
    assert STAIRS_WARNING["en"] not in text


@patch("app.agents.guide.flash")
def test_stairs_warning_omitted_when_no_stairs(mock_flash):
    mock_flash.return_value = _mock_client("Head over to G.")
    result = RouteFound(
        origin="a",
        destination="g",
        nodes=("a", "g"),
        total_walk_time_minutes=2.0,
        traverses_stairs_only=False,
    )
    text = explain_route(result, "go to G", _fan())
    assert STAIRS_WARNING["en"] not in text


# ---------------------------------------------------------------------------
# RouteBlocked: prose explanation, no SVG call attempted (Entry #17)
# ---------------------------------------------------------------------------


@patch("app.agents.guide.flash")
def test_route_blocked_explanation_no_svg_call(mock_flash):
    mock_flash.return_value = _mock_client(
        "There's no step-free route right now — the elevator near gate D is closed. "
        "If stairs are an option, I can route you that way."
    )
    result = RouteBlocked(
        origin="a",
        destination="g",
        reason="no accessible route — needed edge closed",
    )
    text = explain_route(
        result, "get to G", _fan(flags=(AccessibilityFlag.WHEELCHAIR,))
    )
    assert "step-free" in text or "accessible" in text or "closed" in text
    # Guard: guide agent must not attempt to render an SVG for a blocked route.
    # (There is no SVG module in Phase 3; if one is imported later, this
    # assertion will fail — the correct fix is a rendering pass in Phase 4,
    # not calling it from here.)
    with pytest.raises(ModuleNotFoundError):
        __import__("app.svg.renderer")


# ---------------------------------------------------------------------------
# Non-English response (Entry #25)
# ---------------------------------------------------------------------------


@patch("app.agents.guide.flash")
def test_spanish_route_found_is_not_english(mock_flash):
    canned = (
        "Diríjase desde zone_a pasando por zone_b hasta zone_g. "
        "Tiempo total: 6 minutos."
    )
    mock_flash.return_value = _mock_client(canned)
    result = RouteFound(
        origin="zone_a",
        destination="zone_g",
        nodes=("zone_a", "zone_b", "zone_g"),
        total_walk_time_minutes=6.0,
        traverses_stairs_only=False,
    )
    text = explain_route(result, "llévame a zone_g", _fan(lang=PreferredLanguage.ES))
    english_words = {"walk", "route", "then", "from", "minutes"}
    lowered = text.lower()
    assert not any(w in lowered.split() for w in english_words), (
        "Spanish response contained an English routing word"
    )
    assert "minutos" in lowered or "diríjase" in lowered
    prompt = mock_flash.return_value.generate_content.call_args.args[0]
    assert "Spanish" in prompt


@patch("app.agents.guide.flash")
def test_spanish_stairs_warning_uses_spanish_string(mock_flash):
    mock_flash.return_value = _mock_client("Diríjase hasta la salida G.")
    result = RouteFound(
        origin="a",
        destination="g",
        nodes=("a", "b", "e", "g"),
        total_walk_time_minutes=4.0,
        traverses_stairs_only=True,
    )
    text = explain_route(result, "vamos a G", _fan(lang=PreferredLanguage.ES))
    assert STAIRS_WARNING["es"] in text
    assert STAIRS_WARNING["en"] not in text


@patch("app.agents.guide.flash")
def test_arabic_language_is_supported(mock_flash):
    mock_flash.return_value = _mock_client("توجّه من zone_a إلى zone_g. المدة: 6 دقائق.")
    result = RouteFound(
        origin="zone_a",
        destination="zone_g",
        nodes=("zone_a", "zone_g"),
        total_walk_time_minutes=6.0,
        traverses_stairs_only=False,
    )
    text = explain_route(result, "خذني إلى G", _fan(lang=PreferredLanguage.AR))
    assert "دقائق" in text or "zone_g" in text
    prompt = mock_flash.return_value.generate_content.call_args.args[0]
    assert "Arabic" in prompt
