"""Unit tests for ``app.firestore.fans`` — profile write/read + validation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.firestore import fans


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
        assert name == fans.COLLECTION
        return self

    def document(self, uid: str):
        self._current_uid = uid
        return self

    def set(self, payload: dict) -> None:
        self.written = payload

    def get(self):
        return _MockDoc(self._initial)


def test_build_profile_document_matches_entry_15_schema() -> None:
    doc = fans.build_profile_document(
        seat_section="214",
        accessibility_flags=["wheelchair", "no_stairs"],
        preferred_language="es",
        now=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
    )
    assert set(doc.keys()) == {
        "seat_section",
        "accessibility_flags",
        "preferred_language",
        "created_at",
    }
    assert doc["seat_section"] == "214"
    assert doc["accessibility_flags"] == ["wheelchair", "no_stairs"]
    assert doc["preferred_language"] == "es"
    assert doc["created_at"] == "2026-07-13T12:00:00Z"


def test_build_profile_defaults_language_to_en() -> None:
    doc = fans.build_profile_document("101", [], now=datetime(2026, 1, 1, tzinfo=UTC))
    assert doc["preferred_language"] == "en"


def test_build_profile_rejects_invalid_flag() -> None:
    with pytest.raises(ValueError):
        fans.build_profile_document("101", ["nope"])


def test_build_profile_rejects_invalid_language() -> None:
    with pytest.raises(ValueError):
        fans.build_profile_document("101", [], preferred_language="zz")


def test_build_profile_rejects_empty_seat() -> None:
    with pytest.raises(ValueError):
        fans.build_profile_document("", [])


def test_write_profile_persists_to_client() -> None:
    client = _MockClient()
    fans.write_profile(
        client,
        uid="anon-1",
        seat_section="330",
        accessibility_flags=["stroller"],
        preferred_language="fr",
        now=datetime(2026, 7, 13, tzinfo=UTC),
    )
    assert client.written == {
        "seat_section": "330",
        "accessibility_flags": ["stroller"],
        "preferred_language": "fr",
        "created_at": "2026-07-13T00:00:00Z",
    }


def test_read_profile_returns_none_if_missing() -> None:
    client = _MockClient(initial=None)
    assert fans.read_profile(client, "unknown") is None


def test_read_profile_hydrates_dataclass() -> None:
    client = _MockClient(
        initial={
            "seat_section": "128",
            "accessibility_flags": ["wheelchair"],
            "preferred_language": "ar",
            "created_at": "2026-07-13T09:00:00Z",
        }
    )
    profile = fans.read_profile(client, "anon-2")
    assert profile is not None
    assert profile.seat_section == "128"
    assert profile.accessibility_flags[0].value == "wheelchair"
    assert profile.preferred_language.value == "ar"
    assert profile.created_at == "2026-07-13T09:00:00Z"
