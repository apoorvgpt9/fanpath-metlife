"""Gemini client factory (DECISIONS.md Entry #13, Entry #26, Entry #29).

Both agents now default to Flash tier (Entry #29 — Intent Agent moved from Pro
to Flash to halve per-request latency after a measured Efficiency regression).
Model literals are env-configurable so the tier can be changed back via
``GEMINI_PRO_MODEL`` without a code change.

API surface uses the legacy ``generateContent`` endpoint per Entry #26, matching
the pattern already established in ``scripts/draft_graph.py``.

Agents raise :class:`GeminiServiceError` / :class:`GeminiTimeoutError` from
this module; per DECISIONS.md Entry #23 the HTTP error mapping is Phase 4's
job, not this module's.
"""

from __future__ import annotations

import os

from google import genai

DEFAULT_FLASH_MODEL = "gemini-3.5-flash"
DEFAULT_PRO_MODEL = "gemini-3.5-flash"


class GeminiError(Exception):
    """Base class for Gemini-related failures raised by agents."""


class GeminiTimeoutError(GeminiError):
    """Gemini call exceeded deadline / timed out. Category: transient."""


class GeminiServiceError(GeminiError):
    """Gemini call failed for any other reason (5xx, auth, malformed)."""


def _is_timeout(exc: BaseException) -> bool:
    """Return True when ``exc`` message hints at a timeout/deadline-exceeded."""
    text = str(exc).lower()
    return "timeout" in text or "deadline" in text


MAX_OUTPUT_TOKENS = 5120


class GeminiClient:
    """Thin, mockable wrapper over ``genai.Client.models.generate_content``.

    Deliberately narrow: one public method. Contract tests mock this class
    (or the ``.flash()`` / ``.pro()`` factory functions) rather than the
    agent functions that consume it — mirrors the Layer-3 boundary from
    DECISIONS.md Entry #21.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate_content(
        self,
        prompt: str,
        *,
        response_mime_type: str | None = None,
    ) -> str:
        """Call the Gemini ``generateContent`` API and return the response text.

        Reads ``GEMINI_API_KEY`` from the environment. Raises
        :class:`GeminiTimeoutError` when the SDK error hints at a timeout,
        otherwise :class:`GeminiServiceError` for any other failure.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise GeminiServiceError("GEMINI_API_KEY not set in environment")
        client = genai.Client(api_key=api_key)
        config = genai.types.GenerateContentConfig(
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        if response_mime_type:
            config.response_mime_type = response_mime_type
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            if _is_timeout(exc):
                raise GeminiTimeoutError(str(exc)) from exc
            raise GeminiServiceError(str(exc)) from exc
        return response.text or ""


def flash() -> GeminiClient:
    """Flash-tier client. Guide Agent (Entry #13). Model per Entry #26."""
    return GeminiClient(os.environ.get("GEMINI_FLASH_MODEL", DEFAULT_FLASH_MODEL))


def pro() -> GeminiClient:
    """Pro-tier client. Intent Agent (Entry #13, #29). Now defaults to Flash."""
    return GeminiClient(os.environ.get("GEMINI_PRO_MODEL", DEFAULT_PRO_MODEL))
