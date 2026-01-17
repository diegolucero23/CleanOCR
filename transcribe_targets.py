import os
import json
import base64
import time
from google import genai
from google.genai import types

# --- CONFIGURATION ---

# 1. PASTE YOUR API KEY HERE
API_KEY = "***REMOVED-GOOGLE-API-KEY***"

# 2. The specific images you need to transcribe
TARGET_IMAGES = [
    r"output_images\page_013.png",
    r"output_images\page_331.png"
]

OUTPUT_FOLDER = "ocr_json"

def encode_image(image_path):
    """Encodes an image file to base64 for the API."""
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def transcribe_page(client, image_path):
    """Sends image to Gemini 2.0 Flash for transcription with specific JSON schema."""
    
    filename = os.path.basename(image_path)
    print(f"Processing: {filename}...")

    # Prepare Image
    b64_image = encode_image(image_path)
    if not b64_image: return None

    # --- UPDATED PROMPT ---
    # Now strictly enforces Integers for Volume/Issue
    prompt = """
    You are an expert archivist. Transcribe this page from 'The Latter Day Saint's Messenger And Advocate' verbatim.
    
    STRICT REQUIREMENTS:
    1. Output strictly valid JSON.
    2. Extract metadata (Volume, Issue, Date) if visible.
    3. **IMPORTANT: 'volume', 'issue', and 'page_number' MUST be strings containing Arabic numerals only.** - Correct: "1", "12", "5"
       - Incorrect: "I", "XII", "Five", "Vol. 1"
       - Convert Roman numerals (e.g. "Vol. II") to "2".
    4. Infer the 'page_number' from the image content if visible.
    5. Maintain original spelling/punctuation in 'markdown_content'.
    6. Layout: Transcribe column by column (left to right).
    
    JSON STRUCTURE:
    {
      "metadata": {
        "volume": "String (number) or null",
        "issue": "String (number) or null",
        "date": "String or null",
        "page_number": "String (number) or null"
      },
      "layout_type": "column",
      "markdown_content": "The full transcribed text here..."
    }
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", 
            contents=[
                types.Content(
                    parts=[
                        types.Part(text=prompt),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/png",
                                data=b64_image
                            )
                        )
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        return response.text

    except Exception as e:
        print(f"[API ERROR] Failed to transcribe {filename}: {e}")
        return None

def main():
    if "PASTE_YOUR" in API_KEY or not API_KEY:
        print("Please edit the script and paste your Google API Key in the 'API_KEY' variable at the top.")
        return

    # Initialize Gemini 2.0 Client
    client = genai.Client(api_key=API_KEY)

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    for image_path in TARGET_IMAGES:
        base_name = os.path.basename(image_path)
        json_name = base_name.replace(".png", ".json")
        output_path = os.path.join(OUTPUT_FOLDER, json_name)

        # Transcribe
        json_result = transcribe_page(client, image_path)

        if json_result:
            try:
                # Parse once to ensure it's valid JSON before saving
                parsed_json = json.loads(json_result)
                
                # OPTIONAL: Extra safety check to force integer if the model slipped
                meta = parsed_json.get("metadata", {})
                if meta.get("page_number") and isinstance(meta["page_number"], str):
                     if meta["page_number"].isdigit():
                         meta["page_number"] = int(meta["page_number"])
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(parsed_json, f, indent=4)
                
                print(f"[SUCCESS] Saved to {output_path}")
                
            except json.JSONDecodeError:
                print(f"[ERROR] Model returned invalid JSON for {base_name}. Content:\n{json_result[:100]}...")
        
        time.sleep(2)

if __name__ == "__main__":
    main()