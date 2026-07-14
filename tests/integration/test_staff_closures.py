"""Layer-4 integration tests for POST /staff/closures and GET /staff/closures.

Verifies:
* Closing a node is reflected in a subsequent GET and in downstream
  ``/navigate`` state.
* Closing an edge round-trips through :func:`app.graph.edge_id.edge_id`.
* Invalid ``target_id`` (unknown zone or edge) is rejected with a permanent
  error — not silently accepted.
* Missing / wrong ``STAFF_TOKEN`` returns 401 with a flat Entry #23 body.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import verify_fan_token
from app.firestore import venue_state as venue_repo
from app.graph.edge_id import edge_id
from app.main import app
from tests.integration.conftest import FakeFirestoreClient

_STAFF = "shared-staff-token-under-test"
_HDR = {"Authorization": f"Bearer {_STAFF}"}


@pytest.fixture(autouse=True)
def _staff_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAFF_TOKEN", _STAFF)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def staff_client(fake_firestore: FakeFirestoreClient) -> TestClient:
    app.state.firestore_client_factory = lambda: fake_firestore
    return TestClient(app)


# ---------------------------------------------------------------------------
# Happy path — node closure
# ---------------------------------------------------------------------------


def test_close_node_reflected_in_get(
    staff_client: TestClient, fake_firestore: FakeFirestoreClient
) -> None:
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": "gate_a_plaza", "target_type": "node", "action": "close"},
    )
    assert response.status_code == 200
    assert "gate_a_plaza" in response.json()["closed_nodes"]

    read = staff_client.get("/staff/closures", headers=_HDR)
    assert read.status_code == 200
    assert "gate_a_plaza" in read.json()["closed_nodes"]

    stored = fake_firestore.data[venue_repo.COLLECTION][venue_repo.DOCUMENT_ID]
    assert "gate_a_plaza" in stored[venue_repo.FIELD_CLOSED_NODES]


def test_open_removes_closure(
    staff_client: TestClient, fake_firestore: FakeFirestoreClient
) -> None:
    fake_firestore.seed_venue_state(
        {
            venue_repo.FIELD_CLOSED_NODES: ["gate_a_plaza"],
            venue_repo.FIELD_CLOSED_EDGES: [],
            venue_repo.FIELD_UPDATED_AT: "2026-07-14T09:00:00Z",
        }
    )
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": "gate_a_plaza", "target_type": "node", "action": "open"},
    )
    assert response.status_code == 200
    assert "gate_a_plaza" not in response.json()["closed_nodes"]


# ---------------------------------------------------------------------------
# Happy path — edge closure round-trips through edge_id
# ---------------------------------------------------------------------------


def test_close_edge_uses_canonical_id(
    staff_client: TestClient, fake_firestore: FakeFirestoreClient
) -> None:
    # gate_a_plaza <-> gate_b_plaza is a real edge in the metlife graph.
    canonical = edge_id("gate_a_plaza", "gate_b_plaza")
    # Send the edge id with the reversed pair — server must canonicalize it.
    reversed_id = "gate_b_plaza__gate_a_plaza"
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": reversed_id, "target_type": "edge", "action": "close"},
    )
    assert response.status_code == 200
    assert canonical in response.json()["closed_edges"]


def test_close_edge_persists_to_firestore(
    staff_client: TestClient, fake_firestore: FakeFirestoreClient
) -> None:
    canonical = edge_id("gate_a_plaza", "gate_b_plaza")
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": canonical, "target_type": "edge", "action": "close"},
    )
    assert response.status_code == 200
    stored = fake_firestore.data[venue_repo.COLLECTION][venue_repo.DOCUMENT_ID]
    assert canonical in stored[venue_repo.FIELD_CLOSED_EDGES]


def test_open_edge_removes_closure(
    staff_client: TestClient, fake_firestore: FakeFirestoreClient
) -> None:
    canonical = edge_id("gate_a_plaza", "gate_b_plaza")
    fake_firestore.seed_venue_state(
        {
            venue_repo.FIELD_CLOSED_NODES: [],
            venue_repo.FIELD_CLOSED_EDGES: [canonical],
            venue_repo.FIELD_UPDATED_AT: "2026-07-14T09:00:00Z",
        }
    )
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": canonical, "target_type": "edge", "action": "open"},
    )
    assert response.status_code == 200
    assert canonical not in response.json()["closed_edges"]
    stored = fake_firestore.data[venue_repo.COLLECTION][venue_repo.DOCUMENT_ID]
    assert canonical not in stored[venue_repo.FIELD_CLOSED_EDGES]


def test_close_edge_visible_to_navigate(
    fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    """The pathfinding layer must observe the closure via the fresh read."""
    from app.pathfinding.engine import find_route

    canonical = edge_id("gate_a_plaza", "gate_b_plaza")
    fake_firestore.seed_venue_state(
        {
            venue_repo.FIELD_CLOSED_NODES: [],
            venue_repo.FIELD_CLOSED_EDGES: [canonical],
            venue_repo.FIELD_UPDATED_AT: "2026-07-14T09:00:00Z",
        }
    )
    from app.graph.edge_id import parse_edge_id

    state = venue_repo.read_state(fake_firestore)
    decoded = {parse_edge_id(e) for e in state.closed_edges}
    assert ("gate_a_plaza", "gate_b_plaza") in decoded

    # Confirm find_route sees the closure — the edge is truly excluded from adj.
    graph = app.state.graph
    result = find_route(
        graph,
        origin="gate_a_plaza",
        destination="gate_b_plaza",
        accessibility_flags=[],
        closed_nodes=set(state.closed_nodes),
        closed_edges=decoded,
    )
    # Direct edge gone; either RouteBlocked or a detour path (longer).
    from app.pathfinding.engine import RouteBlocked, RouteFound

    assert isinstance(result, (RouteFound, RouteBlocked))
    if isinstance(result, RouteFound):
        assert result.nodes != ("gate_a_plaza", "gate_b_plaza")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_unknown_node_target_rejected(staff_client: TestClient) -> None:
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": "does_not_exist", "target_type": "node", "action": "close"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"


def test_unknown_edge_target_rejected(staff_client: TestClient) -> None:
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={
            "target_id": edge_id("gate_a_plaza", "nowhere_zone"),
            "target_type": "edge",
            "action": "close",
        },
    )
    assert response.status_code == 400
    assert response.json()["category"] == "permanent"


def test_edge_between_real_but_nonadjacent_nodes_rejected(staff_client: TestClient) -> None:
    # gate_a_plaza and gate_c_plaza are real zones but not directly connected.
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={
            "target_id": edge_id("gate_a_plaza", "gate_c_plaza"),
            "target_type": "edge",
            "action": "close",
        },
    )
    assert response.status_code == 400
    assert response.json()["category"] == "permanent"


def test_malformed_edge_id_rejected(staff_client: TestClient) -> None:
    response = staff_client.post(
        "/staff/closures",
        headers=_HDR,
        json={"target_id": "no-double-underscore", "target_type": "edge", "action": "close"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_staff_token_rejected(staff_client: TestClient) -> None:
    response = staff_client.get("/staff/closures")  # no Authorization
    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"


def test_wrong_staff_token_rejected(staff_client: TestClient) -> None:
    response = staff_client.get(
        "/staff/closures", headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 401
    assert response.json()["type"] == "error"


# ---------------------------------------------------------------------------
# End-to-end: closure applied to /navigate through the real dependency chain.
# ---------------------------------------------------------------------------


def test_closure_visible_to_navigate_endpoint(
    fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    from app.firestore import fans as fans_repo

    app.state.firestore_client_factory = lambda: fake_firestore
    app.dependency_overrides[verify_fan_token] = lambda: test_uid

    fake_firestore.seed_profile(
        test_uid,
        {
            fans_repo.FIELD_SEAT_SECTION: "142",
            fans_repo.FIELD_ACCESSIBILITY_FLAGS: [],
            fans_repo.FIELD_PREFERRED_LANGUAGE: "en",
            fans_repo.FIELD_CREATED_AT: "2026-07-14T10:00:00Z",
        },
    )
    fake_firestore.seed_venue_state(
        {
            venue_repo.FIELD_CLOSED_NODES: ["gate_b_plaza"],
            venue_repo.FIELD_CLOSED_EDGES: [],
            venue_repo.FIELD_UPDATED_AT: "2026-07-14T10:05:00Z",
        }
    )

    import json as _json
    from unittest.mock import MagicMock

    pro_client = MagicMock()
    pro_client.generate_content.return_value = _json.dumps(
        {
            "type": "resolved",
            "origin": "gate_a_plaza",
            "destination": "gate_c_plaza",
            "rationale": "clear",
        }
    )
    flash_client = MagicMock()
    flash_client.generate_content.return_value = "Take the plaza walkway."

    client = TestClient(app)
    with patch("app.agents.intent.pro", return_value=pro_client), patch(
        "app.agents.guide.flash", return_value=flash_client
    ):
        response = client.post(
            "/navigate",
            headers={"Authorization": "Bearer fan-tok"},
            json={"query": "how do I reach gate C from gate A", "history": []},
        )
    assert response.status_code == 200
    body = response.json()
    # Route found around the closure — Phase 4B renders an SVG data URI here.
    assert isinstance(body["route_image"], str)
    assert body["route_image"].startswith("data:image/svg+xml;base64,")
