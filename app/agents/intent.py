"""Intent Agent (DECISIONS.md Entry #9, Entry #7).

Two responsibilities, one module:

1. :func:`extract_profile` — onboard a fan from a single NL prompt into a
   three-field profile (Entry #7 / Entry #25). Returns
   ``ProfileComplete | ProfileIncomplete | ProfileFailed``. Per Entry #7 the
   system does NOT ask a follow-up when only accessibility is missing; that
   silently defaults to no flags and yields ``ProfileComplete``.
   ``ProfileIncomplete`` is reserved for a missing seat_section.

2. :func:`parse_navigation_request` — turn an NL navigation query + the fan's
   profile + last 3 conversation turns (Entry #10) + the loaded graph into a
   structured ``ResolvedRequest | AmbiguousRequest | UnresolvableRequest``.
   Grounds against the graph's real ``zone_id`` and ``landmark_aliases`` — the
   model never invents a zone that isn't in the graph.

Both use the Pro-tier client (Entry #13). Model boundary is
``gemini_factory.GeminiClient.generate_content`` — contract tests mock at that
seam.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.gemini_factory import (
    GeminiError,
    GeminiServiceError,
    pro,
)
from app.agents.schemas import (
    AmbiguousRequest,
    ConversationTurn,
    NavigationParse,
    ProfileComplete,
    ProfileExtraction,
    ProfileFailed,
    ProfileIncomplete,
    ResolvedRequest,
    UnresolvableRequest,
)
from app.firestore.fans import FanProfile
from app.graph.loader import Graph

# ---------------------------------------------------------------------------
# Profile extraction (Entry #7)
# ---------------------------------------------------------------------------

_PROFILE_PROMPT_TEMPLATE = """You are onboarding a fan for MetLife Stadium indoor navigation.

Extract three fields from the fan's message:

- seat_section: string (e.g. "128", "214", "Section 305"). REQUIRED. If not
  mentioned, mark it as missing.
- accessibility_flags: subset of {"wheelchair","no_stairs","stroller","visual_impairment"}.
  If nothing accessibility-related is mentioned, return an empty list — do NOT
  ask a follow-up. Empty is a valid, complete answer.
- preferred_language: one of {"en","es","fr","pt","ar"}. Detect from the
  language of the message or from explicit statements ("I speak Spanish").
  Default "en".

Return STRICT JSON (no markdown, no prose) matching EXACTLY one of these shapes:

If seat_section extracted:
  {"type":"profile_complete",
   "seat_section":"<string>",
   "accessibility_flags":[<zero-or-more flags>],
   "preferred_language":"<code>"}

If seat_section could not be extracted:
  {"type":"profile_incomplete",
   "missing":["seat_section"],
   "followup_question":"<a natural follow-up in preferred_language>"}

If the message is unusable (empty, gibberish, off-topic):
  {"type":"profile_failed","reason":"<short reason>"}

Fan message: <<<__NL_INPUT__>>>
"""


def _parse_profile_json(raw: str) -> ProfileExtraction:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeminiServiceError(f"profile response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "type" not in data:
        raise GeminiServiceError(f"profile response missing 'type' discriminator: {data!r}")
    return _dispatch_profile(data)


def _dispatch_profile(data: dict[str, Any]) -> ProfileExtraction:
    kind = data.get("type")
    try:
        if kind == "profile_complete":
            return ProfileComplete.model_validate(data)
        if kind == "profile_incomplete":
            return ProfileIncomplete.model_validate(data)
        if kind == "profile_failed":
            return ProfileFailed.model_validate(data)
    except ValidationError as exc:
        raise GeminiServiceError(f"profile response failed validation: {exc}") from exc
    raise GeminiServiceError(f"profile response has unknown type: {kind!r}")


def extract_profile(nl_input: str) -> ProfileExtraction:
    """Parse a fan's onboarding message into a profile-extraction union member."""
    if not nl_input or not nl_input.strip():
        return ProfileFailed(reason="empty input")
    prompt = _PROFILE_PROMPT_TEMPLATE.replace("__NL_INPUT__", nl_input.strip())
    client = pro()
    raw = client.generate_content(prompt, response_mime_type="application/json")
    return _parse_profile_json(raw)


