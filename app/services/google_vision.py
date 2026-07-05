import logging
from google import genai
from google.genai.errors import ClientError
from typing import Any
from .ocr_interface import OCRProvider
from app.core import config as app_config
from app.core import cost_guard
from app.core.secrets import SecretRedactingFilter, redact

logger = logging.getLogger(__name__)
logger.addFilter(SecretRedactingFilter())

# Only 404 reliably signals a missing/deprecated model.
# 400 (INVALID_ARGUMENT) covers too many unrelated failures (bad prompt,
# oversized image, content policy) and must not trigger a model fallback.
_MODEL_UNAVAILABLE_PHRASES = ("not found", "deprecated", "invalid model", "model is not supported")


def _is_model_unavailable(e: ClientError) -> bool:
    return e.code == 404 and any(p in str(e).lower() for p in _MODEL_UNAVAILABLE_PHRASES)


def _active_model() -> str:
    """Select model name based on OCR_TIER env var."""
    if app_config.OCR_TIER == "pro":
        return app_config.PRO_MODEL_NAME
    return app_config.MODEL_NAME


class GoogleVisionProvider(OCRProvider):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def generate_content(self, contents: list, config: Any) -> str:
        model_name = _active_model()
        try:
            return self._call(model_name, contents, config)
        except ClientError as e:
            fallback = app_config.FALLBACK_MODEL_NAME
            if _is_model_unavailable(e) and model_name != fallback:
                logger.warning(
                    "Model '%s' unavailable (%s). Falling back to '%s'.",
                    model_name, redact(e), fallback,
                )
                try:
                    return self._call(fallback, contents, config)
                except ClientError as fe:
                    logger.error(
                        "Fallback model '%s' also failed (%s). Original model was '%s'.",
                        fallback, redact(fe), model_name,
                    )
                    raise fe
            raise

    def _call(self, model_name: str, contents: list, config: Any) -> str:
        # Enforce the spend caps before any billable request leaves the box.
        cost_guard.register_call()
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return response.text
