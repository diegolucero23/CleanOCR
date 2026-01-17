import os
import time
import json
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import PIL.Image

# --- CONFIGURATION ---
API_KEY = "***REMOVED-GOOGLE-API-KEY***"  # <--- PASTE KEY HERE

INPUT_FOLDER = "output_images"
OUTPUT_FOLDER = "ocr_json"
MODEL_NAME = "gemini-2.0-flash"

# Standard wait between successful requests
DELAY_SECONDS = 10 

# --- SETUP ---
client = genai.Client(api_key=API_KEY)

PROMPT_TEXT = """
You are a data ingestion engine for a Vector Database.
Analyze this document image.

1. **Metadata Extraction**: Identify Volume, Issue, Date, and Page Number.
2. **Text Extraction**: 
   - Transcribe the text in **reading order** (e.g., Column 1, then Column 2). 
   - **DO NOT** attempt to visually reproduce columns with spacing or vertical bars.
   - Use standard Markdown headers (#, ##) for titles.
   - Ignore running headers and footers (page numbers, issue titles) in the main text body.

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

def process_images():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    files = sorted([f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

    print(f"Targeting Python 3.11 Environment (New SDK)")
    print(f"Found {len(files)} images to process.")

    for i, filename in enumerate(files):
        img_path = os.path.join(INPUT_FOLDER, filename)
        json_filename = filename.replace(os.path.splitext(filename)[1], ".json")
        json_path = os.path.join(OUTPUT_FOLDER, json_filename)

        if os.path.exists(json_path):
            print(f"[{i+1}/{len(files)}] Skipping {filename} (already done).")
            continue

        print(f"[{i+1}/{len(files)}] Processing {filename}...", end="", flush=True)

        # RETRY LOOP: Keeps trying until success or non-recoverable error
        while True:
            try:
                img = PIL.Image.open(img_path)
                
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[PROMPT_TEXT, img],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                
                with open(json_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                
                print(" Success.")
                time.sleep(DELAY_SECONDS)
                break # Break retry loop on success

            except ClientError as e:
                # Check if it is a 429 (Rate Limit) error
                if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"\n   [!] Rate Limit Hit. Pausing for 60 seconds to refill quota...", end="", flush=True)
                    time.sleep(60)
                    print(" Retrying...")
                    continue # Retry the loop
                else:
                    # Some other API error (like 400 or 500)
                    print(f" FAILED (API Error): {e}")
                    break # Move to next file
            
            except Exception as e:
                # Local error (file not found, etc)
                print(f" FAILED (Local Error): {e}")
                break

if __name__ == "__main__":
    process_images()