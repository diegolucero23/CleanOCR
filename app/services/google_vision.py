import logging
from typing import Any
import PIL.Image
from google import genai
from google.genai.errors import ClientError
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
        images = [c for c in contents if isinstance(c, PIL.Image.Image)]
        text_prompts = [c for c in contents if isinstance(c, str)]
        
        if images and text_prompts and "LAYOUT DETECTION" in text_prompts[0]:
            image = images[0]
            layout_type = self.detect_layout_type(image)
            
            if layout_type == "multi-column":
                from app.core.image_utils import add_padding
                logger.info("Multi-column layout detected. Applying center gutter padding.")
                image = add_padding(image)
            else:
                logger.info("Single-column layout detected. Skipping center gutter padding.")
                
            new_contents = []
            for c in contents:
                if isinstance(c, PIL.Image.Image):
                    new_contents.append(image)
                else:
                    new_contents.append(c)
            contents = new_contents

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

    def detect_layout_type(self, image: "PIL.Image.Image") -> str:
        from google.genai import types
        from app.core import prompts as app_prompts
        import json
        
        layout_prompt = app_prompts.LAYOUT_PROMPT
        # Layout detection uses a dedicated lightweight model and low media resolution
        # to minimize auxiliary token consumption.
        model_name = getattr(app_config, "LAYOUT_MODEL_NAME", "gemini-3.1-flash-lite")
        try:
            response_text = self._call(
                model_name,
                [layout_prompt, image],
                types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
                )
            )
            data = json.loads(response_text)
            return data.get("layout_type", "single-column")
        except Exception as e:
            logger.warning(
                "Failed to detect layout type; defaulting to single-column. Error: %s",
                e
            )
            return "single-column"

    def _call(self, model_name: str, contents: list, config: Any) -> str:
        # Enforce the spend caps before any billable request leaves the box.
        cost_guard.register_call()

        # For Gemini 3.8 models, default thinking_level to LOW to avoid output token bloat
        # unless thinking_config has already been explicitly provided.
        if "3.8" in model_name or model_name == getattr(app_config, "PRO_MODEL_NAME", None):
            from google.genai import types
            if isinstance(config, types.GenerateContentConfig):
                if getattr(config, "thinking_config", None) is None:
                    config.thinking_config = types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
            elif isinstance(config, dict) and "thinking_config" not in config:
                config["thinking_config"] = {"thinking_level": "LOW"}

        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return response.text

