"""Firebase Anonymous Auth dependency for fan endpoints.

Per DECISIONS.md Entry #6 (Firebase Anonymous only) and Entry #23 (two-category
error contract — auth failures are ``permanent``).

Not wired into any endpoint yet (Phase 1 scope). Fan endpoints in Phase 4
apply ``verify_fan_token`` via ``Depends``.
"""

from __future__ import annotations

import os
import threading
from typing import Annotated

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.errors import error_payload

_INIT_LOCK = threading.Lock()

_ERROR_MESSAGE = "Sign-in required. Please refresh the page to continue."


def _ensure_firebase_initialized() -> None:
    """Idempotent Firebase Admin SDK initialization."""
    if firebase_admin._apps:
        return
    with _INIT_LOCK:
        if firebase_admin._apps:
            return
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        options = {"projectId": project_id} if project_id else None
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options)


def _reject(detail_message: str | None = None) -> HTTPException:
    """Build the 401 :class:`HTTPException` with the Entry #23 auth payload."""
    payload = error_payload("permanent", _ERROR_MESSAGE, detail_message)
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=payload)


def verify_fan_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Verify a Firebase ID token and return the anonymous UID.

    Raises 401 with the DECISIONS.md Entry #23 error payload on any failure.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _reject("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _reject("empty bearer token")
    _ensure_firebase_initialized()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except firebase_auth.InvalidIdTokenError as exc:
        raise _reject(f"invalid id token: {exc}") from exc
    except firebase_auth.ExpiredIdTokenError as exc:
        raise _reject(f"expired id token: {exc}") from exc
    except (
        firebase_auth.RevokedIdTokenError,
        firebase_auth.CertificateFetchError,
        ValueError,
    ) as exc:
        raise _reject(f"token verification failed: {exc}") from exc
    uid = decoded.get("uid")
    if not uid:
        raise _reject("decoded token missing uid")
    return uid


FanUid = Annotated[str, Depends(verify_fan_token)]
