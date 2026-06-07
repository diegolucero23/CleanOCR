import logging
from google import genai
from google.genai.errors import ClientError
from typing import Any
from .ocr_interface import OCRProvider
from app.core import config as app_config

logger = logging.getLogger(__name__)

# HTTP status codes and message fragments that indicate a model is gone/invalid.
_MODEL_UNAVAILABLE_CODES = {404, 400}
_MODEL_UNAVAILABLE_PHRASES = ("not found", "deprecated", "invalid model", "model is not supported")


def _is_model_unavailable(e: ClientError) -> bool:
    msg = str(e).lower()
    return e.code in _MODEL_UNAVAILABLE_CODES and any(p in msg for p in _MODEL_UNAVAILABLE_PHRASES)


class GoogleVisionProvider(OCRProvider):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def generate_content(self, contents: list, config: Any) -> str:
        model_name = app_config.MODEL_NAME
        try:
            return self._call(model_name, contents, config)
        except ClientError as e:
            fallback = app_config.FALLBACK_MODEL_NAME
            if _is_model_unavailable(e) and model_name != fallback:
                logger.warning(
                    "Model '%s' unavailable (%s). Falling back to '%s'.",
                    model_name, e, fallback
                )
                return self._call(fallback, contents, config)
            raise

    def _call(self, model_name: str, contents: list, config: Any) -> str:
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return response.text
