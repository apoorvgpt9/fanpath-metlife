"""Unit tests for :mod:`app.auth.staff` — STAFF_TOKEN shared-secret guard."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import staff


def test_missing_env_var_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STAFF_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        staff.verify_staff_token("Bearer whatever")
    assert exc.value.status_code == 401
    assert exc.value.detail["category"] == "permanent"


def test_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    assert staff.verify_staff_token("Bearer hunter2") is None


def test_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException) as exc:
        staff.verify_staff_token("Bearer nope")
    assert exc.value.status_code == 401
    assert exc.value.detail["type"] == "error"


def test_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException) as exc:
        staff.verify_staff_token(None)
    assert exc.value.status_code == 401


def test_malformed_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException):
        staff.verify_staff_token("Basic abc")


def test_empty_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException):
        staff.verify_staff_token("Bearer ")


def test_error_payload_shape_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException) as exc:
        staff.verify_staff_token("Bearer wrong")
    assert exc.value.detail["detail"] is not None


def test_error_payload_shape_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "fanpath-metlife")
    monkeypatch.setenv("STAFF_TOKEN", "hunter2")
    with pytest.raises(HTTPException) as exc:
        staff.verify_staff_token("Bearer wrong")
    assert exc.value.detail["detail"] is None
