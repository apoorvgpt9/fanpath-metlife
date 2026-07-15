"""Contract tests for the Intent Agent (DECISIONS.md Entry #21 Layer 3).

Mocks the Gemini API boundary — ``app.agents.gemini_factory.pro`` — not the
agent functions themselves. Six required cases:

- 3 navigation-parse variants: Resolved, Ambiguous, Unresolvable
- 3 profile-extraction variants: Complete, Incomplete, Failed
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.gemini_factory import GeminiServiceError
from app.agents.intent import extract_profile, parse_navigation_request
from app.agents.schemas import (
    AmbiguousRequest,
    ConversationTurn,
    ProfileComplete,
    ProfileFailed,
    ProfileIncomplete,
    ResolvedRequest,
    UnresolvableRequest,
)
from app.firestore.fans import FanProfile
from app.graph.loader import load_graph
from app.models.enums import AccessibilityFlag, PreferredLanguage

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "small_graph.json"


@pytest.fixture
def small_graph():
    return load_graph(FIXTURE)


@pytest.fixture
def fan():
    return FanProfile(
        uid="u1",
        seat_section="a",
        accessibility_flags=(),
        preferred_language=PreferredLanguage.EN,
        created_at="2026-07-14T00:00:00Z",
    )


def _mock_client(response_text: str) -> MagicMock:
    client = MagicMock()
    client.generate_content = AsyncMock(return_value=response_text)
    return client


# ---------------------------------------------------------------------------
# Navigation parse: 3 variants
# ---------------------------------------------------------------------------


@patch("app.agents.intent.pro")
async def test_navigation_resolved(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "resolved",
                "origin": "a",
                "destination": "g",
                "rationale": "clear origin and destination",
            }
        )
    )
    result = await parse_navigation_request("get me from A to G", fan, [], small_graph)
    assert isinstance(result, ResolvedRequest)
    assert result.origin == "a"
    assert result.destination == "g"


@patch("app.agents.intent.pro")
async def test_navigation_ambiguous(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "ambiguous",
                "candidates": ["b", "c"],
                "clarification_question": "did you mean B junction or C junction?",
            }
        )
    )
    result = await parse_navigation_request("get me to the junction", fan, [], small_graph)
    assert isinstance(result, AmbiguousRequest)
    assert set(result.candidates) == {"b", "c"}


@patch("app.agents.intent.pro")
async def test_navigation_unresolvable(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(
        json.dumps({"type": "unresolvable", "reason": "off-topic query"})
    )
    result = await parse_navigation_request("what's the score?", fan, [], small_graph)
    assert isinstance(result, UnresolvableRequest)
    assert "off-topic" in result.reason


@patch("app.agents.intent.pro")
async def test_navigation_history_is_used(mock_pro, small_graph, fan):
    """Client-managed history (Entry #10) is passed to the prompt, not read from Firestore."""
    mock_pro.return_value = _mock_client(
        json.dumps({"type": "resolved", "origin": "a", "destination": "g", "rationale": ""})
    )
    history = [
        ConversationTurn(role="fan", content="I'm at gate A"),
        ConversationTurn(role="guide", content="OK, where to?"),
    ]
    await parse_navigation_request("take me to G", fan, history, small_graph)
    prompt = mock_pro.return_value.generate_content.call_args.args[0]
    assert "I'm at gate A" in prompt
    assert "OK, where to?" in prompt


async def test_navigation_empty_query_short_circuits(small_graph, fan):
    """Empty query must not touch Gemini."""
    with patch("app.agents.intent.pro") as mock_pro:
        result = await parse_navigation_request("   ", fan, [], small_graph)
        assert isinstance(result, UnresolvableRequest)
        mock_pro.assert_not_called()


@patch("app.agents.intent.pro")
async def test_navigation_unknown_zone_id_raises(mock_pro, small_graph, fan):
    """Model that invents a zone not in the graph must be rejected — Entry #9."""
    mock_pro.return_value = _mock_client(
        json.dumps(
            {"type": "resolved", "origin": "a", "destination": "not_a_zone", "rationale": ""}
        )
    )
    with pytest.raises(GeminiServiceError, match="not in graph"):
        await parse_navigation_request("go somewhere", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_malformed_json_raises(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client("this is not json")
    with pytest.raises(GeminiServiceError, match="not valid JSON"):
        await parse_navigation_request("go somewhere", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_unknown_type_raises(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(json.dumps({"type": "banana"}))
    with pytest.raises(GeminiServiceError, match="unknown type"):
        await parse_navigation_request("go", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_missing_type_raises(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(json.dumps({"origin": "a"}))
    with pytest.raises(GeminiServiceError, match="missing 'type'"):
        await parse_navigation_request("go", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_validation_failure_raises(mock_pro, small_graph, fan):
    mock_pro.return_value = _mock_client(json.dumps({"type": "resolved", "origin": 5}))
    with pytest.raises(GeminiServiceError, match="failed validation"):
        await parse_navigation_request("go", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_resolved_amenity_only(mock_pro, small_graph, fan):
    """Entry #28 — amenity-type destination without a specific zone."""
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "resolved",
                "origin": "a",
                "destination_amenity_type": "restroom",
                "rationale": "fan asked for closest restroom",
            }
        )
    )
    result = await parse_navigation_request(
        "where's the closest restroom?", fan, [], small_graph
    )
    assert isinstance(result, ResolvedRequest)
    assert result.origin == "a"
    assert result.destination is None
    assert result.destination_amenity_type is not None
    assert result.destination_amenity_type.value == "restroom"


@patch("app.agents.intent.pro")
async def test_navigation_resolved_rejects_both_destination_fields(
    mock_pro, small_graph, fan
):
    """Entry #28 — model_validator forbids setting both destination fields."""
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "resolved",
                "origin": "a",
                "destination": "g",
                "destination_amenity_type": "restroom",
                "rationale": "",
            }
        )
    )
    with pytest.raises(GeminiServiceError, match="failed validation"):
        await parse_navigation_request("go somewhere", fan, [], small_graph)


@patch("app.agents.intent.pro")
async def test_navigation_resolved_rejects_neither_destination_field(
    mock_pro, small_graph, fan
):
    """Entry #28 — model_validator forbids leaving both destination fields unset."""
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "resolved",
                "origin": "a",
                "rationale": "",
            }
        )
    )
    with pytest.raises(GeminiServiceError, match="failed validation"):
        await parse_navigation_request("go", fan, [], small_graph)


