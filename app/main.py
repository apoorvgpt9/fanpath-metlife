"""FastAPI entrypoint for fanpath-metlife.

Phase 0 skeleton: health check only. No fan or staff routes yet — those are
added in Phase 4. See DECISIONS.md Entry #19 for the full endpoint surface.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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


app = FastAPI(
    title="fanpath-metlife",
    description="Smart Indoor Navigation for MetLife Stadium (FIFA World Cup 2026).",
    version="0.1.0",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    """Cloud Run health probe. Unauthenticated by design."""
    return {"status": "ok"}
