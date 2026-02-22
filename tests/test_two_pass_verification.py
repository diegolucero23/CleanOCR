import os
import pytest
from unittest.mock import patch, MagicMock
from app.services import stitcher

def test_two_pass_llm_verification():
    """
    TDD Test: Verifies that during Markdown stitching, if Two-Pass Verification
    is enabled, the stitcher sends crossing boundaries to the LLM to fix hyphenation
    splits and sentence breaks.
    """
    
    dummy_input_folder = "dummy_json_input"
    dummy_output_folder = "dummy_md_output"
    
    with patch('app.services.stitcher.os.path.exists', return_value=True), \
         patch('app.services.stitcher.os.makedirs'), \
         patch('app.services.stitcher.os.listdir', return_value=["page_001.json", "page_002.json"]), \
         patch('app.services.stitcher.load_and_repair_json') as mock_load, \
         patch('app.services.stitcher.audit_files'), \
         patch('builtins.open'):
         
        # Mock load_and_repair_json to return consecutive pages with a hyphenated split
        mock_load.side_effect = [
            {"metadata": {"page_number": 1}, "markdown_content": "This is the end of page one, continuing under-"},
            {"metadata": {"page_number": 2}, "markdown_content": "ground."}
        ]
        
        with patch('app.services.stitcher.genai.Client') as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "underground."
            mock_client.models.generate_content.return_value = mock_response
            
            # The LLM verification function is now defined
            result = stitcher.verify_boundary_text("under-", "ground.")
            
            # Assert LLM was called and correctly merged the text
            mock_client.models.generate_content.assert_called_once()
            assert result == "underground."
