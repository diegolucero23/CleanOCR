import os
import sys
from dotenv import load_dotenv

# Load the .env file
# Root is 3 levels up from app/core/config.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# --- API KEYS ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    sys.exit("Error: GOOGLE_API_KEY not found in .env file.")

# --- PATHS ---
# Determine OS: 'nt' is Windows, 'posix' is Linux/Mac
if os.name == 'nt':
    # On Windows, we need the specific path from .env
    POPPLER_PATH = os.getenv("POPPLER_PATH")
else:
    # On Linux (Docker), Poppler is installed in the system PATH.
    # Passing None tells pdf2image to look for it automatically.
    POPPLER_PATH = None 

PDF_SOURCE = os.getenv("PDF_SOURCE")

# --- DIRECTORIES ---
# Allow override for experiments (e.g. "experiment_images")
INPUT_IMAGE_FOLDER = os.getenv("OVERRIDE_IMAGE_FOLDER", "output_images")
WORKSPACES_DIR = os.getenv("WORKSPACES_DIR", "workspaces") # <--- Configurable for RedTeam Sandwiching
# Allow override for experiment results
OCR_JSON_FOLDER = os.getenv("OVERRIDE_OCR_JSON_FOLDER", "ocr_jsonv2")
FINAL_MARKDOWN_FOLDER = "CleanOCR_Finalv2"
LOG_FILE = "failed_pages.log"

# --- CONFIG ---
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")