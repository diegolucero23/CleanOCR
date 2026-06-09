import logging
from typing import Optional
from app.core import config as app_config

logger = logging.getLogger(__name__)

_instance: Optional["GemmaTextProvider"] = None


def is_gemma_loaded() -> bool:
    """Return True if the Gemma singleton is instantiated and the model pipeline is loaded."""
    return _instance is not None and _instance._pipeline is not None


def get_gemma_provider() -> "GemmaTextProvider":
    """Return a module-level singleton so the model is loaded at most once."""
    global _instance
    if _instance is None:
        _instance = GemmaTextProvider()
    return _instance


class GemmaTextProvider:
    """
    Wraps a locally hosted Gemma model for text-only inference.

    Lazy-loads on first use so Docker/startup time is unaffected.  Only
    relevant when OCR_TIER=local; for other tiers GoogleVisionProvider is used.
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or app_config.LOCAL_GEMMA_MODEL
        self._pipeline = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            import torch
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            raise ImportError(
                "transformers and torch are required for OCR_TIER=local. "
                "Install with: pip install -r requirements-local.txt"
            ) from exc

        logger.info("Loading Gemma model '%s' (this may take a moment)…", self.model_name)
        dtype = "auto"
        self._pipeline = hf_pipeline(
            "text-generation",
            model=self.model_name,
            torch_dtype=dtype,
            device_map="auto",
        )
        logger.info("Gemma model loaded.")

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        """Generate text from a single string prompt."""
        self._load()
        messages = [{"role": "user", "content": prompt}]
        outputs = self._pipeline(
            messages,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )
        # transformers chat pipeline returns the full conversation; last entry is the reply
        return outputs[0]["generated_text"][-1]["content"]
