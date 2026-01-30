import sys
import os
from .google_vision import GoogleVisionProvider

def get_provider(api_key: str):
    """
    Returns an OCRProvider instance.
    If api_key indicates MOCK_MODE, tries to load the RedTeam artifact.
    """
    if str(api_key).startswith("MOCK_KEY"):
        try:
            # Dynamic Import: This file (mock_vision.py) is NOT in the main package.
            # It lives in tests/redteam_artifacts.
            # We must convert the path to a module import or append sys.path.
            
            # Assuming 'tests' is at the root level relative to CWD
            if os.getcwd() not in sys.path:
                sys.path.append(os.getcwd())

            from tests.redteam_artifacts.mock_vision import RedTeamMockProvider
            return RedTeamMockProvider()
        
        except ImportError as e:
            # CRITICAL SAFETY: If we are Configured for Mock, but the Mock File is missing,
            # we must NOT return the Production Provider (that would use a fake key and crash),
            # nor should we return a Real Provider (billing risk).
            # We raise an error.
            print(f"❌ RedTeam Configuration Error: {e}")
            raise RuntimeError("MOCK_KEY detected, but 'tests/redteam_artifacts/mock_vision.py' is missing. Build integrity check failed.")
            
    return GoogleVisionProvider(api_key)
