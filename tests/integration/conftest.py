"""Shared fixtures for Layer-4 integration tests.

Exposes a fake Firestore client that mirrors just enough of the real API
surface for ``app.firestore.fans`` and ``app.firestore.venue_state`` to work
against it, plus an ``integration_client`` fixture that builds a
``TestClient`` with:

* Firestore replaced with the fake.
* :func:`app.auth.firebase.verify_fan_token` overridden to return a fixed UID.
* :func:`app.auth.staff.verify_staff_token` left in place; tests set
  ``STAFF_TOKEN`` and pass a matching Authorization header.

The real graph is loaded via ``load_default_graph()`` — no fixture graph.
Gemini boundary mocking is per-test.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.firebase import verify_fan_token
from app.firestore import fans as fans_repo
from app.firestore import venue_state as venue_repo


class _Doc:
    def __init__(self, store: dict, key: str) -> None:
        self._store = store
        self._key = key

    @property
    def exists(self) -> bool:
        return self._key in self._store

    def to_dict(self) -> dict | None:
        data = self._store.get(self._key)
        return dict(data) if data else None


class _DocRef:
    def __init__(self, store: dict, key: str) -> None:
        self._store = store
        self._key = key

    def get(self) -> _Doc:
        return _Doc(self._store, self._key)

    def set(self, payload: dict) -> None:
        self._store[self._key] = dict(payload)


class _Collection:
    def __init__(self, store: dict[str, dict[str, Any]], name: str) -> None:
        self._store = store
        self._name = name

    def document(self, doc_id: str) -> _DocRef:
        self._store.setdefault(self._name, {})
        return _DocRef(self._store[self._name], doc_id)


class FakeFirestoreClient:
    """In-memory Firestore stand-in for integration tests."""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> _Collection:
        return _Collection(self.data, name)

    def seed_profile(self, uid: str, profile: dict) -> None:
        self.data.setdefault(fans_repo.COLLECTION, {})[uid] = dict(profile)

    def seed_venue_state(self, payload: dict) -> None:
        self.data.setdefault(venue_repo.COLLECTION, {})[venue_repo.DOCUMENT_ID] = dict(payload)


@pytest.fixture
def fake_firestore() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def test_uid() -> str:
    return "anon-uid-integration"


@pytest.fixture
def integration_client(
    fake_firestore: FakeFirestoreClient, test_uid: str
) -> TestClient:
    from app.main import app

    app.state.firestore_client_factory = lambda: fake_firestore
    app.dependency_overrides[verify_fan_token] = lambda: test_uid
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
