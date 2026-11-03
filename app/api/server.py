import asyncio
import json
import logging
import os
import time
import uuid
import hashlib
try:
    import magic
except ImportError:
    magic = None
    print("WARNING: python-magic not found. Uploads will be rejected (fail closed) until libmagic is installed.")
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import json as jsonlogger
from redis import Redis
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.workers.celery_worker import run_ocr_pipeline
from celery.result import AsyncResult
from dotenv import load_dotenv
from app.core import config
from app.core.secrets import SecretRedactingFilter, redact
from app.core.security import verify_api_key, rate_limit_upload, rate_limit_status
from app.db.database import init_db, get_db, get_db_context
from app.db.models import JobModel, JobMetadataModel, JobResultModel

load_dotenv()

# --- 1. Structured Logging Setup ---
logger = logging.getLogger("cleanocr_api")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(timestamp)s %(level)s %(message)s %(module)s %(funcName)s"
)
logHandler.setFormatter(formatter)
logHandler.addFilter(SecretRedactingFilter())
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: initializes database schema on startup."""
    init_db()
    yield

app = FastAPI(title="CleanOCR API", lifespan=lifespan)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc: HTTPException):
    headers = getattr(exc, "headers", None)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

# Mount upload directory for static access (PDF Viewer)
# Check directory existence again to be safe
if not os.path.exists(config.UPLOAD_DIR):
    os.makedirs(config.UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")

# Setup Redis connection for checking cache
# Using the same URL as worker.py (defaulting to localhost for local dev if not in docker)
redis_client = Redis.from_url(config.REDIS_URL)

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_file_type(file_path):
    """
    Uses python-magic to verify the file is actually a PDF,
    not just named .pdf. Fails closed: without libmagic there is no
    content check, and an extension-only gate would let arbitrary
    bytes reach Poppler.
    """
    if magic is None:
        logger.error("libmagic unavailable; rejecting upload (fail closed).", extra={"file_path": file_path})
        return False

    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    if file_type != "application/pdf":
        logger.warning(f"Invalid file type failed validation: {file_type}", extra={"file_path": file_path})
        return False
    return True

def get_pdf_page_count(file_path):
    """Return the PDF's page count via poppler, or None if it can't be read."""
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(
            file_path,
            poppler_path=config.POPPLER_PATH,
            timeout=config.PDF_INFO_TIMEOUT,
        )
        return int(info["Pages"])
    except Exception as e:
        logger.warning(f"Could not read PDF page count: {e}", extra={"file_path": file_path})
        return None

def compute_stream_timeout_seconds(page_count) -> int:
    """
    Max seconds a client should expect a job (and its SSE stream) to run:
    a base allowance for queue wait + PDF burst, plus a per-page OCR budget.
    Disclosed in the /upload response and enforced by /stream.
    """
    pages = max(0, int(page_count or 0))
    return config.STREAM_BASE_BUDGET_SECONDS + pages * config.STREAM_PAGE_BUDGET_SECONDS

def ingestion_limits() -> dict:
    """Return the ingestion caps and streaming budgets for client-side disclosure."""
    return {
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "max_pdf_pages": config.MAX_PDF_PAGES,
        "max_page_pixels": config.MAX_PAGE_PIXELS,
        "render_dpi": config.PDF_RENDER_DPI,
        "accepted_types": ["application/pdf"],
        "stream_unknown_job_timeout_seconds": config.STREAM_UNKNOWN_JOB_TIMEOUT,
        "stream_base_budget_seconds": config.STREAM_BASE_BUDGET_SECONDS,
        "stream_page_budget_seconds": config.STREAM_PAGE_BUDGET_SECONDS,
    }

def require_valid_job_id(job_id: str) -> None:
    """
    Reject job ids that are not UUIDs. job_id comes straight from the URL
    and is joined into a workspace path; Starlette percent-decodes path
    params, so without this check '..%2F..%2F...' traverses out of
    WORKSPACES_DIR. All real job ids are uuid4 strings.
    """
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid job id: must be a valid UUID",
        )

def save_upload_capped(src, dest_path, max_bytes: int) -> bool:
    """
    Stream bytes from `src` to `dest_path`, aborting and returning False
    if more than `max_bytes` are read. Protects against unbounded disk
    consumption from chunked uploads where Content-Length was missing.
    """
    written = 0
    with open(dest_path, "wb") as buffer:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                return True
            written += len(chunk)
            if written > max_bytes:
                return False
            buffer.write(chunk)

@app.post("/upload", dependencies=[Depends(verify_api_key), Depends(rate_limit_upload)])
async def upload_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    volume: str | None = Form(None),
    issue: str | None = Form(None),
    date: str | None = Form(None),
    skip_metadata: bool = Form(False),
    db: Session = Depends(get_db)
):
    job_id = str(uuid.uuid4())
    logger.info("Received upload request", extra={"job_id": job_id, "uploaded_filename": file.filename})

    # Bundle Metadata
    metadata = {
        "title": title,
        "volume": volume,
        "issue": issue,
        "date": date,
        "skip_metadata": skip_metadata,
        "original_filename": file.filename
    }

    try:
        filename = f"{job_id}.pdf"
        file_path = os.path.join(config.UPLOAD_DIR, filename)
        
        # Save file temporarily, enforcing the size cap while streaming
        max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
        if not save_upload_capped(file.file, file_path, max_bytes):
            os.remove(file_path)
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {config.MAX_UPLOAD_MB} MB upload limit.",
            )

        # --- 2. Input Sanitization ---
        if magic is None:
            os.remove(file_path)
            raise HTTPException(
                status_code=503,
                detail="File type verification is unavailable on this server (libmagic missing); refusing all uploads.",
            )
        if not validate_file_type(file_path):
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Invalid file type. Only strictly valid PDFs are accepted.")

        page_count = get_pdf_page_count(file_path)
        if page_count is None:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Could not read PDF page count; the file may be corrupt.")
        if page_count > config.MAX_PDF_PAGES:
            os.remove(file_path)
            raise HTTPException(
                status_code=413,
                detail=f"PDF has {page_count} pages; the limit is {config.MAX_PDF_PAGES}.",
            )

        file_size = os.path.getsize(file_path)
        upload_time = time.time()

        # --- 3. Smart Caching ---
        file_hash = calculate_sha256(file_path)
        logger.info(f"File hash calculated: {file_hash}", extra={"job_id": job_id})
        
        try:
            cached_job_id = redis_client.get(f"cache:{file_hash}")
        except Exception as e:
            logger.warning(f"Redis cache check failed: {e}")
            cached_job_id = None
        
        if cached_job_id:
            cached_job_id = cached_job_id.decode('utf-8')
            cached_status_bytes = None
            try:
                cached_status_bytes = redis_client.get(f"cache:{cached_job_id}:status")
            except Exception:
                pass
            cached_status = cached_status_bytes.decode('utf-8') if cached_status_bytes else None

            if cached_status != "failed":
                logger.info("Cache hit! Returning existing job.", extra={"new_job_id": job_id, "cached_job_id": cached_job_id})
                os.remove(file_path)
                return {
                    "status": "cached",
                    "job_id": cached_job_id,
                    "message": "Duplicate file detected. Returning cached result."
                }
            else:
                logger.info("Cache hit on a FAILED job. Ignoring cache and re-processing.", extra={"job_id": job_id})

        # --- 4. Relational Database Persistence (Set B) ---
        db_job = JobModel(
            id=job_id,
            status="queued",
            file_hash=file_hash,
            original_filename=file.filename or filename,
            file_size=file_size,
            total_pages=page_count,
            processed_pages=0,
            model_name=config.MODEL_NAME,
            upload_time=upload_time,
        )
        db_meta = JobMetadataModel(
            job_id=job_id,
            title=title,
            volume=volume,
            issue=issue,
            publication_date=date,
            skip_metadata=skip_metadata,
        )
        db.add(db_job)
        db.add(db_meta)
        db.commit()

        # Enqueue background Celery task
        task = run_ocr_pipeline.apply_async(args=[job_id, file_path, file_hash, metadata], task_id=job_id)
        
        # Redis Caching & Stats
        try:
            redis_client.set(f"cache:{file_hash}", job_id, ex=86400)
            redis_client.set(f"cache:{job_id}:upload_time", upload_time, ex=86400)
            redis_client.set(f"cache:{job_id}:file_size", file_size, ex=86400)
        except Exception as e:
            logger.warning(f"Redis write error on upload: {e}")
        
        return {
            "status": "queued",
            "job_id": job_id,
            "task_id": task.id,
            "message": "File uploaded. Processing started in background.",
            "expectations": {
                "page_count": page_count,
                "estimated_max_processing_seconds": compute_stream_timeout_seconds(page_count),
                "stream_timeout_seconds": compute_stream_timeout_seconds(page_count),
                "limits": ingestion_limits(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(redact(traceback.format_exc()), flush=True)
        raise e

def _build_status_payload(job_id: str, db: Session = None) -> dict:
    """Build the status response dict for a given job_id from Redis state, falling back to DB."""
    response = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Waiting for worker..."
    }

    status_bytes = None
    try:
        status_bytes = redis_client.get(f"cache:{job_id}:status")
    except Exception as e:
        logger.warning(f"Redis error reading status: {e}")

    # Fallback path: If Redis does not contain job status, query the persistent relational database
    if not status_bytes:
        db_job = None
        try:
            if db:
                db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
            else:
                with get_db_context() as session:
                    db_job = session.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
        except Exception as db_e:
            logger.warning(f"Database query error during status fallback: {db_e}")

        if db_job:
            response["status"] = db_job.status
            response["upload_time"] = db_job.upload_time
            response["file_size"] = db_job.file_size
            response["total_pages"] = db_job.total_pages

            if db_job.status == "completed":
                response["progress"] = 100
                response["message"] = "Processing complete."
                response["processing_time"] = db_job.duration_seconds
                response["complexity"] = db_job.complexity
                if db_job.result and db_job.result.markdown_text:
                    response["markdown"] = db_job.result.markdown_text
            elif db_job.status == "processing":
                total = db_job.total_pages or 1
                comp = db_job.processed_pages or 0
                response["progress"] = int((comp / total) * 100) if total > 0 else 10
                response["message"] = f"Processed {comp} of {total} images..."
            elif db_job.status == "failed":
                response["message"] = db_job.error_message or "Pipeline failed or encountered an error."
            return response

        # If not found in DB either, attempt Celery state lookup
        try:
            task_result = AsyncResult(job_id)
            if task_result.state == 'FAILURE':
                response["status"] = "failed"
                response["message"] = redact(task_result.info)
        except Exception:
            pass
        return response

    status = status_bytes.decode('utf-8')
    response["status"] = status

    if status == "processing":
        total_bytes = None
        comp_bytes = None
        try:
            total_bytes = redis_client.get(f"cache:{job_id}:total_pages")
            comp_bytes = redis_client.get(f"cache:{job_id}:completed_pages")
        except Exception:
            pass

        total = int(total_bytes) if total_bytes else 0
        comp = int(comp_bytes) if comp_bytes else 0

        if total > 0:
            response["progress"] = int((comp / total) * 100)
            response["message"] = f"Processed {comp} of {total} images..."
        else:
            response["progress"] = 10
            response["message"] = "Converting PDF to images..."

    elif status == "completed":
        response["progress"] = 100
        response["message"] = "Processing complete."

        job_workspace = os.path.join(config.WORKSPACES_DIR, job_id)
        full_content_file = os.path.join(job_workspace, "output", "full_extracted_content.md")

        if os.path.exists(full_content_file):
            with open(full_content_file, "r", encoding="utf-8") as f:
                response["markdown"] = f.read()
        else:
            # Fall back to DB for markdown content if disk output is purged
            try:
                if db:
                    res_row = db.execute(select(JobResultModel).where(JobResultModel.job_id == job_id)).scalar_one_or_none()
                    if res_row and res_row.markdown_text:
                        response["markdown"] = res_row.markdown_text
            except Exception:
                pass
            if "markdown" not in response:
                response["message"] = "Completed, but full_extracted_content.md not found."

        try:
            upload_time_bytes = redis_client.get(f"cache:{job_id}:upload_time")
            end_time_bytes = redis_client.get(f"cache:{job_id}:end_time")
            file_size_bytes = redis_client.get(f"cache:{job_id}:file_size")
            total_pages_bytes = redis_client.get(f"cache:{job_id}:total_pages")

            if upload_time_bytes:
                response["upload_time"] = float(upload_time_bytes)
            if file_size_bytes:
                file_size = int(file_size_bytes)
                response["file_size"] = file_size

                if upload_time_bytes and end_time_bytes:
                    up_time = float(upload_time_bytes)
                    end_time = float(end_time_bytes)
                    proc_time = end_time - up_time
                    response["processing_time"] = round(proc_time, 2)

                    pages = int(total_pages_bytes) if total_pages_bytes else 1
                    mb_size = file_size / (1024 * 1024)
                    complexity = (mb_size * 0.2) + (pages * 0.1) + (proc_time * 0.05)
                    response["complexity"] = min(10.0, round(complexity, 1))
        except Exception as e:
            logger.error("Failed to compile stats", extra={"error": str(e)})

    elif status == "failed":
        response["message"] = "Pipeline failed or encountered an error."

    return response


@app.get("/jobs", dependencies=[Depends(verify_api_key), Depends(rate_limit_status)])
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None, pattern="^(queued|processing|completed|failed)$"),
    search: str | None = Query(None, max_length=100),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated, filterable, and searchable list of historical jobs from the database.
    Supports filtering by status, search by filename or title, and order by creation time.
    """
    query = select(JobModel).outerjoin(JobModel.citation_metadata)

    if status:
        query = query.where(JobModel.status == status)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                JobModel.original_filename.ilike(search_pattern),
                JobMetadataModel.title.ilike(search_pattern),
            )
        )

    # Count total matching rows via subquery
    subq = query.subquery()
    count_query = select(func.count()).select_from(subq)
    total = db.execute(count_query).scalar() or 0

    # Sort
    if sort_order == "asc":
        query = query.order_by(JobModel.created_at.asc())
    else:
        query = query.order_by(JobModel.created_at.desc())

    # Paginate
    offset = (page - 1) * limit
    items_query = query.offset(offset).limit(limit)
    jobs = db.execute(items_query).scalars().all()

    total_pages = (total + limit - 1) // limit if total > 0 else 0
    job_summaries = [job.to_summary_dict() for job in jobs]

    return {
        "items": job_summaries,
        "jobs": job_summaries,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@app.get("/jobs/{job_id}", dependencies=[Depends(verify_api_key), Depends(rate_limit_status)])
async def get_job_by_id(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve detailed records for a specific job, including metadata and extracted markdown text.
    Returns 404 if the job is not found in the persistence database.
    """
    require_valid_job_id(job_id)
    job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job {job_id} was not found in persistence records.",
                }
            },
        )
    return job.to_detail_dict()


@app.get("/limits")
async def get_limits():
    """
    Pre-upload disclosure of ingestion limits, so clients can show users
    the caps (file size, page count, page dimensions) and streaming
    budgets before a file is ever submitted.
    """
    return ingestion_limits()


@app.get("/system-status")
async def system_status():
    """Return tier configuration and Gemma availability for the local tier."""
    from app.services.gemma_provider import is_gemma_loaded
    tier = config.OCR_TIER
    gemma_ready = is_gemma_loaded()
    if tier == "local" and not gemma_ready:
        logger.warning(
            "OCR_TIER=local but Gemma model is not loaded. "
            "Run 'python -m app.local_setup' to pre-download the model."
        )
    return {
        "tier": tier,
        "two_pass_available": tier == "local" and gemma_ready,
        "gemma_model": config.LOCAL_GEMMA_MODEL if tier == "local" else None,
    }


@app.get("/status/{job_id}", dependencies=[Depends(verify_api_key), Depends(rate_limit_status)])
async def get_status(job_id: str, db: Session = Depends(get_db)):
    """Fetch the status of a specific job from Redis State Tracking, falling back to DB."""
    require_valid_job_id(job_id)
    return _build_status_payload(job_id, db=db)


@app.get("/stream/{job_id}", dependencies=[Depends(verify_api_key), Depends(rate_limit_status)])
async def stream_job_status(job_id: str):
    """
    SSE endpoint: pushes a JSON event whenever job state changes.
    Closes automatically when the job reaches a terminal state
    (completed or failed). Sends a heartbeat comment every 15 s to
    keep the connection alive through proxies.
    """
    require_valid_job_id(job_id)

    async def event_generator():
        last_snapshot: dict | None = None
        start_time = asyncio.get_event_loop().time()
        last_heartbeat = start_time
        HEARTBEAT_INTERVAL = 15  # seconds
        POLL_INTERVAL = 0.5      # seconds

        while True:
            payload = _build_status_payload(job_id)
            status = payload.get("status")

            # Emit an event only when something meaningful changed.
            # For terminal states always emit so the client can close.
            snapshot_key = (status, payload.get("progress"), payload.get("markdown") is not None)
            if snapshot_key != last_snapshot or status in ("completed", "failed"):
                last_snapshot = snapshot_key
                yield f"data: {json.dumps(payload)}\n\n"

            if status in ("completed", "failed"):
                break

            # --- Stream duration bound ---
            now = asyncio.get_event_loop().time()
            elapsed = now - start_time
            job_seen = False
            try:
                job_seen = bool(
                    redis_client.exists(f"cache:{job_id}:status")
                    or redis_client.exists(f"cache:{job_id}:upload_time")
                )
            except Exception:
                pass

            if job_seen:
                total_bytes = None
                try:
                    total_bytes = redis_client.get(f"cache:{job_id}:total_pages")
                except Exception:
                    pass
                total_pages = int(total_bytes) if total_bytes else 0
                max_stream = compute_stream_timeout_seconds(total_pages)
                timeout_message = (
                    "Live stream closed after reaching its maximum duration. "
                    "The job may still be processing — poll /status/{job_id} "
                    "for the final result."
                )
            else:
                max_stream = config.STREAM_UNKNOWN_JOB_TIMEOUT
                timeout_message = (
                    "No job with this id was observed within the wait window. "
                    "It may not exist, or its records may have expired."
                )
            if elapsed >= max_stream:
                timeout_payload = {
                    "job_id": job_id,
                    "status": "stream_timeout",
                    "message": timeout_message,
                }
                yield f"data: {json.dumps(timeout_payload)}\n\n"
                break

            # Heartbeat: a SSE comment keeps the connection alive
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            await asyncio.sleep(POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering
        },
    )
