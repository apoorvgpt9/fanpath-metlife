"""Tests for the Phase 0 FastAPI skeleton.

Covers real Phase 0 features only:
  * GET /health returns {"status": "ok"} with 200
  * Security headers appear on every response
  * ALLOWED_ORIGIN env var is parsed into a list of origins
  * ``load_dotenv()`` is wired and safe when no .env file is present
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main as main_module


def _client() -> TestClient:
    return TestClient(main_module.app)


def test_health_returns_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_are_set() -> None:
    response = _client().get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_health_route_has_no_trailing_slash_redirect() -> None:
    # redirect_slashes=False means /health/ should NOT 307 to /health.
    response = _client().get("/health/", follow_redirects=False)
    assert response.status_code == 404


def test_cors_origins_defaults_to_wildcard(monkeypatch) -> None:
    monkeypatch.delenv("ALLOWED_ORIGIN", raising=False)
    assert main_module._cors_origins() == ["*"]


def test_cors_origins_parses_comma_list(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGIN", "https://a.example.com, https://b.example.com")
    assert main_module._cors_origins() == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_origins_ignores_empty_entries(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGIN", "https://a.example.com,,  ,")
    assert main_module._cors_origins() == ["https://a.example.com"]


def test_module_reimport_is_stable() -> None:
    # Guard against side-effect surprises at import time.
    reloaded = importlib.reload(main_module)
    assert reloaded.app.title == "fanpath-metlife"


def test_module_imports_without_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Reimport app.main from a working directory that has no .env file.
    # load_dotenv() must be a safe no-op (returns False, no exception).
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("app.main", None)
    with patch("dotenv.load_dotenv", return_value=False) as spy:
        import app.main as reloaded_main  # noqa: F401

        spy.assert_called_once()
