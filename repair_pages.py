import os
import time
import PIL.Image
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import config
import prompts

def repair_from_log():
    # 1. Check if the log file exists
    if not os.path.exists(config.LOG_FILE):
        print(f"No log file found at '{config.LOG_FILE}'. Nothing to repair.")
        return

    # 2. Read the failed files
    with open(config.LOG_FILE, "r") as f:
        lines = f.readlines()

    # Filter out empty lines and parse filenames
    # The log format is: filename|reason
    targets = []
    for line in lines:
        if "|" in line:
            targets.append(line.split("|")[0].strip())
    
    # Remove duplicates
    targets = sorted(list(set(targets)))

    if not targets:
        print("Log file is empty or malformed.")
        return

    print(f"--- REPAIR MODE ---")
    print(f"Found {len(targets)} failed pages in log.")
    print(f"Targeting: {targets}")

    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    # 3. Process only the targets
    for filename in targets:
        img_path = os.path.join(config.INPUT_IMAGE_FOLDER, filename)
        
        # Calculate JSON path
        json_filename = filename.replace(os.path.splitext(filename)[1], ".json")
        json_path = os.path.join(config.OCR_JSON_FOLDER, json_filename)

        print(f"Retrying {filename}...", end="", flush=True)

        if not os.path.exists(img_path):
            print(" Source image missing! Skipping.")
            continue

        try:
            img = PIL.Image.open(img_path)
            
            # Use the shared prompt
            response = client.models.generate_content(
                model=config.MODEL_NAME,
                contents=[prompts.OCR_PROMPT, img], 
                config=types.GenerateContentConfig(
                    temperature=0.1, 
                    response_mime_type="application/json"
                )
            )
            
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(" FIXED.")
            time.sleep(5) # Be gentle on retry
            
        except Exception as e:
            print(f" Failed again: {e}")

    print("\nRepair run complete. Check your folders.")
    # Optional: You could clear the log file here if you wanted.

if __name__ == "__main__":
    repair_from_log()