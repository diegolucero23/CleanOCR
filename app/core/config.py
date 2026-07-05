import os
import sys
from dotenv import load_dotenv

# Load the .env file
# Root is 3 levels up from app/core/config.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# --- TIER (must be read before API key guard) ---
# "standard" | "pro" | "local"
# "local" uses Surya + Gemma on the user's machine (no Google API needed).
OCR_TIER = os.getenv("OCR_TIER", "standard")
# Gemma model to use for the local tier (any HuggingFace hub id).
LOCAL_GEMMA_MODEL = os.getenv("LOCAL_GEMMA_MODEL", "google/gemma-4-E4B-it")

# --- API KEYS ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY and OCR_TIER != "local":
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
# Primary model (standard tier). Gemini 2.0 Flash was shut down June 1, 2026.
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
# Upgraded model for pro-tier users (selected when OCR_TIER=pro).
PRO_MODEL_NAME = os.getenv("PRO_MODEL_NAME", "gemini-3.1-flash-lite")
# Fallback if the active model is unavailable. Must differ from MODEL_NAME
# for the fallback to engage; defaults to the heavier non-lite variant.
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "gemini-2.5-flash")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# --- UPLOAD LIMITS ---
# Reject uploads larger than this (MB) and PDFs with more pages than this.
# The API is unauthenticated, and each page becomes a billed OCR call, so
# these caps bound the worst-case disk/CPU/API cost of a single request.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))

# --- RASTERIZATION LIMITS ---
# DPI used when bursting PDF pages to images (pdf_converter).
PDF_RENDER_DPI = int(os.getenv("PDF_RENDER_DPI", "300"))
# Decompression-bomb guard: reject any PDF page whose rasterized size at
# PDF_RENDER_DPI would exceed this many pixels. A tiny PDF can declare an
# arbitrarily large MediaBox and make poppler allocate gigabytes. The
# default (150M px ~= a 29"x40" double-elephant broadsheet at 300 DPI,
# ~450 MB of RGB) leaves generous headroom for real newspaper scans.
MAX_PAGE_PIXELS = int(os.getenv("MAX_PAGE_PIXELS", "150000000"))
# Kill poppler subprocesses that exceed these timeouts (seconds); malformed
# PDFs can otherwise hang pdfinfo/pdftoppm indefinitely.
PDF_INFO_TIMEOUT = int(os.getenv("PDF_INFO_TIMEOUT", "60"))
PDF_CONVERT_TIMEOUT = int(os.getenv("PDF_CONVERT_TIMEOUT", "600"))

# --- GEMINI COST GUARD ---
# Hard caps on billed Gemini API calls, enforced in GoogleVisionProvider
# before each request (see app/core/cost_guard.py). 0 disables a cap.
# GEMINI_DAILY_CALL_CAP: shared across all workers via Redis, per UTC day.
# GEMINI_RUN_CALL_CAP:   per-process, works even without Redis (CLI batch).
GEMINI_DAILY_CALL_CAP = int(os.getenv("GEMINI_DAILY_CALL_CAP", "2000"))
GEMINI_RUN_CALL_CAP = int(os.getenv("GEMINI_RUN_CALL_CAP", "5000"))

# --- CLEANUP ---
# How many hours to retain completed/failed job workspaces before deletion.
# Set to 0 to disable automatic cleanup.
WORKSPACE_TTL_HOURS = int(os.getenv("WORKSPACE_TTL_HOURS", "24"))