# ---------------------------------------------------------------------------
# Navigation-request parsing (Entry #9, Entry #10)
# ---------------------------------------------------------------------------

_NAVIGATION_PROMPT_TEMPLATE = """You are the Intent Agent for MetLife Stadium indoor navigation.

Fan profile:
- seat_section: {seat_section}
- accessibility_flags: {accessibility_flags}
- preferred_language: {preferred_language}

Last conversation turns (oldest first):
{history_block}

The stadium graph has these zones. You MUST NOT invent a zone_id. Every
zone_id you return must appear verbatim in this list.

{zones_block}

Fan's new query: <<<{query}>>>

Return STRICT JSON (no markdown, no prose) matching EXACTLY one of these shapes:

Resolved (both origin and destination are unambiguous zone_ids from the list):
  {{"type":"resolved",
    "origin":"<zone_id>",
    "destination":"<zone_id>",
    "rationale":"<short>"}}

Ambiguous (multiple plausible destinations OR origin — offer 2-4 candidates):
  {{"type":"ambiguous",
    "candidates":["<zone_id>","<zone_id>"],
    "clarification_question":"<in preferred_language>"}}

Unresolvable (query refers to something not in the graph, or is off-topic):
  {{"type":"unresolvable","reason":"<short reason>"}}
"""


def _format_history(history: list[ConversationTurn]) -> str:
    if not history:
        return "(no prior turns)"
    lines = [f"- {turn.role}: {turn.content}" for turn in history[-3:]]
    return "\n".join(lines)


def _format_zones(graph: Graph) -> str:
    lines: list[str] = []
    for zone_id, node in graph.nodes.items():
        aliases = ", ".join(node.landmark_aliases) or "(no aliases)"
        sections = ", ".join(node.sections) if node.sections else "(none)"
        lines.append(f"- {zone_id} | sections: {sections} | aliases: {aliases}")
    return "\n".join(lines)


def _build_navigation_prompt(
    query: str,
    profile: FanProfile,
    history: list[ConversationTurn],
    graph: Graph,
) -> str:
    flags = [f.value for f in profile.accessibility_flags] or "(none)"
    return _NAVIGATION_PROMPT_TEMPLATE.format(
        seat_section=profile.seat_section,
        accessibility_flags=flags,
        preferred_language=profile.preferred_language.value,
        history_block=_format_history(history),
        zones_block=_format_zones(graph),
        query=query.strip(),
    )


def _parse_navigation_json(raw: str, graph: Graph) -> NavigationParse:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeminiServiceError(f"navigation response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "type" not in data:
        raise GeminiServiceError(f"navigation response missing 'type': {data!r}")
    return _dispatch_navigation(data, graph)


def _dispatch_navigation(data: dict[str, Any], graph: Graph) -> NavigationParse:
    kind = data.get("type")
    try:
        if kind == "resolved":
            parsed = ResolvedRequest.model_validate(data)
            _assert_zones_exist(graph, [parsed.origin, parsed.destination])
            return parsed
        if kind == "ambiguous":
            parsed_a = AmbiguousRequest.model_validate(data)
            _assert_zones_exist(graph, list(parsed_a.candidates))
            return parsed_a
        if kind == "unresolvable":
            return UnresolvableRequest.model_validate(data)
    except ValidationError as exc:
        raise GeminiServiceError(f"navigation response failed validation: {exc}") from exc
    raise GeminiServiceError(f"navigation response has unknown type: {kind!r}")


def _assert_zones_exist(graph: Graph, zone_ids: list[str]) -> None:
    unknown = [z for z in zone_ids if z not in graph.nodes]
    if unknown:
        raise GeminiServiceError(
            f"model returned zone_id(s) not in graph: {unknown}"
        )


def parse_navigation_request(
    query: str,
    profile: FanProfile,
    history: list[ConversationTurn],
    graph: Graph,
) -> NavigationParse:
    """Ground an NL query against the loaded graph. Raises :class:`GeminiError`."""
    if not query or not query.strip():
        return UnresolvableRequest(reason="empty query")
    prompt = _build_navigation_prompt(query, profile, history, graph)
    client = pro()
    raw = client.generate_content(prompt, response_mime_type="application/json")
    return _parse_navigation_json(raw, graph)


__all__ = [
    "GeminiError",
    "extract_profile",
    "parse_navigation_request",
]
