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

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DEFAULT_LANGUAGE, AccessibilityFlag, PreferredLanguage


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# Conversation memory (Entry #10)
# ---------------------------------------------------------------------------


class ConversationTurn(_StrictModel):
    role: Literal["fan", "guide"]
    content: str


# ---------------------------------------------------------------------------
# Navigation parse union (Entry #9)
# ---------------------------------------------------------------------------


class ResolvedRequest(_StrictModel):
    type: Literal["resolved"] = "resolved"
    origin: str
    destination: str
    rationale: str = ""


class AmbiguousRequest(_StrictModel):
    type: Literal["ambiguous"] = "ambiguous"
    candidates: tuple[str, ...]
    clarification_question: str


class UnresolvableRequest(_StrictModel):
    type: Literal["unresolvable"] = "unresolvable"
    reason: str


NavigationParse = ResolvedRequest | AmbiguousRequest | UnresolvableRequest


# ---------------------------------------------------------------------------
# Profile extraction union (Entry #7)
# ---------------------------------------------------------------------------


class ProfileComplete(_StrictModel):
    type: Literal["profile_complete"] = "profile_complete"
    seat_section: str
    accessibility_flags: tuple[AccessibilityFlag, ...] = Field(default_factory=tuple)
    preferred_language: PreferredLanguage = DEFAULT_LANGUAGE


class ProfileIncomplete(_StrictModel):
    type: Literal["profile_incomplete"] = "profile_incomplete"
    missing: tuple[str, ...]
    followup_question: str


class ProfileFailed(_StrictModel):
    type: Literal["profile_failed"] = "profile_failed"
    reason: str


ProfileExtraction = ProfileComplete | ProfileIncomplete | ProfileFailed
