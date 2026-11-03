from unittest.mock import patch, MagicMock, call
import numpy as np
from PIL import Image
from google.genai import types

from app.core import image_utils, prompts
from app.services.google_vision import GoogleVisionProvider


def test_preprocess_image_no_padding():
    # Create a 200x200 white image
    img = Image.new("RGB", (200, 200), color="white")
    processed = image_utils.preprocess_image(img)
    # The processed image should still be 200x200 since we only deskew (no padding/gutter)
    assert processed.width == 200
    assert processed.height == 200


def test_add_padding():
    img = Image.new("RGB", (200, 200), color="white")
    padded = image_utils.add_padding(img, padding_px=50)
    # Padding splits down the middle and adds 50px white gutter
    assert padded.width == 250
    assert padded.height == 200


@patch("app.services.google_vision.genai.Client")
@patch("app.services.google_vision.app_config.LAYOUT_MODEL_NAME", "gemini-3.1-flash-lite")
@patch("app.services.google_vision._active_model", return_value="gemini-3.8-flash")
def test_google_vision_provider_layout_detection_single_column(mock_active_model, mock_client_class):
    provider = GoogleVisionProvider(api_key="test-key")
    
    # We want to mock _call to return different things:
    # 1st call (layout detection): returns JSON {"layout_type": "single-column"}
    # 2nd call (transcription): returns the transcription text
    mock_responses = [
        '{"layout_type": "single-column"}',
        '{"metadata": {}, "layout_type": "single-column", "markdown_content": "transcribed text"}'
    ]
    
    with patch.object(provider, "_call", side_effect=mock_responses) as mock_call:
        img = Image.new("RGB", (200, 200), color="white")
        result = provider.generate_content(
            contents=[prompts.OCR_PROMPT, img],
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        # Verify provider made 2 calls
        assert mock_call.call_count == 2
        
        # 1st call should be layout detection with LAYOUT_PROMPT and the unpadded image using LAYOUT_MODEL_NAME
        first_call = mock_call.call_args_list[0]
        assert first_call[0][0] == "gemini-3.1-flash-lite"
        assert "Determine if the layout is primarily" in first_call[0][1][0]  # prompt text
        assert first_call[0][1][1].width == 200  # unpadded image
        assert first_call[0][2].media_resolution == types.MediaResolution.MEDIA_RESOLUTION_LOW
        
        # 2nd call should be transcription with OCR_PROMPT and the unpadded image using active model
        second_call = mock_call.call_args_list[1]
        assert second_call[0][0] == "gemini-3.8-flash"
        assert "You are a data ingestion engine" in second_call[0][1][0]  # OCR_PROMPT
        assert second_call[0][1][1].width == 200  # unpadded image
        
        assert "transcribed text" in result


@patch("app.services.google_vision.genai.Client")
@patch("app.services.google_vision.app_config.LAYOUT_MODEL_NAME", "gemini-3.1-flash-lite")
@patch("app.services.google_vision._active_model", return_value="gemini-3.8-flash")
def test_google_vision_provider_layout_detection_multi_column(mock_active_model, mock_client_class):
    provider = GoogleVisionProvider(api_key="test-key")
    
    # We want to mock _call to return different things:
    # 1st call (layout detection): returns JSON {"layout_type": "multi-column"}
    # 2nd call (transcription): returns the transcription text
    mock_responses = [
        '{"layout_type": "multi-column"}',
        '{"metadata": {}, "layout_type": "multi-column", "markdown_content": "transcribed text"}'
    ]
    
    with patch.object(provider, "_call", side_effect=mock_responses) as mock_call:
        img = Image.new("RGB", (200, 200), color="white")
        result = provider.generate_content(
            contents=[prompts.OCR_PROMPT, img],
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        # Verify provider made 2 calls
        assert mock_call.call_count == 2
        
        # 1st call should be layout detection with LAYOUT_PROMPT and the unpadded image using LAYOUT_MODEL_NAME
        first_call = mock_call.call_args_list[0]
        assert first_call[0][0] == "gemini-3.1-flash-lite"
        assert "Determine if the layout is primarily" in first_call[0][1][0]  # prompt text
        assert first_call[0][1][1].width == 200  # unpadded image
        assert first_call[0][2].media_resolution == types.MediaResolution.MEDIA_RESOLUTION_LOW
        
        # 2nd call should be transcription with OCR_PROMPT and the padded image (200 + 50 = 250 px width)
        second_call = mock_call.call_args_list[1]
        assert second_call[0][0] == "gemini-3.8-flash"
        assert "You are a data ingestion engine" in second_call[0][1][0]  # OCR_PROMPT
        assert second_call[0][1][1].width == 250  # padded image!
        
        assert "transcribed text" in result

