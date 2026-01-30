from google import genai
from google.genai import types
from .ocr_interface import OCRProvider

class GoogleVisionProvider(OCRProvider):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def generate_content(self, contents: list, config: Any) -> str:
        """
        Wraps the Real Google API Call.
        """
        # Note: 'config' here is types.GenerateContentConfig passed from the caller
        model_name = "gemini-2.0-flash-exp" # Or passed via Init
        
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
        return response.text
