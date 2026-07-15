"""Discriminated-union Pydantic models for agent outputs.

Two distinct unions, one module, per DECISIONS.md:

* Navigation parse (Entry #9):
  ``ResolvedRequest | AmbiguousRequest | UnresolvableRequest``
* Profile extraction / onboarding (Entry #7):
  ``ProfileComplete | ProfileIncomplete | ProfileFailed``

Each variant carries a literal ``type`` discriminator so downstream dispatch is
unambiguous (``isinstance`` or ``match``) — never a bare string, never an
optional field standing in for state.

Also defines :class:`ConversationTurn`, the shape of each of the last-3 turns
that Entry #10 says are client-managed and sent in every ``POST /navigate``
body.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    DEFAULT_LANGUAGE,
    AccessibilityFlag,
    AmenityType,
    PreferredLanguage,
)


class _StrictModel(BaseModel):
    """Base model rejecting extra keys and freezing instances (Entry #9)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# Conversation memory (Entry #10)
# ---------------------------------------------------------------------------


class ConversationTurn(_StrictModel):
    """A single fan↔guide exchange in the rolling 3-turn conversation window."""

    role: Literal["fan", "guide"]
    content: str


# ---------------------------------------------------------------------------
# Navigation parse union (Entry #9)
# ---------------------------------------------------------------------------


class ResolvedRequest(_StrictModel):
    """Intent Agent resolved origin + destination unambiguously."""

    type: Literal["resolved"] = "resolved"
    origin: str
    destination: str | None = None
    destination_amenity_type: AmenityType | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def _exactly_one_destination(self) -> ResolvedRequest:
        """Enforce that exactly one of zone/amenity destination is set (Entry #28)."""
        has_zone = self.destination is not None
        has_amenity = self.destination_amenity_type is not None
        if has_zone == has_amenity:
            raise ValueError(
                "exactly one of 'destination' or 'destination_amenity_type' "
                "must be set (Entry #28)"
            )
        return self


class AmbiguousRequest(_StrictModel):
    """Multiple plausible matches — the agent asks a clarifying question."""

    type: Literal["ambiguous"] = "ambiguous"
    candidates: tuple[str, ...]
    clarification_question: str


class UnresolvableRequest(_StrictModel):
    """No landmark matches — falls back to a dropdown (Entry #5)."""

    type: Literal["unresolvable"] = "unresolvable"
    reason: str


NavigationParse = ResolvedRequest | AmbiguousRequest | UnresolvableRequest


# ---------------------------------------------------------------------------
# Profile extraction union (Entry #7)
# ---------------------------------------------------------------------------


class ProfileComplete(_StrictModel):
    """All required profile fields extracted successfully."""

    type: Literal["profile_complete"] = "profile_complete"
    seat_section: str
    accessibility_flags: tuple[AccessibilityFlag, ...] = Field(default_factory=tuple)
    preferred_language: PreferredLanguage = DEFAULT_LANGUAGE


class ProfileIncomplete(_StrictModel):
    """seat_section could not be extracted — ask a follow-up."""

    type: Literal["profile_incomplete"] = "profile_incomplete"
    missing: tuple[str, ...]
    followup_question: str


class ProfileFailed(_StrictModel):
    """Input was unusable (empty, gibberish, off-topic)."""

    type: Literal["profile_failed"] = "profile_failed"
    reason: str


ProfileExtraction = ProfileComplete | ProfileIncomplete | ProfileFailed
