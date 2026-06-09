import json
import os
import time
import PIL.Image
from google.genai import types
from app.core import config
from app.core.secrets import redact
from app.services.ocr_factory import get_provider
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
    # New log format: job_id|ISO-timestamp|filename|reason
    # Legacy format:  filename|reason  (2 fields — kept for backward compat)
    targets = []
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 4:
            # New format: job_id|timestamp|filename|reason
            targets.append(parts[2].strip())
        elif len(parts) == 2:
            # Legacy format: filename|reason
            targets.append(parts[0].strip())

    # Remove duplicates
    targets = sorted(list(set(targets)))

    if not targets:
        print("Log file is empty or malformed.")
        return

    print(f"--- REPAIR MODE ---")
    print(f"Found {len(targets)} failed pages in log.")
    print(f"Targeting: {targets}")

    MOCK_MODE = config.GOOGLE_API_KEY.startswith("MOCK_KEY")
    if MOCK_MODE:
        print("⚠️  MOCK MODE ENABLED: No API calls will be made.")

    provider = get_provider(config.GOOGLE_API_KEY)

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

            if MOCK_MODE:
                print(" [MOCK FIX] ", end="")
                time.sleep(0.5)
                response_text = json.dumps({
                    "markdown_content": f"# Repaired Mock Page {filename}\n\n[REPAIRED DATA]",
                    "metadata": {"confidence": 1.0}
                })
            else:
                response_text = provider.generate_content(
                    contents=[prompts.OCR_PROMPT, img],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(response_text or "")

            print(" FIXED.")
            time.sleep(5)  # Be gentle on retry

        except Exception as e:
            print(f" Failed again: {redact(e)}")

    print("\nRepair run complete. Check your folders.")

if __name__ == "__main__":
    repair_from_log()
