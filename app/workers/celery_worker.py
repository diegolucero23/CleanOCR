import os
import shutil
import time
import json
import logging
import redis
from celery import Celery, chord
from celery.schedules import crontab
from celery.signals import task_failure
from kombu import Queue
from pythonjsonlogger import jsonlogger
from app.core import config

# Import processing logic
from app.services import pdf_converter as convert_pdf
from app.services import ocr_processor as batch_ocr
from app.services import stitcher as stitch_to_markdown

# ---------------------------------------------------------------------------
# 1. Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("cleanocr_worker")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(timestamp)s %(level)s %(message)s %(module)s %(funcName)s"
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# 2. Celery application
# ---------------------------------------------------------------------------
celery_app = Celery(
    "cleanocr_worker",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
)

# Queue definitions: all normal work goes to 'default';
# permanently-failed task metadata is written to 'dlq' in Redis.
celery_app.conf.task_queues = (
    Queue("default"),
    Queue("dlq"),
)
celery_app.conf.task_default_queue = "default"

# Reliability settings
# acks_late=True  — the broker ACK is sent only *after* the task completes
#                   successfully, so a worker crash re-queues the message.
# task_reject_on_worker_lost=True — if the worker is killed mid-task, the
#                   message is rejected (and re-queued) rather than lost.
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True


# ---------------------------------------------------------------------------
# 3. DLQ signal handler
# ---------------------------------------------------------------------------
@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """
    Fires when a Celery task permanently fails (all retries exhausted).

    Actions:
      1. Push a structured JSON entry to the 'dlq:tasks' Redis list so that
         operators can inspect and replay failed work.
      2. Increment a monotonic 'dlq:total_failures' counter for alerting.
      3. Set cache:{job_id}:status = "failed" so the frontend reflects the
         permanent failure immediately (first positional arg is always job_id).
    """
    r = redis.Redis.from_url(celery_app.conf.broker_url)

    task_name = sender.name if hasattr(sender, "name") else str(sender)

    dlq_entry = json.dumps({
        "task_id": task_id,
        "task_name": task_name,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "args": list(args) if args else [],
        "kwargs": kwargs or {},
        "failed_at": time.time(),
    })

    r.rpush("dlq:tasks", dlq_entry)
    r.incr("dlq:total_failures")

    # Mark the job as failed in Redis (job_id is always the first positional arg)
    if args and len(args) > 0:
        job_id = args[0]
        r.set(f"cache:{job_id}:status", "failed")

    logger.error(
        "Task permanently failed — added to DLQ",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "exception": str(exception),
        },
    )


# ---------------------------------------------------------------------------
# 4. Tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="ocr_page_task", bind=True, max_retries=3, default_retry_delay=30)
def ocr_page_task(self, job_id: str, img_filename: str, input_images_dir: str, ocr_json_dir: str):
    """
    Process a single PDF page image through the OCR pipeline.

    Retries up to 3 times with exponential back-off on any failure.
    After max_retries, the task_failure signal fires and the job is DLQ'd.
    """
    try:
        batch_ocr.process_single_image((img_filename, 1, 0, input_images_dir, ocr_json_dir))

        r = redis.Redis.from_url(celery_app.conf.broker_url)
        r.incr(f"cache:{job_id}:completed_pages")
        return img_filename

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(name="stitch_markdown_task", bind=True, max_retries=3, default_retry_delay=30)
def stitch_markdown_task(self, results, job_id: str, ocr_json_dir: str, final_md_dir: str, metadata_file: str, file_hash: str):
    """
    Stitch all per-page OCR JSON files into a single Markdown document.

    Called as the chord callback after all ocr_page_task workers finish.
    Retries up to 3 times on failure.
    """
    try:
        logger.info("Step 3: Stitching Markdown for job %s", job_id, extra={"job_id": job_id})
        stitch_to_markdown.stitch_markdown(ocr_json_dir, final_md_dir, metadata_file)

        r = redis.Redis.from_url(celery_app.conf.broker_url)

        if file_hash:
            r.set(f"cache:{file_hash}", job_id)

        r.set(f"cache:{job_id}:end_time", time.time())
        r.set(f"cache:{job_id}:status", "completed")
        return "done"

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(name="run_ocr_pipeline", bind=True)
def run_ocr_pipeline(self, job_id: str, pdf_path: str, file_hash: str = None, metadata: dict = None):
    """
    Coordinator task: burst PDF → dispatch OCR chord → stitch.

    This task does not retry automatically because re-running after a chord
    has already been dispatched would produce duplicate OCR work.  Instead,
    it catches all exceptions, marks the job as failed, and re-raises so that
    the task_failure signal (and DLQ handler) can record the event.
    """
    logger.info("--- STARTED JOB %s ---", job_id, extra={"job_id": job_id, "file_path": pdf_path})

    try:
        # PHASE 0: workspace setup
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

        r = redis.Redis.from_url(celery_app.conf.broker_url)
        r.set(f"cache:{job_id}:status", "processing")

        # PHASE 1: burst PDF into images
        config.PDF_SOURCE = pdf_path
        logger.info("Step 1: Converting PDF...", extra={"job_id": job_id})

        generated_files = convert_pdf.convert_pdf_in_chunks(pdf_path, input_images_dir)

        if not generated_files:
            r.set(f"cache:{job_id}:status", "failed")
            raise RuntimeError("PDF conversion generated 0 images.")

        r.set(f"cache:{job_id}:total_pages", len(generated_files))
        r.set(f"cache:{job_id}:completed_pages", 0)

        # PHASE 2 & 3: dispatch OCR chord
        logger.info(
            "Step 2: Dispatching %d OCR tasks...", len(generated_files),
            extra={"job_id": job_id},
        )

        ocr_tasks = [
            ocr_page_task.s(job_id, os.path.basename(img_path), input_images_dir, ocr_json_dir)
            for img_path in generated_files
        ]
        callback = stitch_markdown_task.s(job_id, ocr_json_dir, final_md_dir, metadata_file, file_hash)
        chord(ocr_tasks)(callback)

        return {"status": "dispatched", "job_id": job_id}

    except Exception as e:
        logger.error("Job failed", extra={"job_id": job_id, "error": str(e)}, exc_info=True)
        r = redis.Redis.from_url(celery_app.conf.broker_url)
        r.set(f"cache:{job_id}:status", "failed")
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
