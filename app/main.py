"""FastAPI entrypoint for fanpath-metlife.

Phase 4A: full six-endpoint surface wired in — see :mod:`app.routes` for the
handlers. This module owns app assembly: middleware, exception handlers,
rate-limiter attachment, and the startup graph load (Entry #8).

Key wiring notes:

* The custom ``HTTPException`` handler unwraps FastAPI's default
  ``{"detail": ...}`` envelope when the raised detail is already an
  Entry #23-shaped dict. Plain-string details are wrapped into the same
  shape as a fallback. This fixes the double-wrap bug flagged in Phase 3.
* The graph is loaded ONCE at startup and stored on ``app.state.graph``.
  Requests do not touch disk (Entry #8: static, loaded at startup).
* Rate limits live in :mod:`app.rate_limit`; :mod:`app.routes` decorates each
  fan/staff endpoint. ``/health`` is deliberately undecorated and stays
  unlimited.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.errors import error_payload, is_error_payload
from app.graph.loader import load_default_graph
from app.rate_limit import limiter
from app.routes import router as api_router

load_dotenv()

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the fixed security header set to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        return response


def _cors_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGIN", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _default_firestore_client_factory():  # pragma: no cover
    from google.cloud import firestore

    return firestore.Client()


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Unwrap Entry #23 payloads; wrap plain-string details in the same shape."""
    detail = exc.detail
    if is_error_payload(detail):
        return JSONResponse(status_code=exc.status_code, content=detail)
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    message = detail if isinstance(detail, str) and detail else "Request failed."
    category = "permanent" if 400 <= exc.status_code < 500 else "transient"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(category, message),
    )


async def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=error_payload("transient", "Rate limit exceeded.", str(exc.detail)),
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="fanpath-metlife",
        description="Smart Indoor Navigation for MetLife Stadium (FIFA World Cup 2026).",
        version="0.2.0",
        redirect_slashes=False,
    )
    app.state.limiter = limiter
    app.state.firestore_client_factory = _default_firestore_client_factory
    app.state.graph = load_default_graph()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Cloud Run health probe. Unauthenticated, unlimited by design."""
        return {"status": "ok"}

    return app


app = create_app()
