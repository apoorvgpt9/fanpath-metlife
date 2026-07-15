"""Coverage top-up for defensive branches across main/rate_limit/routes.

These branches exist for genuine failure modes but require targeted setup —
kept in one small file so the mocking stays scoped.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app import main as app_main
from app.rate_limit import rate_limit_key


def test_http_exception_handler_dict_but_not_error_payload_shape() -> None:
    """A ``dict`` detail that fails ``is_error_payload`` is passed through as JSON."""
    request = MagicMock(spec=Request)
    exc = HTTPException(status_code=400, detail={"foo": "bar"})
    response = asyncio.run(app_main._http_exception_handler(request, exc))
    assert response.status_code == 400
    assert b'"foo":"bar"' in response.body


def test_create_app_skips_static_mount_when_directory_missing(monkeypatch) -> None:
    """The static mount branch is skipped when ``static/`` does not exist."""
    missing = Path("/tmp/definitely-not-a-real-static-dir-xyz")
    monkeypatch.setattr(app_main, "_STATIC_DIR", missing)
    with patch.object(app_main, "load_default_graph", return_value=object()):
        app = app_main.create_app()
    assert not any(route.path == "/static" for route in app.routes if hasattr(route, "path"))


def test_rate_limit_key_falls_back_to_ip_when_no_auth_header() -> None:
    """Requests without an Authorization header key on the client IP."""
    scope = {
        "type": "http",
        "headers": [],
        "client": ("1.2.3.4", 55555),
    }
    request = Request(scope)
    key = rate_limit_key(request)
    assert key.startswith("ip:")


def test_navigate_500s_when_venue_state_has_malformed_edge_id(
    fake_firestore, test_uid, integration_client
) -> None:
    """A malformed ``closed_edges`` entry surfaces the Entry #23 500 payload."""
    from app.firestore import fans as fans_repo

    fake_firestore.seed_profile(
        test_uid,
        {
            fans_repo.FIELD_SEAT_SECTION: "111",
            fans_repo.FIELD_ACCESSIBILITY_FLAGS: [],
            fans_repo.FIELD_PREFERRED_LANGUAGE: "en",
            fans_repo.FIELD_CREATED_AT: "2026-07-15T12:00:00Z",
        },
    )
    fake_firestore.seed_venue_state(
        {
            "closed_nodes": [],
            "closed_edges": ["totally-not-a-valid-edge-id"],
            "updated_at": "2026-07-15T12:00:00Z",
        }
    )
    response = integration_client.post(
        "/navigate",
        json={"query": "how do I get to the bathroom", "history": []},
        headers={"Authorization": "Bearer x"},
    )
    assert response.status_code == 500
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
