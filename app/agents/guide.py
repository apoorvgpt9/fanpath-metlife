"""Guide Agent (DECISIONS.md Entry #9, Entry #17, Entry #25).

Turns a deterministic pathfinding result into natural-language directions in
the fan's ``preferred_language``. The agent never invents nodes or times —
those come verbatim from the :class:`RouteFound` payload (Entry #9: "The
model never invents a route").

Two branches:

* :class:`RouteFound` — Flash-tier prompt with the ordered zone_id list and
  cumulative walk time. If the route traverses a ``stairs_only`` edge AND the
  fan has no accessibility flags, the Entry #7 stairs-warning is appended
  DETERMINISTICALLY in code — not left to the model to remember.
* :class:`RouteBlocked` — Entry #17 style prose explanation naming the
  blocking reason and offering to relax the accessibility filter when
  applicable. No SVG is generated for the blocked case (Entry #17).
"""

from __future__ import annotations

from app.agents.gemini_factory import flash
from app.firestore.fans import FanProfile
from app.models.enums import PreferredLanguage
from app.pathfinding.engine import RouteBlocked, RouteFound

# Entry #7 stairs-warning, per preferred_language (Entry #25).
STAIRS_WARNING: dict[str, str] = {
    "en": "This route includes stairs. Need a step-free alternative?",
    "es": "Esta ruta incluye escaleras. ¿Necesita una alternativa sin escalones?",
    "fr": "Cet itinéraire comprend des escaliers. Besoin d'un itinéraire sans marches ?",
    "pt": "Esta rota inclui escadas. Precisa de uma alternativa sem degraus?",
    "ar": "يتضمن هذا المسار درجات. هل تحتاج إلى بديل بدون درجات؟",
}


_FOUND_PROMPT_TEMPLATE = """You are the Guide Agent for MetLife Stadium indoor navigation.

Produce short, friendly turn-by-turn directions for the fan.

Language: respond ENTIRELY in {language}. Do not mix languages. Do not translate
zone identifiers — treat underscored zone_ids as-is or convert them to natural
phrases in {language} (e.g. "lower_west_concourse_a" -> a natural phrase for
"lower west concourse A"). Include the total walk time.

The fan's original query: <<<{query}>>>
{amenity_note}
Route (do NOT invent nodes; use exactly this order):
{route_lines}

Total walk time: {total_minutes} minutes.

Return prose only — no JSON, no markdown headers.
"""


_AMENITY_NOTE_TEMPLATE = (
    "\nThe fan asked for a KIND of place ('{amenity_type}'), not a specific zone. "
    "The pathfinding layer chose destination zone '{destination}' as the nearest "
    "matching '{amenity_type}'. Your directions MUST name this destination zone "
    "explicitly (as a natural phrase in {language}) so the fan knows which "
    "specific {amenity_type} they're being routed to.\n"
)


_BLOCKED_PROMPT_TEMPLATE = """You are the Guide Agent for MetLife Stadium indoor navigation.

The pathfinding layer could not find a route. Explain this to the fan in a
friendly way in {language}.

The fan's original query: <<<{query}>>>

Blocking reason (verbatim from pathfinding): {reason}

Rules:
- Respond ENTIRELY in {language}.
- Do NOT invent an alternate route — you do not have one.
- If the fan has accessibility flags {flags} and the reason mentions stairs
  or accessibility, offer to relax the accessibility filter (Entry #17 style:
  "If stairs are an option, I can route you that way").
- Otherwise, apologize briefly and suggest they try a different destination.

Return prose only.
"""


def _language_code(profile: FanProfile) -> str:
    """Return the fan's preferred-language BCP-47-style code (e.g. ``"en"``)."""
    lang = profile.preferred_language
    if isinstance(lang, PreferredLanguage):
        return lang.value
    return str(lang)


def _language_name(code: str) -> str:
    """Map an enum code to the language name embedded in prompt text."""
    return {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "pt": "Portuguese",
        "ar": "Arabic",
    }.get(code, "English")


def _explain_found(
    result: RouteFound,
    query: str,
    profile: FanProfile,
    amenity_type: str | None,
) -> str:
    """Render NL directions for a :class:`RouteFound`, appending stairs warning if needed."""
    code = _language_code(profile)
    route_lines = "\n".join(f"  {i + 1}. {n}" for i, n in enumerate(result.nodes))
    amenity_note = (
        _AMENITY_NOTE_TEMPLATE.format(
            amenity_type=amenity_type,
            destination=result.destination,
            language=_language_name(code),
        )
        if amenity_type is not None
        else ""
    )
    prompt = _FOUND_PROMPT_TEMPLATE.format(
        language=_language_name(code),
        query=query.strip(),
        route_lines=route_lines,
        total_minutes=result.total_walk_time_minutes,
        amenity_note=amenity_note,
    )
    body = flash().generate_content(prompt).strip()
    if result.traverses_stairs_only and not profile.accessibility_flags:
        warning = STAIRS_WARNING.get(code, STAIRS_WARNING["en"])
        return f"{body}\n\n{warning}"
    return body


def _explain_blocked(result: RouteBlocked, query: str, profile: FanProfile) -> str:
    """Render an Entry #17 style prose explanation for a :class:`RouteBlocked`."""
    code = _language_code(profile)
    flags = [f.value for f in profile.accessibility_flags] or "(none)"
    prompt = _BLOCKED_PROMPT_TEMPLATE.format(
        language=_language_name(code),
        query=query.strip(),
        reason=result.reason,
        flags=flags,
    )
    return flash().generate_content(prompt).strip()


def explain_route(
    result: RouteFound | RouteBlocked,
    query: str,
    profile: FanProfile,
    amenity_type: str | None = None,
) -> str:
    """Produce NL directions or an Entry #17 blocked-route explanation."""
    if isinstance(result, RouteFound):
        return _explain_found(result, query, profile, amenity_type)
    return _explain_blocked(result, query, profile)


__all__ = ["STAIRS_WARNING", "explain_route"]
