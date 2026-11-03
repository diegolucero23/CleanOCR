"""
tests/test_google_vision.py

Covers GoogleVisionProvider model fallback chain:
  primary model 404 → fallback model used
  fallback model 404 → exception re-raised
  success on first try → no fallback called
"""
from unittest.mock import patch, MagicMock, call

import pytest
from google.genai.errors import ClientError

from app.services.google_vision import GoogleVisionProvider, _is_model_unavailable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(api_key="test-key"):
    with patch("app.services.google_vision.genai.Client"):
        provider = GoogleVisionProvider(api_key=api_key)
    return provider


def _404_error(msg="model not found"):
    """Build a ClientError that _is_model_unavailable() recognises."""
    return ClientError(code=404, response_json={"error": {"code": 404, "message": msg}})


def _500_error():
    return ClientError(code=500, response_json={"error": {"code": 500, "message": "internal error"}})


def _fake_contents():
    return ["prompt text"]


def _fake_config():
    return MagicMock()


# ---------------------------------------------------------------------------
# _is_model_unavailable helper
# ---------------------------------------------------------------------------

class TestIsModelUnavailable:
    def test_404_with_not_found_phrase(self):
        assert _is_model_unavailable(_404_error("model not found")) is True

    def test_404_with_deprecated_phrase(self):
        err = _404_error("model is deprecated")
        assert _is_model_unavailable(err) is True

    def test_500_returns_false(self):
        assert _is_model_unavailable(_500_error()) is False

    def test_404_unrelated_message_returns_false(self):
        err = ClientError(code=404, response_json={"error": {"code": 404, "message": "resource exhausted"}})
        assert _is_model_unavailable(err) is False


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

class TestFallbackChain:
    def test_success_on_first_try_no_fallback(self):
        """When primary model succeeds, _call is invoked once (no fallback)."""
        provider = _make_provider()

        with patch.object(provider, "_call", return_value="ocr text") as mock_call:
            result = provider.generate_content(_fake_contents(), _fake_config())

        assert result == "ocr text"
        assert mock_call.call_count == 1

    def test_404_on_primary_uses_fallback(self):
        """When primary model returns 404, fallback model is tried and succeeds."""
        provider = _make_provider()

        primary_model = "gemini-3.1-flash-lite"
        fallback_model = "gemini-3.5-flash-lite"

        def side_effect(model_name, contents, config):
            if model_name == primary_model:
                raise _404_error("model not found")
            return "fallback ocr text"

        with patch("app.services.google_vision._active_model", return_value=primary_model), \
             patch("app.services.google_vision.app_config.FALLBACK_MODEL_NAME", fallback_model), \
             patch.object(provider, "_call", side_effect=side_effect) as mock_call:
            result = provider.generate_content(_fake_contents(), _fake_config())

        assert result == "fallback ocr text"
        assert mock_call.call_count == 2
        assert mock_call.call_args_list[0][0][0] == primary_model
        assert mock_call.call_args_list[1][0][0] == fallback_model

    def test_fallback_also_fails_raises(self):
        """When both primary and fallback models fail with 404, ClientError is re-raised."""
        provider = _make_provider()

        primary_model = "gemini-3.1-flash-lite"
        fallback_model = "gemini-3.5-flash-lite"

        def side_effect(model_name, contents, config):
            raise _404_error("model not found")

        with patch("app.services.google_vision._active_model", return_value=primary_model), \
             patch("app.services.google_vision.app_config.FALLBACK_MODEL_NAME", fallback_model), \
             patch.object(provider, "_call", side_effect=side_effect):
            with pytest.raises(ClientError):
                provider.generate_content(_fake_contents(), _fake_config())

    def test_non_404_error_not_retried(self):
        """A non-404 ClientError (e.g., 500) must NOT trigger fallback."""
        provider = _make_provider()

        with patch.object(provider, "_call", side_effect=_500_error()) as mock_call:
            with pytest.raises(ClientError):
                provider.generate_content(_fake_contents(), _fake_config())

        # _call invoked exactly once — no fallback attempt
        assert mock_call.call_count == 1

    def test_primary_and_fallback_same_model_no_retry(self):
        """When primary == fallback (misconfigured), don't infinite-loop; raise immediately."""
        provider = _make_provider()

        same_model = "gemini-3.1-flash-lite"

        with patch("app.services.google_vision._active_model", return_value=same_model), \
             patch("app.services.google_vision.app_config.FALLBACK_MODEL_NAME", same_model), \
             patch.object(provider, "_call", side_effect=_404_error("model not found")) as mock_call:
            with pytest.raises(ClientError):
                provider.generate_content(_fake_contents(), _fake_config())

        # Falls through the `model_name != fallback` guard — only called once
        assert mock_call.call_count == 1



