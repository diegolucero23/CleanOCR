import sys
import os
from app.core import config
from .google_vision import GoogleVisionProvider


def get_provider(api_key: str, tier: str = None):
    """
    Return an OCRProvider for the requested tier.

    tier defaults to config.OCR_TIER when omitted.  Passing an explicit value
    lets callers (tests, CLI scripts) override the env var at runtime.

    Tiers:
      "standard" / "pro" → GoogleVisionProvider (Gemini API)
      "local"            → SuryaOCRProvider     (Surya + Gemma, no API key)
    """
    tier = tier or config.OCR_TIER

    if str(api_key or "").startswith("MOCK_KEY"):
        try:
            if os.getcwd() not in sys.path:
                sys.path.append(os.getcwd())
            from tests.redteam_artifacts.mock_vision import RedTeamMockProvider
            return RedTeamMockProvider()
        except ImportError as e:
            print(f"❌ RedTeam Configuration Error: {e}")
            raise RuntimeError(
                "MOCK_KEY detected, but 'tests/redteam_artifacts/mock_vision.py' is missing. "
                "Build integrity check failed."
            )

    if tier == "local":
        from .surya_provider import SuryaOCRProvider
        return SuryaOCRProvider()

    return GoogleVisionProvider(api_key)
