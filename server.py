import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File
from worker import run_ocr_pipeline # <--- Import the task

app = FastAPI(title="CleanOCR API")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    filename = f"{job_id}.pdf"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # --- THE MAGIC CHANGE ---
    # Instead of running logic here, we push it to the queue.
    # .delay() is the Celery command for "Do this later."
    task = run_ocr_pipeline.delay(job_id, file_path)
    
    return {
        "status": "queued",
        "job_id": job_id,
        "task_id": task.id,
        "message": "File uploaded. Processing started in background."
    }