import os
import time
import json
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import PIL.Image

# --- CONFIGURATION ---
API_KEY = "AIzaSyCyohUkgJ1AXuwhxA5w6oEnwu1ItdCxYSw" # <--- PASTE KEY HERE

# The specific files that failed
TARGET_FILES = ["page_004.png", "page_064.png", "page_110.png", "page_207.png", "page_295.png", "page_335.png"]

INPUT_FOLDER = "output_images"
OUTPUT_FOLDER = "ocr_json"
MODEL_NAME = "gemini-2.0-flash" # Switching to 1.5 for stability on retry

# --- SETUP ---
client = genai.Client(api_key=API_KEY)

PROMPT_TEXT = """
You are a data ingestion engine for a Vector Database.
Analyze this document image.

1. **Metadata Extraction**: Identify Volume, Issue, Date, and Page Number.
2. **Text Extraction**: 
   - Transcribe the text in **reading order**. 
   - Use standard Markdown headers (#, ##).
   - Ignore running headers/footers in the main text body.

Return strictly this JSON structure:
{
    "metadata": {
        "volume": "string or null",
        "issue": "string or null",
        "date": "string or null",
        "page_number": "string or null"
    },
    "layout_type": "string",
    "markdown_content": "string"
}
"""

def repair():
    print(f"Repairing {len(TARGET_FILES)} failed pages...")
    
    for filename in TARGET_FILES:
        img_path = os.path.join(INPUT_FOLDER, filename)
        json_filename = filename.replace(".png", ".json")
        json_path = os.path.join(OUTPUT_FOLDER, json_filename)
        
        print(f"Retrying {filename}...", end="", flush=True)

        if not os.path.exists(img_path):
            print(" Image not found!")
            continue

        try:
            img = PIL.Image.open(img_path)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[PROMPT_TEXT, img],
                config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json")
            )
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(" Fixed.")
            time.sleep(4) # Short pause
            
        except Exception as e:
            print(f" Failed again: {e}")

if __name__ == "__main__":
    repair()