import os
import shutil
import uuid
import hashlib
import logging
import json
try:
    import magic
except ImportError:
    magic = None
    print("WARNING: python-magic not found. File type validation will be limited.")
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger
from redis import Redis
from app.workers.celery_worker import run_ocr_pipeline
from celery.result import AsyncResult
from dotenv import load_dotenv

load_dotenv()

# --- 1. Structured Logging Setup ---
logger = logging.getLogger("cleanocr_api")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(timestamp)s %(level)s %(message)s %(module)s %(funcName)s"
)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

app = FastAPI(title="CleanOCR API")

# Mount upload directory for static access (PDF Viewer)
# Check directory existence again to be safe
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Setup Redis connection for checking cache
# Using the same URL as worker.py (defaulting to localhost for local dev if not in docker)
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = Redis.from_url(redis_url)

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_file_type(file_path):
    """
    Uses python-magic to verify the file is actually a PDF,
    not just named .pdf.
    """
    if magic is None:
        return file_path.lower().endswith(".pdf")
        
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(file_path)
    if file_type != "application/pdf":
        logger.warning(f"Invalid file type failed validation: {file_type}", extra={"file_path": file_path})
        return False
    return True

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    volume: str | None = Form(None),
    issue: str | None = Form(None),
    date: str | None = Form(None),
    skip_metadata: bool = Form(False)
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
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save file temporarily
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print("DEBUG: File saved.")
    
        # --- 2. Input Sanitization ---
        if not validate_file_type(file_path):
            os.remove(file_path) # Cleanup
            raise HTTPException(status_code=400, detail="Invalid file type. Only strictly valid PDFs are accepted.")

        # --- 3. Smart Caching ---
        file_hash = calculate_sha256(file_path)
        logger.info(f"File hash calculated: {file_hash}", extra={"job_id": job_id})
        
        cached_job_id = redis_client.get(f"cache:{file_hash}")
        
        if cached_job_id:
            cached_job_id = cached_job_id.decode('utf-8')
            logger.info("Cache hit! Returning existing job.", extra={"new_job_id": job_id, "cached_job_id": cached_job_id})
            os.remove(file_path)
            return {
                "status": "cached",
                "job_id": cached_job_id,
                "message": "Duplicate file detected. Returning cached result."
            }

        # If new, proceed
        # Force Task ID = Job ID so we can query status easily later
        # 4. Pass Metadata to Worker
        task = run_ocr_pipeline.apply_async(args=[job_id, file_path, file_hash, metadata], task_id=job_id)
        
        # 3b. Set Cache Immediately (Debounce/Dedupe)
        redis_client.set(f"cache:{file_hash}", job_id, ex=86400)
        
        return {
            "status": "queued",
            "job_id": job_id,
            "task_id": task.id,
            "message": "File uploaded. Processing started in background."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Fetch the status of a specific job from Celery/Redis.
    """
    # 1. Check if it's in our "Smart Cache" (Completed)
    # We might not have the hash, so we rely on Celery's Result Backend.
    
    task_result = AsyncResult(job_id)
    
    response = {
        "job_id": job_id,
        "status": task_result.status.lower(), # pending, processing, success, failure
        "progress": 0,
        "message": "Initializing..."
    }

    if task_result.state == 'PENDING':
        response["status"] = "queued"
        response["message"] = "Waiting for worker..."
    
    elif task_result.state == 'PROCESSING':
        # Custom state we added in worker.py
        response["status"] = "processing"
        info = task_result.info or {}
        response["progress"] = info.get("progress", 0)
        response["message"] = info.get("message", "Processing...")
        
    elif task_result.state == 'SUCCESS':
        response["status"] = "completed"
        response["progress"] = 100
        response["message"] = "Processing complete."
        
        # FIX: Extract the actual return value from the worker
        result = task_result.result
        
        if isinstance(result, dict):
            response["markdown"] = result.get("markdown")
        
    elif task_result.state == 'FAILURE':
        response["status"] = "failed"
        response["message"] = str(task_result.info) # Exception info
        
    return response
