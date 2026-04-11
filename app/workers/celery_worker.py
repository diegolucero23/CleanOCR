import os
import shutil
import time
import logging
from celery import Celery, chord
from celery.schedules import crontab
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


@celery_app.task(name="cleanup_old_workspaces")
def cleanup_old_workspaces():
    """
    Periodic task: delete workspaces and uploaded PDFs for jobs older than
    WORKSPACE_TTL_HOURS. Uses the upload_time stored in Redis; falls back to
    filesystem mtime if the Redis key has already expired.
    Skips cleanup entirely when WORKSPACE_TTL_HOURS is 0.
    """
    ttl_hours = config.WORKSPACE_TTL_HOURS
    if ttl_hours <= 0:
        return {"skipped": True, "reason": "WORKSPACE_TTL_HOURS=0"}

    ttl_seconds = ttl_hours * 3600
    now = time.time()
    cutoff = now - ttl_seconds

    rc = redis.Redis.from_url(celery_app.conf.broker_url)

    workspaces_root = config.WORKSPACES_DIR
    upload_dir = config.UPLOAD_DIR

    removed_workspaces = []
    removed_uploads = []
    errors = []

    if not os.path.isdir(workspaces_root):
        return {"removed_workspaces": [], "removed_uploads": [], "errors": []}

    for job_id in os.listdir(workspaces_root):
        workspace_path = os.path.join(workspaces_root, job_id)
        if not os.path.isdir(workspace_path):
            continue

        # Determine job age: prefer Redis upload_time, fall back to dir mtime
        upload_time_bytes = rc.get(f"cache:{job_id}:upload_time")
        if upload_time_bytes:
            job_start = float(upload_time_bytes)
        else:
            job_start = os.path.getmtime(workspace_path)

        if job_start > cutoff:
            continue  # Too recent — keep it

        # Delete workspace directory
        try:
            shutil.rmtree(workspace_path)
            removed_workspaces.append(job_id)
        except Exception as exc:
            errors.append({"job_id": job_id, "path": workspace_path, "error": str(exc)})
            continue

        # Delete uploaded PDF (if still present)
        pdf_path = os.path.join(upload_dir, f"{job_id}.pdf")
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                removed_uploads.append(job_id)
            except Exception as exc:
                errors.append({"job_id": job_id, "path": pdf_path, "error": str(exc)})

        # Remove Redis keys for this job
        redis_keys = rc.keys(f"cache:{job_id}:*")
        if redis_keys:
            rc.delete(*redis_keys)

    logger.info(
        "Workspace cleanup complete",
        extra={
            "removed_workspaces": len(removed_workspaces),
            "removed_uploads": len(removed_uploads),
            "errors": len(errors),
            "ttl_hours": ttl_hours,
        },
    )
    return {
        "removed_workspaces": removed_workspaces,
        "removed_uploads": removed_uploads,
        "errors": errors,
    }


# Celery Beat schedule: run cleanup every hour
celery_app.conf.beat_schedule = {
    "cleanup-old-workspaces": {
        "task": "cleanup_old_workspaces",
        "schedule": crontab(minute=0),  # top of every hour
    },
}