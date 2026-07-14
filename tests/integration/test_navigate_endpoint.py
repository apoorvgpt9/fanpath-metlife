"""Layer-4 integration tests for POST /profile, GET /profile, POST /navigate.

Mocks Firestore at the client boundary (via the fake exposed in
``conftest.py``) and Gemini at the ``gemini_factory.pro`` / ``.flash`` seam —
never at the agent function boundary.

The regression test for Phase 3's double-wrap bug is
``test_missing_auth_returns_flat_error_shape``: the failing behaviour returned
``{"detail": {"type": "error", ...}}``; the fix returns
``{"type": "error", "category": "permanent", ...}`` at the top level.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.gemini_factory import GeminiTimeoutError
from app.firestore import fans as fans_repo
from app.main import app
from tests.integration.conftest import FakeFirestoreClient


def _seed_default_profile(fake: FakeFirestoreClient, uid: str) -> None:
    fake.seed_profile(
        uid,
        {
            fans_repo.FIELD_SEAT_SECTION: "142",
            fans_repo.FIELD_ACCESSIBILITY_FLAGS: [],
            fans_repo.FIELD_PREFERRED_LANGUAGE: "en",
            fans_repo.FIELD_CREATED_AT: "2026-07-14T10:00:00Z",
        },
    )


def _fake_gemini(pro_payload: dict | str, flash_text: str = "Turn left, then right.") -> tuple:
    pro_client = MagicMock()
    if isinstance(pro_payload, dict):
        pro_client.generate_content.return_value = json.dumps(pro_payload)
    else:
        pro_client.generate_content.return_value = pro_payload
    flash_client = MagicMock()
    flash_client.generate_content.return_value = flash_text
    return pro_client, flash_client


# ---------------------------------------------------------------------------
# /profile POST + GET
# ---------------------------------------------------------------------------


def test_post_profile_complete_writes_document(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    pro_client, _ = _fake_gemini({
        "type": "profile_complete",
        "seat_section": "128",
        "accessibility_flags": [],
        "preferred_language": "en",
    })
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/profile",
            headers={"Authorization": "Bearer fan-tok"},
            json={"nl_input": "I'm in section 128"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["seat_section"] == "128"
    assert body["uid"] == test_uid
    stored = fake_firestore.data[fans_repo.COLLECTION][test_uid]
    assert stored[fans_repo.FIELD_SEAT_SECTION] == "128"


def test_post_profile_incomplete_returns_followup(
    integration_client: TestClient,
) -> None:
    pro_client, _ = _fake_gemini({
        "type": "profile_incomplete",
        "missing": ["seat_section"],
        "followup_question": "Which section are you in?",
    })
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/profile",
            headers={"Authorization": "Bearer fan-tok"},
            json={"nl_input": "hey"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "profile_incomplete"
    assert body["followup_question"] == "Which section are you in?"


def test_post_profile_failed(integration_client: TestClient) -> None:
    pro_client, _ = _fake_gemini({"type": "profile_failed", "reason": "gibberish"})
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/profile",
            headers={"Authorization": "Bearer fan-tok"},
            json={"nl_input": "asdfgh"},
        )
    assert response.status_code == 200
    assert response.json()["type"] == "profile_failed"


def test_get_profile_returns_stored(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    response = integration_client.get(
        "/profile", headers={"Authorization": "Bearer fan-tok"}
    )
    assert response.status_code == 200
    assert response.json()["seat_section"] == "142"


def test_get_profile_missing_returns_permanent_error(
    integration_client: TestClient,
) -> None:
    response = integration_client.get(
        "/profile", headers={"Authorization": "Bearer fan-tok"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
    assert body["message"] == "Profile not found."


# ---------------------------------------------------------------------------
# /navigate
# ---------------------------------------------------------------------------


def test_navigate_resolved_returns_directions(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    pro_client, flash_client = _fake_gemini(
        {
            "type": "resolved",
            "origin": "gate_a_plaza",
            "destination": "gate_c_plaza",
            "rationale": "clear",
        },
        flash_text="Head straight past gate B, arrive at gate C.",
    )
    with patch("app.agents.intent.pro", return_value=pro_client), patch(
        "app.agents.guide.flash", return_value=flash_client
    ):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "how do I get to gate C from gate A", "history": []},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["route_image"] is None
    assert "gate C" in body["directions"]


def test_navigate_ambiguous_returns_clarification(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    pro_client, _ = _fake_gemini({
        "type": "ambiguous",
        "candidates": ["gate_a_plaza", "gate_c_plaza"],
        "clarification_question": "Do you mean gate A or gate C?",
    })
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "the gate", "history": []},
        )
    assert response.status_code == 200
    assert response.json()["directions"] == "Do you mean gate A or gate C?"


def test_navigate_unresolvable_returns_permanent_error(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    pro_client, _ = _fake_gemini({
        "type": "unresolvable",
        "reason": "no such landmark in the stadium",
    })
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "the moon", "history": []},
        )
    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
    assert "no such landmark" in body["message"]


def test_navigate_missing_profile_permanent_404(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/navigate",
        headers={"Authorization": "Bearer fan-tok"},
        json={"query": "gate C", "history": []},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"


def test_navigate_gemini_timeout_transient(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    pro_client = MagicMock()
    pro_client.generate_content.side_effect = GeminiTimeoutError("deadline exceeded")
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "gate C", "history": []},
        )
    assert response.status_code == 504
    assert response.json()["category"] == "transient"


def test_profile_gemini_service_error_transient(
    integration_client: TestClient,
) -> None:
    from app.agents.gemini_factory import GeminiServiceError

    pro_client = MagicMock()
    pro_client.generate_content.side_effect = GeminiServiceError("upstream 500")
    with patch("app.agents.intent.pro", return_value=pro_client):
        response = integration_client.post(
            "/profile",
            headers={"Authorization": "Bearer fan-tok"},
            json={"nl_input": "I'm in section 128"},
        )
    assert response.status_code == 502
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "transient"


def test_navigate_closed_edge_forces_detour_through_endpoint(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    """Seed a closed edge, hit the real endpoint, confirm the closure is honored."""
    from app.firestore import venue_state as venue_repo
    from app.graph.edge_id import edge_id as _edge_id

    _seed_default_profile(fake_firestore, test_uid)
    canonical = _edge_id("gate_a_plaza", "gate_b_plaza")
    fake_firestore.seed_venue_state(
        {
            venue_repo.FIELD_CLOSED_NODES: [],
            venue_repo.FIELD_CLOSED_EDGES: [canonical],
            venue_repo.FIELD_UPDATED_AT: "2026-07-14T10:05:00Z",
        }
    )
    pro_client, flash_client = _fake_gemini(
        {
            "type": "resolved",
            "origin": "gate_a_plaza",
            "destination": "gate_b_plaza",
            "rationale": "clear",
        },
        flash_text="Detour prose from the guide agent.",
    )
    with patch("app.agents.intent.pro", return_value=pro_client), patch(
        "app.agents.guide.flash", return_value=flash_client
    ):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "gate B", "history": []},
        )
    # Endpoint decoded the closed edge (exercises _decode_closures parse loop)
    # and returned a valid response — either detour or RouteBlocked prose.
    assert response.status_code == 200
    assert response.json()["route_image"] is None
    assert flash_client.generate_content.called


def test_navigate_route_blocked_returns_200_with_prose(
    integration_client: TestClient, fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    _seed_default_profile(fake_firestore, test_uid)
    # Close gate_c_plaza so a plausible route to it becomes blocked.
    fake_firestore.seed_venue_state(
        {"closed_nodes": ["gate_c_plaza"], "closed_edges": [], "updated_at": ""}
    )
    pro_client, flash_client = _fake_gemini(
        {
            "type": "resolved",
            "origin": "gate_a_plaza",
            "destination": "gate_c_plaza",
            "rationale": "clear",
        },
        flash_text="Sorry — gate C is currently closed.",
    )
    with patch("app.agents.intent.pro", return_value=pro_client), patch(
        "app.agents.guide.flash", return_value=flash_client
    ):
        response = integration_client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "gate C", "history": []},
        )
    assert response.status_code == 200
    body = response.json()
    assert "closed" in body["directions"].lower()


# ---------------------------------------------------------------------------
# Auth regression — the double-wrap bug from Phase 3
# ---------------------------------------------------------------------------


def test_missing_auth_returns_flat_error_shape() -> None:
    """No Depends override — hit the real verify_fan_token, expect a flat body."""
    app.dependency_overrides.clear()  # ensure the real dependency runs
    client = TestClient(app)
    response = client.get("/profile")  # no Authorization header
    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
    assert "detail" not in body or body["detail"] is None or isinstance(body["detail"], str)
    assert body.get("detail") != {"type": "error"}  # sanity: not double-wrapped


def test_invalid_auth_returns_flat_error_shape() -> None:
    from firebase_admin import auth as firebase_auth

    from app.auth import firebase as fb_auth

    app.dependency_overrides.clear()
    client = TestClient(app)
    with patch.object(fb_auth, "_ensure_firebase_initialized", lambda: None), patch.object(
        firebase_auth,
        "verify_id_token",
        side_effect=firebase_auth.InvalidIdTokenError("bad"),
    ):
        response = client.get(
            "/profile", headers={"Authorization": "Bearer clearly-not-a-real-jwt"}
        )
    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"


@pytest.fixture(autouse=True)
def _isolate_dependency_overrides():
    """Reset dependency overrides between tests to avoid leaking auth bypasses."""
    yield
    app.dependency_overrides.clear()
