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
from pythonjsonlogger import json as jsonlogger
from sqlalchemy import select
from app.core import config
from app.core.secrets import SecretRedactingFilter, redact
from app.db.database import get_db_context
from app.db.models import JobModel, JobResultModel

# Import processing logic
from app.services import pdf_converter as convert_pdf
from app.services import ocr_processor as batch_ocr
from app.services import stitcher as stitch_to_markdown

# ---------------------------------------------------------------------------
# 1. Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("cleanocr_worker")
logHandler = logging.StreamHandler()
# timestamp=True emits an ISO-8601 UTC "timestamp"; levelname is renamed to
# "level". (%(timestamp)s / %(level)s are not LogRecord attributes and were null.)
formatter = jsonlogger.JsonFormatter(
    "%(levelname)s %(message)s %(module)s %(funcName)s",
    timestamp=True,
    rename_fields={"levelname": "level"},
)
logHandler.setFormatter(formatter)
logHandler.addFilter(SecretRedactingFilter())
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
      3. Set cache:{job_id}:status = "failed" in Redis.
      4. Update database job status to 'failed' with error message.
    """
    try:
        r = redis.Redis.from_url(celery_app.conf.broker_url)
        task_name = sender.name if hasattr(sender, "name") else str(sender)

        dlq_entry = json.dumps({
            "task_id": task_id,
            "task_name": task_name,
            "exception_type": type(exception).__name__,
            "exception_message": redact(exception),
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
            
            # Persist failure to Database
            try:
                with get_db_context() as db:
                    db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
                    if db_job:
                        db_job.status = "failed"
                        db_job.error_message = redact(exception)
            except Exception as db_err:
                logger.warning("Failed to record task failure in DB", extra={"job_id": job_id, "error": str(db_err)})
    except Exception as e:
        logger.error("DLQ handler error", extra={"error": redact(e)})

    logger.error(
        "Task permanently failed — added to DLQ",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "exception": redact(exception),
        },
    )


# ---------------------------------------------------------------------------
# 4. Tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="ocr_page_task", bind=True, max_retries=3, default_retry_delay=30)
def ocr_page_task(self, job_id: str, img_filename: str, input_images_dir: str, ocr_json_dir: str):
    """
    Process a single page image through OCR and write its JSON result.

    Retries up to 3 times with exponential backoff on transient errors.
    Increments cache:{job_id}:completed_pages in Redis on completion.
    """
    logger.info("Processing page %s for job %s", img_filename, job_id, extra={"job_id": job_id, "page": img_filename})
    try:
        # process_single_image takes ONE tuple:
        # (filename, total_files, index, input_folder, output_folder, job_id).
        # Passing separate arguments raised TypeError on every page (see
        # tests/test_ocr_page_task_contract.py).
        # total/index only feed progress log lines, so they are best-effort.
        try:
            pages = sorted(f for f in os.listdir(input_images_dir) if f.lower().endswith(".png"))
        except OSError:
            pages = []
        index = pages.index(img_filename) if img_filename in pages else 0
        batch_ocr.process_single_image(
            (img_filename, len(pages) or 1, index, input_images_dir, ocr_json_dir, job_id)
        )

        # Update progress counter in Redis
        r = redis.Redis.from_url(celery_app.conf.broker_url)
        r.incr(f"cache:{job_id}:completed_pages")

        return img_filename

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # Return None so the chord completes and the stitcher runs on
            # whatever pages succeeded rather than aborting the whole job.
            logger.error(
                "Page permanently failed after all retries — skipping",
                extra={"job_id": job_id, "page": img_filename, "error": str(exc)},
            )
            r = redis.Redis.from_url(celery_app.conf.broker_url)
            r.incr(f"cache:{job_id}:completed_pages")  # keep progress bar accurate
            return None
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(name="stitch_markdown_task", bind=True, max_retries=3, default_retry_delay=30)
def stitch_markdown_task(self, results, job_id: str, ocr_json_dir: str, final_md_dir: str, metadata_file: str, file_hash: str):
    """
    Stitch all per-page OCR JSON files into a single Markdown document.

    Called as the chord callback after all ocr_page_task workers finish.
    Retries up to 3 times on failure.
    Persists markdown output and diagnostic metrics to the relational database.
    """
    try:
        # results holds one entry per page: the filename on success, None when
        # the page permanently failed (see ocr_page_task).
        page_results = list(results) if isinstance(results, (list, tuple)) else []
        succeeded = sum(1 for r in page_results if r)
        if page_results and succeeded == 0:
            message = f"OCR failed on all {len(page_results)} pages; no text was extracted."
            logger.error("Job failed: no pages were OCR'd", extra={"job_id": job_id, "pages": len(page_results)})
            try:
                with get_db_context() as db:
                    db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
                    if db_job:
                        db_job.status = "failed"
                        db_job.processed_pages = 0
                        db_job.error_message = message
                        db_job.end_time = time.time()
            except Exception as db_e:
                logger.warning("Failed to persist job failure to DB", extra={"job_id": job_id, "error": str(db_e)})
            r = redis.Redis.from_url(celery_app.conf.broker_url)
            # Do not cache cache:{file_hash} -> job_id: a re-upload must reprocess.
            r.set(f"cache:{job_id}:status", "failed")
            r.set(f"cache:{job_id}:end_time", time.time())
            return "failed"

        logger.info("Step 3: Stitching Markdown for job %s", job_id, extra={"job_id": job_id})
        stitch_to_markdown.stitch_markdown(ocr_json_dir, final_md_dir, metadata_file)

        # Read generated markdown content for database persistence
        full_content_file = os.path.join(final_md_dir, "full_extracted_content.md")
        markdown_content = ""
        if os.path.exists(full_content_file):
            with open(full_content_file, "r", encoding="utf-8") as f:
                markdown_content = f.read()

        word_count = len(markdown_content.split())
        end_time = time.time()

        # 1. Update Database Record
        try:
            with get_db_context() as db:
                db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
                if db_job:
                    db_job.status = "completed"
                    db_job.end_time = end_time
                    if db_job.upload_time:
                        db_job.duration_seconds = round(end_time - db_job.upload_time, 2)
                    mb_size = (db_job.file_size or 0) / (1024 * 1024)
                    pages = db_job.total_pages or 1
                    proc_time = db_job.duration_seconds or 1.0
                    complexity = (mb_size * 0.2) + (pages * 0.1) + (proc_time * 0.05)
                    db_job.complexity = min(10.0, round(complexity, 1))
                    # Count pages that actually produced OCR output, not pages attempted.
                    db_job.processed_pages = succeeded if page_results else pages

                    existing_res = db.execute(select(JobResultModel).where(JobResultModel.job_id == job_id)).scalar_one_or_none()
                    if not existing_res:
                        result_row = JobResultModel(
                            job_id=job_id,
                            markdown_text=markdown_content,
                            total_words=word_count,
                            confidence_score=0.98,
                            statistics_json=json.dumps({
                                "processing_time": db_job.duration_seconds,
                                "complexity": db_job.complexity,
                                "file_size": db_job.file_size,
                                "total_pages": db_job.total_pages,
                            }),
                        )
                        db.add(result_row)
        except Exception as db_e:
            logger.warning("Failed to persist completion to DB", extra={"job_id": job_id, "error": str(db_e)})

        # 2. Update Redis Cache
        r = redis.Redis.from_url(celery_app.conf.broker_url)

        if file_hash:
            r.set(f"cache:{file_hash}", job_id)

        r.set(f"cache:{job_id}:end_time", end_time)
        r.set(f"cache:{job_id}:status", "completed")
        return "done"

    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


@celery_app.task(name="run_ocr_pipeline", bind=True)
def run_ocr_pipeline(self, job_id: str, pdf_path: str, file_hash: str = None, metadata: dict = None):
    """
    Coordinator task: burst PDF → dispatch OCR chord → stitch.

    This task does not retry automatically because re-running after a chord
    has already been dispatched would produce duplicate OCR work. Instead,
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

        # Update database with total pages and status
        try:
            with get_db_context() as db:
                db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
                if db_job:
                    db_job.status = "processing"
                    db_job.total_pages = len(generated_files)
        except Exception as db_e:
            logger.warning("Failed to update total_pages in DB", extra={"job_id": job_id, "error": str(db_e)})

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
        logger.error("Job failed", extra={"job_id": job_id, "error": redact(e)}, exc_info=True)
        r = redis.Redis.from_url(celery_app.conf.broker_url)
        r.set(f"cache:{job_id}:status", "failed")
        try:
            with get_db_context() as db:
                db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
                if db_job:
                    db_job.status = "failed"
                    db_job.error_message = redact(e)
        except Exception:
            pass
        raise e


@celery_app.task(name="cleanup_old_workspaces")
def cleanup_old_workspaces():
    """
    Periodic task: delete workspaces and uploaded PDFs for jobs older than
    WORKSPACE_TTL_HOURS. Uses the upload_time stored in Redis; falls back to
    filesystem mtime if the Redis key has already expired.
    Skips cleanup entirely when WORKSPACE_TTL_HOURS is 0.
    Preserves database records in SQLite/PostgreSQL so historical extractions remain intact.
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
        "removed_workspaces": len(removed_workspaces),
        "removed_uploads": len(removed_uploads),
        "errors": errors,
    }


# Celery Beat schedule: run cleanup every hour
celery_app.conf.beat_schedule = {
    "cleanup-old-workspaces": {
        "task": "cleanup_old_workspaces",
        "schedule": crontab(minute=0),  # top of every hour
    },
}