# ---------------------------------------------------------------------------
# Pro tier model selection
# ---------------------------------------------------------------------------

class TestActivModelSelection:
    def test_pro_tier_uses_pro_model(self):
        with patch("app.services.google_vision.app_config.OCR_TIER", "pro"), \
             patch("app.services.google_vision.app_config.PRO_MODEL_NAME", "gemini-3.8-flash"):
            from app.services.google_vision import _active_model
            assert _active_model() == "gemini-3.8-flash"

    def test_standard_tier_uses_standard_model(self):
        with patch("app.services.google_vision.app_config.OCR_TIER", "standard"), \
             patch("app.services.google_vision.app_config.MODEL_NAME", "gemini-3.1-flash-lite"):
            from app.services.google_vision import _active_model
            assert _active_model() == "gemini-3.1-flash-lite"


# ---------------------------------------------------------------------------
# Layout decoupling & Thinking Config
# ---------------------------------------------------------------------------

class TestLayoutAndThinkingConfig:
    def test_detect_layout_type_uses_layout_model_in_pro_tier(self):
        """detect_layout_type must use LAYOUT_MODEL_NAME, not PRO_MODEL_NAME."""
        from PIL import Image
        from app.core import config as app_config
        from google.genai import types

        provider = _make_provider()
        img = Image.new("RGB", (100, 100), color="white")

        with patch("app.services.google_vision.app_config.OCR_TIER", "pro"), \
             patch("app.services.google_vision.app_config.PRO_MODEL_NAME", "gemini-3.8-flash"), \
             patch("app.services.google_vision.app_config.LAYOUT_MODEL_NAME", "gemini-3.1-flash-lite"), \
             patch.object(provider, "_call", return_value='{"layout_type": "single-column"}') as mock_call:
            layout = provider.detect_layout_type(img)

        assert layout == "single-column"
        mock_call.assert_called_once()
        called_model = mock_call.call_args[0][0]
        called_config = mock_call.call_args[0][2]

        assert called_model == "gemini-3.1-flash-lite"
        assert called_config.media_resolution == types.MediaResolution.MEDIA_RESOLUTION_LOW

    def test_pro_model_thinking_config_applied(self):
        """When calling gemini-3.8-flash, thinking_level should default to LOW to avoid token bloat."""
        from google.genai import types

        provider = _make_provider()
        mock_client = MagicMock()
        provider.client = mock_client
        mock_response = MagicMock()
        mock_response.text = "test output"
        mock_client.models.generate_content.return_value = mock_response

        cfg = types.GenerateContentConfig(temperature=0.1)
        with patch("app.services.google_vision.cost_guard.register_call"):
            provider._call("gemini-3.8-flash", ["test prompt"], cfg)

        mock_client.models.generate_content.assert_called_once()
        used_config = mock_client.models.generate_content.call_args.kwargs.get("config") or mock_client.models.generate_content.call_args[1].get("config")
        assert used_config.thinking_config is not None
        assert used_config.thinking_config.thinking_level == types.ThinkingLevel.LOW
