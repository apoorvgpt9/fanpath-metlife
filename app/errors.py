"""Two-category error contract (DECISIONS.md Entry #23).

Every non-2xx response body from this service has the shape::

    {"type": "error", "category": "transient" | "permanent",
     "message": <human-readable>, "detail": <string or null>}

``detail`` carries the raw exception text and is included ONLY in local
development, keyed off Cloud Run's ``K_SERVICE`` env var (present in prod,
absent locally). This module centralises the K_SERVICE gate so no call site
has to repeat it.

Note: FastAPI's default ``HTTPException`` handler wraps ``exc.detail`` under a
``{"detail": ...}`` key. To keep the response body flat, ``app.main``
registers a custom handler that unwraps our payload — see
``_http_exception_handler`` there.
"""

from __future__ import annotations

import os
from typing import Any, Literal, NoReturn

from fastapi import HTTPException

ErrorCategory = Literal["transient", "permanent"]


def error_payload(
    category: ErrorCategory,
    message: str,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build a flat error body per Entry #23. ``detail`` is dropped in prod."""
    hide_detail = bool(os.environ.get("K_SERVICE"))
    return {
        "type": "error",
        "category": category,
        "message": message,
        "detail": None if hide_detail else detail,
    }


def is_error_payload(value: Any) -> bool:
    """True when ``value`` already has the flat Entry #23 shape."""
    return (
        isinstance(value, dict)
        and value.get("type") == "error"
        and value.get("category") in {"transient", "permanent"}
        and "message" in value
    )


def raise_error(
    status_code: int,
    category: ErrorCategory,
    message: str,
    detail: str | None = None,
) -> NoReturn:
    """Raise an :class:`HTTPException` whose ``detail`` is our flat payload."""
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(category, message, detail),
    )


__all__ = ["ErrorCategory", "error_payload", "is_error_payload", "raise_error"]
