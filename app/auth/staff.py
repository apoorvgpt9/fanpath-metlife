"""Staff shared-token auth (DECISIONS.md Entry #18).

Single shared ``STAFF_TOKEN`` env var, no per-staff identity, no
``updated_by`` audit trail. Deliberate simplification, documented in Entry #18
and SECURITY.md as a limitation, not a gap. Compares with
``hmac.compare_digest`` so token comparison is constant-time.

Same 401 error shape as :mod:`app.auth.firebase` — permanent category per
Entry #23.
"""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.errors import error_payload

_ERROR_MESSAGE = "Staff authentication required."


def _reject(detail_message: str | None = None) -> HTTPException:
    """Build the 401 :class:`HTTPException` with the Entry #23 staff payload."""
    payload = error_payload("permanent", _ERROR_MESSAGE, detail_message)
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=payload)


def _extract_bearer(authorization: str | None) -> str:
    """Return the raw bearer token or raise the 401 rejection payload."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _reject("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _reject("empty bearer token")
    return token


def verify_staff_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Constant-time comparison against ``STAFF_TOKEN``."""
    expected = os.environ.get("STAFF_TOKEN")
    if not expected:
        raise _reject("STAFF_TOKEN not configured on server")
    provided = _extract_bearer(authorization)
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise _reject("staff token mismatch")


StaffAuth = Annotated[None, Depends(verify_staff_token)]


__all__ = ["StaffAuth", "verify_staff_token"]
