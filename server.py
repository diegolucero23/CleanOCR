import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File
import config

app = FastAPI(title="CleanOCR API")

# Ensure an upload directory exists
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    1. Accepts a PDF file.
    2. Generates a unique Job ID.
    3. Saves the file to disk.
    4. Returns the ID to the user.
    """
    # Generate a unique ID for this job (e.g., "a1b2-c3d4...")
    job_id = str(uuid.uuid4())
    
    # Create a safe filename (job_id + original extension)
    filename = f"{job_id}.pdf"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save the uploaded file chunks to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "status": "received",
        "job_id": job_id,
        "filename": file.filename,
        "message": "File saved successfully. Processing not yet started."
    }

@app.get("/")
def home():
    return {"message": "CleanOCR API is running. Go to /docs to upload."}