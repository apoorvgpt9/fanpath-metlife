"""Unit tests for :mod:`app.errors` — Entry #23 error contract."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.errors import error_payload, is_error_payload, raise_error


def test_payload_includes_detail_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    payload = error_payload("permanent", "boom", "raw traceback")
    assert payload == {
        "type": "error",
        "category": "permanent",
        "message": "boom",
        "detail": "raw traceback",
    }


def test_payload_hides_detail_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "fanpath-metlife")
    payload = error_payload("transient", "network flaky", "internal stack trace")
    assert payload["detail"] is None
    assert payload["message"] == "network flaky"


def test_payload_detail_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    payload = error_payload("permanent", "not found")
    assert payload["detail"] is None


def test_is_error_payload_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert is_error_payload(error_payload("transient", "x", "y")) is True


def test_is_error_payload_negative() -> None:
    assert is_error_payload("plain string") is False
    assert is_error_payload({"foo": "bar"}) is False
    assert is_error_payload({"type": "not-error"}) is False
    assert is_error_payload({"type": "error", "category": "weird", "message": "m"}) is False


def test_raise_error_wraps_http_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    with pytest.raises(HTTPException) as exc:
        raise_error(404, "permanent", "gone", "not on disk")
    assert exc.value.status_code == 404
    assert exc.value.detail["type"] == "error"
    assert exc.value.detail["detail"] == "not on disk"
