# Context.md

## Project Metadata
*   **Name:** CleanOCR
*   **Goal:** Production-grade historical text extraction for **Academic Research** (Mormon History).
*   **Current Focus:** Generalizing the platform for robust Citation/Metadata handling.

## Tech Stack
*   **Core:** Python 3.11+, FastAPI, Celery, Redis.
*   **AI:** Google Gemini 2.0 Flash Vision.
*   **Image Processing:** OpenCV (Headless), Numpy, PIL (Pillow).
*   **Infra:** Docker.

## Active Status
*   **Phase:** Phase 11 (Citation Metadata) & Phase 12 (Commit Prep) Complete.
*   **Status:** Stable Release Candidate.
*   **Next:** Feature Freeze & Commit.
*   **Status:** Stable, Sandboxed, & User-Friendly.
*   **Next:** Maintenance or Cloud Deployment.

## Recent Decisions
*   **2026-01-27:** Adopted `AGENTS.md` "Operating System".
*   **2026-01-27:** **Architecture Decision:** Modularize image logic into `image_utils.py` (Functional, Stateless).
*   **2026-01-27:** **Feature Selection:** Proceeding with **Deskew + Padding** to improve OCR. **Split** is reserved as a fallback/debugging tool.
*   **2026-01-27:** **Integration:** `image_utils.py` implemented and integrated into `convert_pdf.py`.
*   **2026-01-28:** **Production Features:** Implemented Sanitization, Smart Caching, and JSON Logging.
*   **2026-01-28:** **Architecture:** Adopted "Optimistic Caching" in `server.py`.
*   **2026-01-28:** **Status API:** Implemented `GET /status/{job_id}` with real-time Polling.
*   **2026-01-28:** **Frontend:** Integrated `react-pdf` for Side-by-Side verification.
*   **2026-01-28:** **Scalability:** Refactored `batch_ocr.py` to use `ThreadPoolExecutor` (4x Concurrency).
*   **2026-01-28:** **Reliability:** Removed hardcoded sleeps in favor of Exponential Backoff.

*   **2026-01-28:** **Tooling:** Added `test_upload.py` for CLI-based end-to-end verification.
*   **2026-01-28:** **Job Isolation:** Implemented directory wiping in `worker.py` to prevent data pollution between jobs.

*   **2026-01-29:** **Resilience:** Implemented Client-Side Persistence (`localStorage`) to recover job history on reload.
*   **2026-01-29:** **UX:** Added "Onboarding Steps" and "Empty States" to Frontend.
*   **2026-01-29:** **Architecture (Critical):** Implemented **Job Sandboxing** (`workspaces/{job_id}/`) to ensure strict isolation for concurrent jobs. Removed global folder wiping.
*   **2026-01-29:** **Refactor:** Migrated all helper scripts to accept dynamic path arguments.
*   **2026-01-29:** **Citation System:** Implemented Metadata-aware stitching.
    *   **Backend:** `POST /upload` accepts optional Form Data.
    *   **Frontend:** Modal Driven Input.
    *   **Worker:** Persists metadata to `workspaces/{job_id}/metadata.json`.
*   **2026-01-29:** **Protocol:** Updated Source Control Ignores (`workspaces/` and logs) to prepare for Main Branch merge.

## Next Objectives
1.  Implement GitHub Actions (CI/CD).
2.  Deploy to Cloud (AWS/GCP).