# ---------------------------------------------------------------------------
# Profile extraction: 3 variants (Entry #7)
# ---------------------------------------------------------------------------


@patch("app.agents.intent.pro")
async def test_profile_complete_with_flags(mock_pro):
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "profile_complete",
                "seat_section": "128",
                "accessibility_flags": ["wheelchair"],
                "preferred_language": "en",
            }
        )
    )
    result = await extract_profile("I'm in 128, my mother uses a wheelchair")
    assert isinstance(result, ProfileComplete)
    assert result.seat_section == "128"
    assert AccessibilityFlag.WHEELCHAIR in result.accessibility_flags
    assert result.preferred_language == PreferredLanguage.EN


@patch("app.agents.intent.pro")
async def test_profile_complete_no_accessibility_is_still_complete(mock_pro):
    """Entry #7: silence about accessibility → empty flags → ProfileComplete, no follow-up."""
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "profile_complete",
                "seat_section": "305",
                "accessibility_flags": [],
                "preferred_language": "es",
            }
        )
    )
    result = await extract_profile("Estoy en la sección 305")
    assert isinstance(result, ProfileComplete)
    assert result.accessibility_flags == ()
    assert result.preferred_language == PreferredLanguage.ES


@patch("app.agents.intent.pro")
async def test_profile_incomplete_missing_seat(mock_pro):
    mock_pro.return_value = _mock_client(
        json.dumps(
            {
                "type": "profile_incomplete",
                "missing": ["seat_section"],
                "followup_question": "Which section are you in?",
            }
        )
    )
    result = await extract_profile("I use a wheelchair")
    assert isinstance(result, ProfileIncomplete)
    assert "seat_section" in result.missing


@patch("app.agents.intent.pro")
async def test_profile_failed_from_model(mock_pro):
    mock_pro.return_value = _mock_client(
        json.dumps({"type": "profile_failed", "reason": "gibberish input"})
    )
    result = await extract_profile("asdlkfjasldkfj")
    assert isinstance(result, ProfileFailed)


async def test_profile_empty_input_short_circuits():
    with patch("app.agents.intent.pro") as mock_pro:
        result = await extract_profile("")
        assert isinstance(result, ProfileFailed)
        mock_pro.assert_not_called()


@patch("app.agents.intent.pro")
async def test_profile_malformed_json_raises(mock_pro):
    mock_pro.return_value = _mock_client("not json at all")
    with pytest.raises(GeminiServiceError, match="not valid JSON"):
        await extract_profile("hello")


@patch("app.agents.intent.pro")
async def test_profile_unknown_type_raises(mock_pro):
    mock_pro.return_value = _mock_client(json.dumps({"type": "banana"}))
    with pytest.raises(GeminiServiceError, match="unknown type"):
        await extract_profile("hello")


@patch("app.agents.intent.pro")
async def test_profile_missing_type_raises(mock_pro):
    mock_pro.return_value = _mock_client(json.dumps({"seat_section": "128"}))
    with pytest.raises(GeminiServiceError, match="missing 'type'"):
        await extract_profile("hello")


@patch("app.agents.intent.pro")
async def test_profile_validation_failure_raises(mock_pro):
    mock_pro.return_value = _mock_client(
        json.dumps({"type": "profile_complete", "seat_section": 128})
    )
    with pytest.raises(GeminiServiceError, match="failed validation"):
        await extract_profile("hello")


# ---------------------------------------------------------------------------
# Gemini JSON-parse retry (Phase 5 hardening)
# ---------------------------------------------------------------------------


@patch("app.agents.intent.pro")
async def test_profile_retry_on_json_parse_failure(mock_pro):
    """First call returns bad JSON, retry succeeds."""
    good = json.dumps(
        {"type": "profile_complete", "seat_section": "214",
         "accessibility_flags": [], "preferred_language": "en"}
    )
    client = MagicMock()
    client.generate_content = AsyncMock(side_effect=["not json", good])
    mock_pro.return_value = client
    result = await extract_profile("section 214")
    assert isinstance(result, ProfileComplete)
    assert client.generate_content.call_count == 2


@patch("app.agents.intent.pro")
async def test_navigation_retry_on_json_parse_failure(mock_pro, small_graph, fan):
    """First call returns bad JSON, retry succeeds."""
    good = json.dumps(
        {"type": "resolved", "origin": "a", "destination": "g", "rationale": ""}
    )
    client = MagicMock()
    client.generate_content = AsyncMock(side_effect=["not json", good])
    mock_pro.return_value = client
    result = await parse_navigation_request("from A to G", fan, [], small_graph)
    assert isinstance(result, ResolvedRequest)
    assert client.generate_content.call_count == 2
