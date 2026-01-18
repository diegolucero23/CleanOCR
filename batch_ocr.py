import os
import time
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import PIL.Image
import config
import prompts

# --- CONFIGURATION ---
DELAY_SECONDS = 10 

client = genai.Client(api_key=config.GOOGLE_API_KEY)

def log_failure(filename, reason):
    """Writes failed files to a log for the repair script."""
    with open(config.LOG_FILE, "a") as f:
        f.write(f"{filename}|{reason}\n")

def process_images():
    # Create the folder if it doesn't exist
    if not os.path.exists(config.OCR_JSON_FOLDER):
        os.makedirs(config.OCR_JSON_FOLDER)

    # Filter for images
    files = sorted([f for f in os.listdir(config.INPUT_IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    print(f"--- DEBUG INFO ---")
    print(f"Looking for images in: {config.INPUT_IMAGE_FOLDER}")
    print(f"Saving JSON output to: {config.OCR_JSON_FOLDER}")
    print(f"Found {len(files)} images to process.")
    print(f"------------------")

    if len(files) == 0:
        print("No images found! Check your 'output_images' folder.")
        return

    for i, filename in enumerate(files):
        img_path = os.path.join(config.INPUT_IMAGE_FOLDER, filename)
        
        # THIS IS THE CRITICAL LINE: It must use config.OCR_JSON_FOLDER
        json_filename = filename.replace(os.path.splitext(filename)[1], ".json")
        json_path = os.path.join(config.OCR_JSON_FOLDER, json_filename)

        # Check if file exists
        if os.path.exists(json_path):
            # If you want to see what is being skipped, uncomment the next line:
            # print(f"Skipping {filename} (File exists in {config.OCR_JSON_FOLDER})")
            continue

        print(f"[{i+1}/{len(files)}] Processing {filename}...", end="", flush=True)

        # RETRY LOOP
        while True:
            try:
                img = PIL.Image.open(img_path)
                
                # Make the API Call
                response = client.models.generate_content(
                    model=config.MODEL_NAME,
                    contents=[prompts.OCR_PROMPT, img],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                
                # Save the file
                with open(json_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                
                print(" Success.")
                time.sleep(DELAY_SECONDS)
                break 

            except ClientError as e:
                if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                    print(f" [Rate Limit] Pausing 60s...", end="", flush=True)
                    time.sleep(60)
                    continue
                else:
                    print(f" FAILED (API): {e}")
                    log_failure(filename, str(e))
                    break
            except Exception as e:
                print(f" FAILED (Local): {e}")
                log_failure(filename, str(e))
                break

if __name__ == "__main__":
    process_images()