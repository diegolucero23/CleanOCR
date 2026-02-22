import os
print("🔥🔥🔥 WORKER MODULE LOADING 🔥🔥🔥")
import time
import logging
from celery import Celery, chord
import json
import redis
from pythonjsonlogger import jsonlogger
from app.core import config

# Import your actual processing logic
from app.services import pdf_converter as convert_pdf
from app.services import ocr_processor as batch_ocr
from app.services import stitcher as stitch_to_markdown

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
    broker=config.REDIS_URL,
    backend=config.REDIS_URL
)

@celery_app.task(name="ocr_page_task")
def ocr_page_task(job_id: str, img_filename: str, input_images_dir: str, ocr_json_dir: str):
    # Process single image
    # Note: process_single_image expects a tuple: (filename, total_files, index, input_folder, output_folder)
    batch_ocr.process_single_image((img_filename, 1, 0, input_images_dir, ocr_json_dir))
    
    # Update Redis state
    redis_client = redis.Redis.from_url(celery_app.conf.broker_url)
    redis_client.incr(f"cache:{job_id}:completed_pages")
    return img_filename

@celery_app.task(name="stitch_markdown_task")
def stitch_markdown_task(results, job_id: str, ocr_json_dir: str, final_md_dir: str, metadata_file: str, file_hash: str):
    logger.info(f"Step 3: Stitching Markdown for job {job_id}...", extra={"job_id": job_id})
    stitch_to_markdown.stitch_markdown(ocr_json_dir, final_md_dir, metadata_file)
    
    redis_client = redis.Redis.from_url(celery_app.conf.broker_url)
    
    # Result Caching
    if file_hash:
        redis_client.set(f"cache:{file_hash}", job_id)
        
    redis_client.set(f"cache:{job_id}:end_time", time.time())
    redis_client.set(f"cache:{job_id}:status", "completed")
    return "done"

# 3. Define the Coordinator Task
@celery_app.task(name="run_ocr_pipeline", bind=True)
def run_ocr_pipeline(self, job_id: str, pdf_path: str, file_hash: str = None, metadata: dict = None):
    logger.info(f"--- STARTED JOB {job_id} ---", extra={"job_id": job_id, "file_path": pdf_path})
    
    try:
        # PHASE 0: SETUP WORKSPACE
        job_workspace = os.path.join(config.WORKSPACES_DIR, job_id)
        input_images_dir = os.path.join(job_workspace, "images")
        ocr_json_dir = os.path.join(job_workspace, "ocr_json")
        final_md_dir = os.path.join(job_workspace, "output")
        
        os.makedirs(input_images_dir, exist_ok=True)
        os.makedirs(ocr_json_dir, exist_ok=True)
        os.makedirs(final_md_dir, exist_ok=True)
        
        metadata_file = None
        if metadata:
            metadata_file = os.path.join(job_workspace, "metadata.json")
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

        redis_client = redis.Redis.from_url(celery_app.conf.broker_url)
        redis_client.set(f"cache:{job_id}:status", "processing")

        # PHASE 1: BURST PDF
        config.PDF_SOURCE = pdf_path
        logger.info("Step 1: Converting PDF...", extra={"job_id": job_id})
        
        generated_files = convert_pdf.convert_pdf_in_chunks(pdf_path, input_images_dir)
        
        if not generated_files:
            redis_client.set(f"cache:{job_id}:status", "failed")
            raise RuntimeError("PDF conversion generated 0 images.")

        redis_client.set(f"cache:{job_id}:total_pages", len(generated_files))
        redis_client.set(f"cache:{job_id}:completed_pages", 0)

        # PHASE 2 & 3: OCR CHORD
        logger.info(f"Step 2: Dispatching {len(generated_files)} OCR tasks...", extra={"job_id": job_id})
        
        # We need the basename instead of full path because process_single_image expects it
        ocr_tasks = [
            ocr_page_task.s(job_id, os.path.basename(img_path), input_images_dir, ocr_json_dir)
            for img_path in generated_files
        ]
        
        # Chord: run all ocr_tasks in parallel, then call stitch_markdown_task
        callback = stitch_markdown_task.s(job_id, ocr_json_dir, final_md_dir, metadata_file, file_hash)
        chord(ocr_tasks)(callback)
        
        return {"status": "dispatched", "job_id": job_id}

    except Exception as e:
        logger.error("Job failed", extra={"job_id": job_id, "error": str(e)}, exc_info=True)
        # Update Redis so frontend knows it failed
        redis_client = redis.Redis.from_url(celery_app.conf.broker_url)
        redis_client.set(f"cache:{job_id}:status", "failed")
        raise e