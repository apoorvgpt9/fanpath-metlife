"""Unit tests for the Firebase Anonymous Auth dependency."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from firebase_admin import auth as firebase_auth

from app.auth import firebase as fb_auth


@pytest.fixture(autouse=True)
def _skip_firebase_init():
    with patch.object(fb_auth, "_ensure_firebase_initialized", lambda: None):
        yield


def test_success_returns_uid() -> None:
    with patch.object(
        firebase_auth, "verify_id_token", return_value={"uid": "anon-uid-42"}
    ):
        assert fb_auth.verify_fan_token("Bearer good.token") == "anon-uid-42"


def test_missing_header_raises_401_permanent() -> None:
    with pytest.raises(HTTPException) as exc:
        fb_auth.verify_fan_token(None)
    assert exc.value.status_code == 401
    assert exc.value.detail["category"] == "permanent"
    assert exc.value.detail["type"] == "error"


def test_malformed_header_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        fb_auth.verify_fan_token("Basic abc")
    assert exc.value.status_code == 401


def test_empty_bearer_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        fb_auth.verify_fan_token("Bearer ")
    assert exc.value.status_code == 401


def test_invalid_token_raises_401() -> None:
    with patch.object(
        firebase_auth,
        "verify_id_token",
        side_effect=firebase_auth.InvalidIdTokenError("bad"),
    ):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer bad.token")
        assert exc.value.status_code == 401
        assert exc.value.detail["category"] == "permanent"


def test_expired_token_raises_401() -> None:
    with patch.object(
        firebase_auth,
        "verify_id_token",
        side_effect=firebase_auth.ExpiredIdTokenError("expired", cause=None),
    ):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer old.token")
        assert exc.value.status_code == 401


def test_value_error_is_wrapped() -> None:
    with patch.object(firebase_auth, "verify_id_token", side_effect=ValueError("bad")):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer weird.token")
        assert exc.value.status_code == 401


def test_missing_uid_in_decoded_raises_401() -> None:
    with patch.object(firebase_auth, "verify_id_token", return_value={}):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer good.token")
        assert exc.value.status_code == 401


def test_detail_populated_locally_but_not_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    with patch.object(
        firebase_auth,
        "verify_id_token",
        side_effect=firebase_auth.InvalidIdTokenError("bad"),
    ):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer bad.token")
        assert exc.value.detail["detail"] is not None

    monkeypatch.setenv("K_SERVICE", "fanpath-metlife")
    with patch.object(
        firebase_auth,
        "verify_id_token",
        side_effect=firebase_auth.InvalidIdTokenError("bad"),
    ):
        with pytest.raises(HTTPException) as exc:
            fb_auth.verify_fan_token("Bearer bad.token")
        assert exc.value.detail["detail"] is None
