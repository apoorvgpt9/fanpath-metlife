"""Unit tests for :mod:`app.agents.gemini_factory`.

The module wraps ``google.genai.Client``. Contract tests for the agents mock
``flash()`` / ``pro()``, so those factories themselves need direct coverage
here — plus the error-classification logic on the ``generate_content`` path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.gemini_factory import (
    DEFAULT_FLASH_MODEL,
    DEFAULT_PRO_MODEL,
    GeminiClient,
    GeminiServiceError,
    GeminiTimeoutError,
    flash,
    pro,
)


def test_flash_default_model(monkeypatch):
    monkeypatch.delenv("GEMINI_FLASH_MODEL", raising=False)
    assert flash().model_name == DEFAULT_FLASH_MODEL


def test_pro_default_model(monkeypatch):
    monkeypatch.delenv("GEMINI_PRO_MODEL", raising=False)
    assert pro().model_name == DEFAULT_PRO_MODEL


def test_flash_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_FLASH_MODEL", "custom-flash")
    assert flash().model_name == "custom-flash"


def test_pro_env_override(monkeypatch):
    """Entry #26 fallback: setting GEMINI_PRO_MODEL to flash is a config change."""
    monkeypatch.setenv("GEMINI_PRO_MODEL", DEFAULT_FLASH_MODEL)
    assert pro().model_name == DEFAULT_FLASH_MODEL


async def test_generate_content_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = GeminiClient("any-model")
    with pytest.raises(GeminiServiceError, match="GEMINI_API_KEY"):
        await client.generate_content("hello")


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_success(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.text = "OK"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client_cls.return_value = mock_client

    client = GeminiClient("test-model")
    assert await client.generate_content("hi") == "OK"
    mock_client.aio.models.generate_content.assert_called_once()
    call = mock_client.aio.models.generate_content.call_args
    assert call.kwargs["model"] == "test-model"
    cfg = call.kwargs["config"]
    assert cfg.max_output_tokens == 5120


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_with_mime(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.text = '{"ok":true}'
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client_cls.return_value = mock_client

    client = GeminiClient("test-model")
    await client.generate_content("hi", response_mime_type="application/json")
    call = mock_client.aio.models.generate_content.call_args
    cfg = call.kwargs["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.max_output_tokens == 5120


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_empty_text(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.text = None
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_client_cls.return_value = mock_client

    assert await GeminiClient("m").generate_content("hi") == ""


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_timeout(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("deadline exceeded")
    )
    mock_client_cls.return_value = mock_client

    with pytest.raises(GeminiTimeoutError):
        await GeminiClient("m").generate_content("hi")


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_timeout_variant(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Request timeout after 30s")
    )
    mock_client_cls.return_value = mock_client

    with pytest.raises(GeminiTimeoutError):
        await GeminiClient("m").generate_content("hi")


@patch("app.agents.gemini_factory.genai.Client")
async def test_generate_content_other_error(mock_client_cls, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("500 internal error")
    )
    mock_client_cls.return_value = mock_client

    with pytest.raises(GeminiServiceError):
        await GeminiClient("m").generate_content("hi")
