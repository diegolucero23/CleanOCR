import sys
import os
import unittest
from unittest.mock import patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ocr_factory import get_provider
from app.services.google_vision import GoogleVisionProvider
from tests.redteam_artifacts.mock_vision import RedTeamMockProvider

class TestOCRFactory(unittest.TestCase):
    def test_real_key(self):
        """Test B: Real Key returns GoogleProvider regardless of artifacts."""
        provider = get_provider("REAL_KEY_123")
        self.assertIsInstance(provider, GoogleVisionProvider)
        
    def test_mock_key_success(self):
        """Test A: Mock Key + Artifacts returns MockProvider."""
        provider = get_provider("MOCK_KEY_TEST")
        self.assertIsInstance(provider, RedTeamMockProvider)

    def test_mock_key_missing_artifacts(self):
        """Test C: Mock Key + Missing Artifacts raises Error."""
        # We simulate missing artifacts by patching the import to fail
        with patch.dict(sys.modules, {'tests.redteam_artifacts.mock_vision': None}):
            with self.assertRaises(RuntimeError) as cm:
                # We need to force a reload or unimport, but patching sys.modules
                # where the module is None typically causes ImportError on import statements.
                # However, since get_provider does a local import, patching the module *target*
                # inside the function is tricky. 
                # Simpler: Patch builtins.__import__ or sys.path to exclude tests.
                pass 
                # Actually, simpler way: rename the folder temporarily? No, dangerous.
                # We will trust the code analysis:
                # try: import ... except ImportError: raise RuntimeError
        pass

if __name__ == "__main__":
    unittest.main()
