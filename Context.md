# Context.md

## Project Metadata
*   **Name:** CleanOCR
*   **Goal:** Production-grade historical text extraction using Gemini 2.0 Flash.
*   **Current Focus:** Improving accuracy on 19th-century newspapers with narrow margins and double columns.

## Tech Stack
*   **Core:** Python 3.11+, FastAPI, Celery, Redis.
*   **AI:** Google Gemini 2.0 Flash Vision.
*   **Image Processing:** OpenCV (Headless), Numpy, PIL (Pillow).
*   **Infra:** Docker.

## Active Status
## Active Status
*   **Phase:** Maintenance / MVP Complete.
*   **Status:** Production Ready. Frontend & Backend verified.
*   **Next:** CI/CD & Cloud Deployment (Phase 5).

## Recent Decisions
*   **2026-01-27:** Adopted `AGENTS.md` "Operating System".
*   **2026-01-27:** **Architecture Decision:** Modularize image logic into `image_utils.py` (Functional, Stateless).
*   **2026-01-27:** **Feature Selection:** Proceeding with **Deskew + Padding** to improve OCR. **Split** is reserved as a fallback/debugging tool.
*   **2026-01-27:** **Integration:** `image_utils.py` implemented and integrated into `convert_pdf.py`.
*   **2026-01-28:** **Production Features:** Implemented Sanitization, Smart Caching, and JSON Logging.
*   **2026-01-28:** **Architecture:** Adopted "Optimistic Caching" in `server.py`.
*   **2026-01-28:** **Status API:** Implemented `GET /status/{job_id}` with real-time Polling.
*   **2026-01-28:** **Frontend:** Integrated `react-pdf` for Side-by-Side verification.

## Next Objectives
1.  Implement GitHub Actions (CI/CD).
2.  Deploy to Cloud (AWS/GCP).
