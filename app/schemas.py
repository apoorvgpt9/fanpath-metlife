"""Request/response Pydantic models for the six-endpoint API surface.

Kept in a top-level ``app/schemas.py`` module (vs. ``app/agents/schemas.py``,
which owns the agent-output discriminated unions). The two files exist for
different consumers:

* ``app.agents.schemas`` — model boundary; the Intent and Guide Agents produce
  and validate these shapes.
* ``app.schemas`` (this file) — HTTP boundary; FastAPI validates against
  these shapes.

Wiring is thin: several response models mirror agent unions verbatim so the
endpoint can pass them straight through (Entry #17 style: ``RouteBlocked`` and
ambiguous parses are not errors, they are legitimate response bodies).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.schemas import ConversationTurn
from app.models.enums import AccessibilityFlag, PreferredLanguage


class _StrictModel(BaseModel):
    """Base model that rejects unknown fields (``extra="forbid"``)."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# /profile (POST + GET)
# ---------------------------------------------------------------------------


class ProfileOnboardRequest(_StrictModel):
    """Fan's natural-language onboarding message (``POST /profile``)."""

    nl_input: str


class ProfileResponse(_StrictModel):
    """Mirrors :class:`app.firestore.fans.FanProfile`."""

    uid: str
    seat_section: str
    accessibility_flags: list[AccessibilityFlag]
    preferred_language: PreferredLanguage
    created_at: str


class ProfileIncompleteResponse(_StrictModel):
    """Emitted when the Intent Agent returns ``ProfileIncomplete``."""

    type: Literal["profile_incomplete"] = "profile_incomplete"
    missing: list[str]
    followup_question: str


class ProfileFailedResponse(_StrictModel):
    """Emitted when the Intent Agent returns ``ProfileFailed``."""

    type: Literal["profile_failed"] = "profile_failed"
    reason: str


# ---------------------------------------------------------------------------
# /navigate (POST)
# ---------------------------------------------------------------------------


class NavigateRequest(_StrictModel):
    """Fan query plus the last 3 conversation turns (``POST /navigate``)."""

    query: str
    history: list[ConversationTurn] = Field(default_factory=list)


class NavigateResponse(_StrictModel):
    """Directions plus (in Phase 4B) the base64 SVG. Phase 4A leaves it None."""

    directions: str
    route_image: str | None = None


# ---------------------------------------------------------------------------
# /staff/closures (POST + GET)
# ---------------------------------------------------------------------------


class ClosureToggleRequest(_StrictModel):
    """Staff closure toggle — close or open a node/edge (``POST /staff/closures``)."""

    target_id: str
    target_type: Literal["node", "edge"]
    action: Literal["close", "open"]


class ClosureStateResponse(_StrictModel):
    """Current closure state snapshot (``GET/POST /staff/closures``)."""

    closed_nodes: list[str]
    closed_edges: list[str]
    updated_at: str


# ---------------------------------------------------------------------------
# Error contract (Entry #23) — for OpenAPI schema documentation only. Actual
# error responses are emitted via :func:`app.errors.raise_error`, which uses
# ``HTTPException.detail`` under the custom handler in ``app.main``.
# ---------------------------------------------------------------------------


class ErrorResponse(_StrictModel):
    """Two-category error envelope (Entry #23). For OpenAPI schema only."""

    type: Literal["error"] = "error"
    category: Literal["transient", "permanent"]
    message: str
    detail: str | None = None


__all__ = [
    "ClosureStateResponse",
    "ClosureToggleRequest",
    "ErrorResponse",
    "NavigateRequest",
    "NavigateResponse",
    "ProfileFailedResponse",
    "ProfileIncompleteResponse",
    "ProfileOnboardRequest",
    "ProfileResponse",
]
