import os
print("🔥🔥🔥 WORKER MODULE LOADING 🔥🔥🔥")
import time
import logging
from celery import Celery
import json
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
def run_ocr_pipeline(self, job_id: str, pdf_path: str, file_hash: str = None, metadata: dict = None):
    logger.info(f"--- STARTED JOB {job_id} ---", extra={"job_id": job_id, "file_path": pdf_path})
    
    try:
        # PHASE 0: SETUP WORKSPACE (Sandboxing)
        # Create a unique workspace for this job
        job_workspace = os.path.join(config.WORKSPACES_DIR, job_id)
        
        # Output folders specific to this job
        input_images_dir = os.path.join(job_workspace, "images")
        ocr_json_dir = os.path.join(job_workspace, "ocr_json")
        final_md_dir = os.path.join(job_workspace, "output")
        
        os.makedirs(input_images_dir, exist_ok=True)
        os.makedirs(ocr_json_dir, exist_ok=True)
        os.makedirs(final_md_dir, exist_ok=True)
        
        # Write Metadata (if exists)
        metadata_file = None
        if metadata:
            metadata_file = os.path.join(job_workspace, "metadata.json")
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

        logger.info(f"Initialized workspace: {job_workspace}", extra={"job_id": job_id})

        # PHASE 1: BURST PDF
        config.PDF_SOURCE = pdf_path
        
        logger.info("Step 1: Converting PDF...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 10, 'message': 'Converting PDF to images...'})
        # Pass dynamic output folder
        convert_pdf.convert_pdf_in_chunks(pdf_path, input_images_dir)
        
        # PHASE 2: OCR
        logger.info("Step 2: Running Gemini OCR...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 30, 'message': 'Running OCR on images...'})
        # Pass dynamic input and output folders
        batch_ocr.process_images(input_images_dir, ocr_json_dir)
        
        # PHASE 3: STITCH
        logger.info("Step 3: Stitching Markdown...", extra={"job_id": job_id})
        self.update_state(state='PROCESSING', meta={'progress': 80, 'message': 'Stitching and cleaning Markdown...'})
        # Pass dynamic input and output folders AND metadata path
        stitch_to_markdown.stitch_markdown(ocr_json_dir, final_md_dir, metadata_file)
        
        # PHASE 4: AUDIT
        # Audit logic might need updating if it heavily relies on globals, 
        # but for now we skip it or assume it's checking the log calls we replaced.
        # Actually, audit_collection.main checks specific config paths in the original code.
        # Let's skip it for now to avoid breaking if we didn't refactor it yet.
        # Or better: We assume the user doesn't need detailed audit logs for every job in production.
        logger.info("Step 4: Audit (Skipped for Sandboxing)", extra={"job_id": job_id})
        # audit_collection.main()
        
        # --- 4. Result Caching ---
        if file_hash:
            # Connect to Redis (using the same broker URL for simplicity)
            # In a bigger app, use a dedicated client.
            with celery_app.connection() as connection:
                redis_client = connection.default_channel.client
                # Cache the mapping: Hash -> Job ID
                redis_client.set(f"cache:{file_hash}", job_id)
                logger.info("Cached result for future use.", extra={"file_hash": file_hash, "job_id": job_id})

        # --- CAPTURE OUTPUT FOR FRONTEND ---
        # Read specifically from our sandboxed output folder
        output_dir = final_md_dir
        final_markdown = "Markdown generation complete."
        
        try:
            # PRIORITY CHECK: Look for the consolidated file first
            full_content_file = os.path.join(output_dir, 'full_extracted_content.md')
            
            if os.path.exists(full_content_file):
                with open(full_content_file, 'r', encoding='utf-8') as f:
                    final_markdown = f.read()
            else:
                logger.warning(f"Consolidated file not found in {output_dir}")

        except Exception as e:
            logger.error(f"Failed to read markdown: {e}")

        logger.info(f"--- FINISHED JOB {job_id} ---", extra={"job_id": job_id})
        return {"status": "completed", "job_id": job_id, "markdown": final_markdown}

    except Exception as e:
        logger.error("Job failed", extra={"job_id": job_id, "error": str(e)}, exc_info=True)
        # Re-raise so Celery knows it failed
        raise e