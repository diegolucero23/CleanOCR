import os
import time
import json
import datetime
import concurrent.futures
import threading
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import PIL.Image
from app.core import config
from app.core import prompts

# Align Pillow's decompression-bomb ceiling with the pipeline's page cap:
# Image.open() raises DecompressionBombError above 2x this value instead of
# silently allocating memory for a crafted or corrupt image. The error is
# handled by the generic failure path in process_single_image (logged +
# page marked failed).
PIL.Image.MAX_IMAGE_PIXELS = config.MAX_PAGE_PIXELS
from app.core.cost_guard import BudgetExceededError
from app.core.secrets import redact

# --- CONFIGURATION ---
# --- CONFIGURATION ---
# --- CONFIGURATION ---
MAX_WORKERS = 4  # Concurrency limit (Safe for free tier/paid tier mix)
BASE_DELAY = 1   # Minimum seconds between requests
ERROR_LOG_LOCK = threading.Lock()


class OCRPageFailure(Exception):
    """Raised when a page fails OCR processing so Celery retries can engage."""


def log_failure(filename, reason, job_id=None):
    """Writes failed files to a log for the repair script (Thread-Safe).

    Format: job_id|ISO-timestamp|filename|reason
    """
    ts = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    entry_job_id = job_id or "unknown"
    with ERROR_LOG_LOCK:
        with open(config.LOG_FILE, "a") as f:
            f.write(f"{entry_job_id}|{ts}|{filename}|{reason}\n")

def process_single_image(args):
    """Worker function for processing a single image.

    Args tuple: (filename, total_files, index, input_folder, output_folder[, job_id])
    Raises OCRPageFailure on any non-recoverable failure so Celery retries engage.
    """
    if len(args) == 6:
        filename, total_files, index, input_folder, output_folder, job_id = args
    else:
        filename, total_files, index, input_folder, output_folder = args
        job_id = None

    img_path = os.path.join(input_folder, filename)
    json_filename = filename.replace(os.path.splitext(filename)[1], ".json")
    json_path = os.path.join(output_folder, json_filename)

    # Skip if done
    if os.path.exists(json_path):
        return f"[{index+1}/{total_files}] Skipped {filename} (Exists)"

    # Adaptive Retry Loop
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            print(f"[{index+1}/{total_files}] Processing {filename} ({retry_count+1}/{max_retries})...", flush=True)

            # OCR Provider Factory
            from app.services.ocr_factory import get_provider
            provider = get_provider(config.GOOGLE_API_KEY)

            response_text = provider.generate_content(
                contents=[prompts.OCR_PROMPT, PIL.Image.open(img_path)],
                config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                )
            )

            # Save Output
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(response_text)

            return f"[{index+1}/{total_files}] ✅ Success: {filename}"

        except ClientError as e:
            if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = (2 ** retry_count) * 5  # Exponential Backoff: 5s, 10s, 20s...
                print(f"⚠️ Rate Limit on {filename}. Sleeping {wait_time}s...", flush=True)
                time.sleep(wait_time)
                retry_count += 1
            else:
                log_failure(filename, redact(e), job_id=job_id)
                raise OCRPageFailure(f"API error on {filename}: {redact(e)}") from e
        except BudgetExceededError as e:
            # Spend cap hit: fail the page immediately — retrying would only
            # burn the backoff budget, the cap won't reset mid-run.
            log_failure(filename, str(e), job_id=job_id)
            raise OCRPageFailure(f"Budget exceeded on {filename}: {e}") from e
        except OCRPageFailure:
            raise
        except Exception as e:
            log_failure(filename, redact(e), job_id=job_id)
            raise OCRPageFailure(f"Unexpected error on {filename}: {redact(e)}") from e

    log_failure(filename, "Max Retries Exceeded", job_id=job_id)
    raise OCRPageFailure(f"Max retries exceeded for {filename}")

def process_images(input_folder, output_folder, job_id=None):
    # Setup Dirs
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Get Files
    if not os.path.exists(input_folder):
        print(f"Input folder not found: {input_folder}")
        return

    files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

    print(f"--- PARALLEL OCR ENGINE STARTING ---")
    print(f"Input: {input_folder}")
    print(f"Output: {output_folder}")
    print(f"Images: {len(files)}")
    print(f"Workers: {MAX_WORKERS}")
    print(f"------------------------------------")

    if len(files) == 0:
        print("No images found.")
        return {"total": 0, "success": 0, "failed": 0}

    # Prepare Args - pass job_id as 6th element for log attribution
    tasks = [(f, len(files), i, input_folder, output_folder, job_id) for i, f in enumerate(files)]

    # Run Parallel
    success_count = 0
    failure_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_image, t): t[0] for t in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print(result)
                success_count += 1
            except OCRPageFailure as e:
                print(str(e))
                failure_count += 1

    return {"total": len(files), "success": success_count, "failed": failure_count}

if __name__ == "__main__":
    process_images(config.INPUT_IMAGE_FOLDER, config.OCR_JSON_FOLDER)