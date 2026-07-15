"""Layer-2 unit tests for :mod:`app.routes` helpers.

Covers branches that are hard or impossible to reach through the live endpoint
against the real graph:

* ``_handle_navigation_parse`` on a ``RouteImpossible`` result. The real
  MetLife graph is fully connected (see ``scripts/verify_graph.py``), so this
  branch can't be reached through the endpoint with real data — but the
  branch still needs regression coverage.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.agents.schemas import ResolvedRequest
from app.firestore import fans as fans_repo
from app.models.enums import AccessibilityFlag, PreferredLanguage
from app.pathfinding.engine import RouteImpossible
from app.routes import _handle_navigation_parse
from app.schemas import NavigateRequest


def _profile() -> fans_repo.FanProfile:
    return fans_repo.FanProfile(
        uid="uid-unit",
        seat_section="142",
        accessibility_flags=(AccessibilityFlag.WHEELCHAIR,),
        preferred_language=PreferredLanguage.EN,
        created_at="2026-07-14T10:00:00Z",
    )


def test_handle_navigation_parse_route_impossible_raises_permanent_400(monkeypatch) -> None:
    """RouteImpossible must map to a permanent 400 per Entry #23."""
    parsed = ResolvedRequest(
        origin="a", destination="b", rationale="clear"
    )
    body = NavigateRequest(query="how do I get there", history=[])
    profile = _profile()

    def _fake_find_route(*args, **kwargs):
        return RouteImpossible(
            origin="a",
            destination="b",
            reason="graph is disconnected under accessibility",
        )

    monkeypatch.setattr("app.routes.find_route", _fake_find_route)

    import asyncio

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            _handle_navigation_parse(
                parsed, body, profile, graph=object(), closed_nodes=set(), closed_edges=set()
            )
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["type"] == "error"
    assert detail["category"] == "permanent"
