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

_INIT_LOCK = threading.Lock()

_ERROR_PAYLOAD_INVALID = {
    "type": "error",
    "category": "permanent",
    "message": "Sign-in required. Please refresh the page to continue.",
    "detail": None,
}


def _ensure_firebase_initialized() -> None:
    """Idempotent Firebase Admin SDK initialization."""
    if firebase_admin._apps:  # noqa: SLF001 — public API returns dict of apps
        return
    with _INIT_LOCK:
        if firebase_admin._apps:  # noqa: SLF001
            return
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        options = {"projectId": project_id} if project_id else None
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options)


def _reject(detail_message: str | None = None) -> HTTPException:
    payload = dict(_ERROR_PAYLOAD_INVALID)
    if detail_message and not os.environ.get("K_SERVICE"):
        payload["detail"] = detail_message
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
