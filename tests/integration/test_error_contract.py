"""Regression tests for Entry #23 flat-error shape at framework boundaries.

FastAPI internally raises ``starlette.exceptions.HTTPException`` (not
``fastapi.exceptions.HTTPException``) for framework-produced errors like
"unknown route" (404) and "method not allowed" (405). If only the FastAPI
class is registered with an exception handler, those framework errors leak
through as ``{"detail": "Not Found"}`` — not the flat Entry #23 shape.

This test file locks down that both classes are handled, and also that the
slowapi rate-limit handler emits the same flat shape.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import verify_fan_token
from app.main import app
from app.rate_limit import limiter
from tests.integration.conftest import FakeFirestoreClient


def test_unknown_route_returns_flat_error_shape() -> None:
    client = TestClient(app)
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
    assert "message" in body


def test_wrong_method_returns_flat_error_shape() -> None:
    client = TestClient(app)
    response = client.delete("/health")
    assert response.status_code == 405
    body = response.json()
    assert body["type"] == "error"
    assert body["category"] == "permanent"
    assert "message" in body


def test_rate_limit_exceeded_returns_transient_429(
    fake_firestore: FakeFirestoreClient, test_uid: str
) -> None:
    """FAN_LIMIT is 60/minute; the 61st call in a burst returns a flat 429."""
    limiter.reset()
    app.state.firestore_client_factory = lambda: fake_firestore
    app.dependency_overrides[verify_fan_token] = lambda: test_uid
    try:
        client = TestClient(app)
        headers = {"Authorization": "Bearer rate-limit-tok"}
        # First 60 requests are allowed; each returns 404 (no profile seeded).
        for _ in range(60):
            resp = client.get("/profile", headers=headers)
            assert resp.status_code == 404
        # 61st trips the limiter.
        blocked = client.get("/profile", headers=headers)
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["type"] == "error"
        assert body["category"] == "transient"
        assert body["message"] == "Rate limit exceeded."
    finally:
        app.dependency_overrides.clear()
        limiter.reset()


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    app.dependency_overrides.clear()
