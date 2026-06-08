import os
import pytest
from unittest.mock import patch, MagicMock
from app.services import stitcher

def test_two_pass_llm_verification():
    """
    Verifies that verify_boundary_text delegates to the OCR provider and
    returns the LLM-merged text when a hyphenation split is detected.

    Patches get_provider at the stitcher boundary so the test is not coupled
    to the internal structure of GoogleVisionProvider or genai.Client.
    """
    mock_provider = MagicMock()
    mock_provider.generate_content.return_value = "underground."

    with patch('app.services.stitcher.get_provider', return_value=mock_provider):
        result = stitcher.verify_boundary_text("under-", "ground.")

    mock_provider.generate_content.assert_called_once()
    assert result == "underground."
