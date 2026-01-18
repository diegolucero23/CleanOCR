import os
import sys
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# --- API KEYS ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    sys.exit("Error: GOOGLE_API_KEY not found in .env file.")

# --- PATHS ---
POPPLER_PATH = os.getenv("POPPLER_PATH")
PDF_SOURCE = os.getenv("PDF_SOURCE")

# --- DIRECTORIES ---
INPUT_IMAGE_FOLDER = "output_images"
OCR_JSON_FOLDER = "ocr_json"
FINAL_MARKDOWN_FOLDER = "CleanOCR_Final"
LOG_FILE = "failed_pages.log"

# --- CONFIG ---
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")