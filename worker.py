import os
import time
from celery import Celery
import config

# Import your actual processing logic
# Note: We will need to slightly adjust these scripts to accept arguments later,
# but for now, we will just trigger them.
import convert_pdf
import batch_ocr
import stitch_to_markdown
import audit_collection

# 1. Setup Celery
# We tell it to look for Redis at the hostname 'redis' (defined in docker-compose later)
celery_app = Celery(
    "cleanocr_worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

# 2. Define the Task
@celery_app.task(name="run_ocr_pipeline")
def run_ocr_pipeline(job_id: str, pdf_path: str):
    print(f"--- STARTED JOB {job_id} ---")
    
    # PHASE 1: BURST PDF
    # We temporarily override the config to point to this specific file
    # (Note: In a perfect production app, we would pass paths as arguments to every function,
    # but this hack works for now to bridge the gap).
    config.PDF_SOURCE = pdf_path
    
    print(f"Step 1: Converting {pdf_path}...")
    # We updated convert_pdf.py earlier to accept an argument!
    convert_pdf.convert_pdf_in_chunks(pdf_path=pdf_path)
    
    # PHASE 2: OCR
    print("Step 2: Running Gemini OCR...")
    batch_ocr.process_images()
    
    # PHASE 3: STITCH
    print("Step 3: Stitching Markdown...")
    stitch_to_markdown.main()
    
    # PHASE 4: AUDIT
    print("Step 4: Auditing...")
    audit_collection.main()
    
    print(f"--- FINISHED JOB {job_id} ---")
    return {"status": "completed", "job_id": job_id}