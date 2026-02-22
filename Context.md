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
*   **Phase:** RedTeam Safety Infrastructure Setup.
*   **Status:** Testing Infrastructure (Verification Phase).
*   **Next:** Adversarial Testing (Subject to Safety Check Pass).

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
*   **2026-01-29:** **RedTeam Infra:** Established `docker-compose.redteam.yml` for isolated stress testing. Mock mode implemented.
*   **2026-02-20:** **Investigation (@PM):** Completed investigation into concurrency and accuracy. Drafted `implementation_plan.md` to shift from sequential processing to a Celery-based Producer-Consumer pipeline, and to introduce context-aware prompts block-by-block.
*   **2026-02-20:** **Milestone (@Eng & @QA):** Completed Implementation of Phase 14 (Concurrency & Accuracy). Refactored backend to use Celery Chords, ProcessPoolExecutor, Redis counters, and introduced Context-Aware Two-Pass Verification. Implemented Test-Driven Development (TDD) mandate.
*   **2026-02-20:** **Bugfix (@Eng/Arch):** Converted `ProcessPoolExecutor` to `ThreadPoolExecutor` because Celery daemon processes are forbidden from spawning children. `pdf2image` releases GIL, so performance remains identical.
*   **2026-02-20:** **Bugfix (@QA):** Identified Edge-Case in Smart Caching logic. Updated `server.py` to bypass cache if the previously cached job has a "failed" status, preventing infinite loops of failed jobs.
*   **2026-02-20:** **Script Fix:** Standardized `start.bat` and `start.sh` to automatically launch the Vite frontend server in the background for zero-code users.
*   **2026-02-20:** **Milestone (@Eng & @QA):** Completed Implementation of Phase 15 (Front-Facing Diagnostic Stats). Instrumented the backend to capture file sizes and processing intervals, exposed these via the `GET /status/{job_id}` endpoint, and integrated "Glassmorphic" stat badges into the frontend `JobCard`.
*   **2026-02-21:** **Cleanup (@PM & @Arch):** Executed "Option 4: Consolidation & Code Cleanup" from the roadmap. Purged legacy sequential output directories (`CleanOCR_Finalv2`, `ocr_jsonv2`, `output_images`, `_archive`, `output`, `services`) in favor of the sandboxed `workspaces/` pipeline. Migrated legacy scripts to `scripts/debug/` and enforced `app/core/config.py` as the ultimate source of truth.
*   **2026-02-21:** **System Arch:** Consolidated redundant IDE AI/Agent configuration directories (`.agent`, `.agents`, `.antigravity`) into a single unified `.agents/` structure to govern AI behavior and `AGENTS.md` adherence. Verified only one `AGENTS.md` exists globally.

## Next Objectives
1.  **Phase 13: Adversarial Validation (@RedTeam):**
    *   **Hypothesis:** The system is fragile under edge-case loads.
    *   **Goal:** "Break" the app (Load, Malformed Input, Network Chaos) to identify weaknesses before users do.
2.  **Phase 14: Concurrency & Accuracy Improvements (@Arch / @Eng):**
    *   **Goal:** Refactor pipeline to streamline PDF bursting and OCR ingestion using `ProcessPoolExecutor` and asynchronous Celery tasks. Improve text quality with Context-Aware Prompting and Two-Pass verification.
3.  **Shelved:** Cloud Deployment (Pending Business Requirements).
