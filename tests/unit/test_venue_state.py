"""Unit tests for ``app.firestore.venue_state`` — closure state read/write."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.firestore import venue_state


class _MockDoc:
    def __init__(self, data: dict | None):
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict | None:
        return self._data


class _MockClient:
    def __init__(self, initial: dict | None = None) -> None:
        self.written: dict | None = None
        self._initial = initial
        self.collection = MagicMock(side_effect=self._collection)

    def _collection(self, name: str):
        assert name == venue_state.COLLECTION
        return self

    def document(self, doc_id: str):
        assert doc_id == venue_state.DOCUMENT_ID
        return self

    def set(self, payload: dict) -> None:
        self.written = payload

    def get(self):
        return _MockDoc(self._initial)


def test_read_state_returns_empty_when_missing() -> None:
    state = venue_state.read_state(_MockClient(initial=None))
    assert state.closed_nodes == ()
    assert state.closed_edges == ()
    assert state.updated_at == ""


def test_read_state_hydrates_document() -> None:
    client = _MockClient(
        initial={
            "closed_nodes": ["gate_b_plaza"],
            "closed_edges": ["concourse_100_east<->coaches_club"],
            "updated_at": "2026-07-13T15:00:00Z",
        }
    )
    state = venue_state.read_state(client)
    assert state.closed_nodes == ("gate_b_plaza",)
    assert state.closed_edges == ("concourse_100_east<->coaches_club",)
    assert state.updated_at == "2026-07-13T15:00:00Z"


def test_write_state_persists_sorted_deduped() -> None:
    client = _MockClient()
    payload = venue_state.write_state(
        client,
        closed_nodes=["gate_b_plaza", "gate_a_plaza", "gate_b_plaza"],
        closed_edges=["e1", "e2", "e1"],
        now=datetime(2026, 7, 13, 15, 0, tzinfo=UTC),
    )
    assert client.written == payload
    assert payload == {
        "closed_nodes": ["gate_a_plaza", "gate_b_plaza"],
        "closed_edges": ["e1", "e2"],
        "updated_at": "2026-07-13T15:00:00Z",
    }


def test_write_state_rejects_non_string_ids() -> None:
    client = _MockClient()
    with pytest.raises(ValueError):
        venue_state.write_state(client, closed_nodes=["ok", 3], closed_edges=[])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        venue_state.write_state(client, closed_nodes=[], closed_edges=[None])  # type: ignore[list-item]
