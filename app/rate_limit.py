"""Shared ``slowapi`` limiter (DECISIONS.md Entry #13 carryover).

Kept in its own module so :mod:`app.main` and :mod:`app.routes` can import it
without circularity.

Key strategy: hash the ``Authorization`` header. This is a proxy for identity —
for fans the header carries a Firebase ID token (unique per anonymous UID
until rotation); for staff it carries the shared ``STAFF_TOKEN``. Hashing
means no raw credential lands in slowapi's in-memory limit table. Requests
without an Authorization header fall back to the client IP so ``/health``
probes and similar routes still get a bounded key when limits are extended
later — the rate-limited fan/staff endpoints all require auth so this fallback
never actually applies to them.

Limits:
* Fan endpoints:   60/min
* Staff endpoints: 30/min
* ``/health``:     unlimited (no decorator applied)
"""

from __future__ import annotations

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

FAN_LIMIT = "60/minute"
STAFF_LIMIT = "30/minute"


def rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization")
    if auth:
        return "auth:" + hashlib.sha256(auth.encode("utf-8")).hexdigest()[:16]
    return "ip:" + get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, default_limits=[])


__all__ = ["FAN_LIMIT", "STAFF_LIMIT", "limiter", "rate_limit_key"]
