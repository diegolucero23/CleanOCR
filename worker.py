import os
print("🔥🔥🔥 WORKER MODULE LOADING 🔥🔥🔥")
import time
import logging
from celery import Celery
from pythonjsonlogger import jsonlogger
import config

# Import your actual processing logic
import convert_pdf
import batch_ocr
import stitch_to_markdown
import audit_collection

# --- 1. Structured Logging Setup ---
logger = logging.getLogger("cleanocr_worker")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(timestamp)s %(level)s %(message)s %(module)s %(funcName)s"
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# 2. Setup Celery
celery_app = Celery(
    "cleanocr_worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

# 3. Define the Task
@celery_app.task(name="run_ocr_pipeline", bind=True) # bind=True gives us access to self (the task instance)
def run_ocr_pipeline(self, job_id: str, pdf_path: str, file_hash: str = None):
    logger.info(f"--- STARTED JOB {job_id} ---", extra={"job_id": job_id, "file_path": pdf_path})
    
    try:
        # PHASE 1: BURST PDF
        config.PDF_SOURCE = pdf_path
        
        logger.info("Step 1: Converting PDF...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 10, 'message': 'Converting PDF to images...'})
        convert_pdf.convert_pdf_in_chunks(pdf_path=pdf_path)
        
        # PHASE 2: OCR
        logger.info("Step 2: Running Gemini OCR...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 30, 'message': 'Running OCR on images...'})
        batch_ocr.process_images()
        
        # PHASE 3: STITCH
        logger.info("Step 3: Stitching Markdown...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 80, 'message': 'Stitching and cleaning Markdown...'})
        stitch_to_markdown.main()
        
        # PHASE 4: AUDIT
        logger.info("Step 4: Auditing...", extra={"job_id": job_id})
        audit_collection.main()
        
        # --- 4. Result Caching ---
        if file_hash:
            # Connect to Redis (using the same broker URL for simplicity)
            # In a bigger app, use a dedicated client.
            with celery_app.connection() as connection:
                redis_client = connection.default_channel.client
                # Cache the mapping: Hash -> Job ID
                # Expire after 24 hours (86400 seconds) or keep indefinitely? 
                # Let's keep it indefinitely for now as per "Smart Caching" requirements.
                redis_client.set(f"cache:{file_hash}", job_id)
                logger.info("Cached result for future use.", extra={"file_hash": file_hash, "job_id": job_id})

        logger.info(f"--- FINISHED JOB {job_id} ---", extra={"job_id": job_id})
        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        logger.error("Job failed", extra={"job_id": job_id, "error": str(e)}, exc_info=True)
        # Re-raise so Celery knows it failed
        raise e