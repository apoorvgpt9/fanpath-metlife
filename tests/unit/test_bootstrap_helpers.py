"""Coverage top-up for firebase init + firestore default client factory.

These wrap third-party call sites that are impractical to touch in the main
unit test suites; kept in a dedicated file so the mocking is scoped tightly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import firebase_admin

from app.auth import firebase as fb_auth
from app.firestore import fans


def test_ensure_firebase_initialized_short_circuits_when_already_initialized() -> None:
    with (
        patch.object(firebase_admin, "_apps", {"[DEFAULT]": object()}),
        patch.object(firebase_admin, "initialize_app") as init,
    ):
        fb_auth._ensure_firebase_initialized()
        init.assert_not_called()


def test_ensure_firebase_initialized_calls_initialize_when_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "test-project")
    with (
        patch.object(firebase_admin, "_apps", {}),
        patch.object(firebase_admin, "initialize_app") as init,
        patch.object(
            fb_auth.credentials, "ApplicationDefault", return_value=MagicMock()
        ),
    ):
        fb_auth._ensure_firebase_initialized()
        init.assert_called_once()
        _, options = init.call_args.args
        assert options == {"projectId": "test-project"}


def test_ensure_firebase_initialized_omits_options_when_no_project_env(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    with (
        patch.object(firebase_admin, "_apps", {}),
        patch.object(firebase_admin, "initialize_app") as init,
        patch.object(
            fb_auth.credentials, "ApplicationDefault", return_value=MagicMock()
        ),
    ):
        fb_auth._ensure_firebase_initialized()
        init.assert_called_once()
        _, options = init.call_args.args
        assert options is None


def test_get_default_firestore_client_returns_firestore_client() -> None:
    sentinel = object()
    with patch.object(fans.firestore, "Client", return_value=sentinel) as ctor:
        assert fans.get_default_client() is sentinel
        ctor.assert_called_once()
