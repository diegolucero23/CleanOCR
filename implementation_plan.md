# Implementation Plan: Front-Facing Job Stats

**Status:** 🏗️ Draft
**Author:** @Architect & @PM
**Target:** CleanOCR Console UI & API

## 1. Executive Summary
We will instrument the backend pipeline to capture critical diagnostic and performance metrics (Upload Time, Processing Time, File Size, Complexity Score) and expose them to the frontend. This will provide users and agents with observable telemetry on job performance.

## 2. Architecture & Data Flow

### A. Metrics Definition
1. **Upload Time:** The absolute timestamp when the file upload was completed by the API and queued for processing.
2. **File Size:** The size of the incoming PDF (in bytes/MB).
3. **Processing Time:** The elapsed time (in seconds) from `Upload Time` until the `stitch_markdown_task` completes.
4. **Complexity Score:** A calculated, user-friendly metric (0.0 to 10.0) intended to help diagnose processing bottlenecks.
   * *Proposed Formula:* `min(10.0, (File_MB * 0.2) + (Total_Pages * 0.1) + (Processing_Time_Seconds * 0.05))`

### B. Backend Flow (FastAPI & Redis)
*   **`app/api/server.py` (`POST /upload`):**
    *   Compute `.pdf` file size upon temp save (`os.path.getsize()`).
    *   Record current timestamp `upload_time = time.time()`.
    *   Persist to Redis: `cache:{job_id}:upload_time` and `cache:{job_id}:file_size`.
*   **`app/workers/celery_worker.py` (`stitch_markdown_task`):**
    *   Once stitching is complete, record `end_time = time.time()`.
    *   Persist to Redis: `cache:{job_id}:end_time`.
*   **`app/api/server.py` (`GET /status/{job_id}`):**
    *   Read `upload_time` and `file_size` from Redis.
    *   If `status == "completed"`, read `end_time`.
    *   Calculate `processing_time = end_time - upload_time`.
    *   Calculate `complexity_score` using the formula.
    *   Attach all metrics to the `JobResponse` payload.

### C. Frontend Flow (React & TS)
*   **`frontend/src/lib/api.ts`:**
    *   Update `JobResponse` signature to include: `upload_time (number)`, `file_size (number)`, `processing_time? (number)`, `complexity? (number)`.
*   **`frontend/src/hooks/useJobPersistence.ts`:**
    *   Update `PersistedJob` to store these new metrics locally.
*   **`frontend/src/components/JobCard.tsx` / `DiffViewer.tsx`:**
    *   Create a visually elegant, "glassmorphic" sub-component or badge row for stats.
    *   Format data appropriately: Filesize to `MB`, processing time to `mm:ss`.
    *   Complexity Score should use standard UI color scaling (e.g., Green/Yellow/Red text depending on the 0-10 intensity).

## 3. Implementation Steps (@Engineer)

1. **Update API Types:** Update TS definitions in frontend first (TDD approach).
2. **Instrument Redis:** Add `redis_client.set()` calls mapped to job states in `server.py` and `celery_worker.py`.
3. **Build Response Payload:** Implement calculating logic directly inside the `/status` route.
4. **UI Integration:** Design and mount the stat badges in `JobCard.tsx` and ensure local history respects the new properties.

## 4. Verification Plan (@QA)
* [ ] **Parity Check:** Upload a small vs huge PDF. Verify `complexity` scales appropriately.
* [ ] **Mock Test:** Under mocked API mode, ensure `processing_time` reflects the expected sleep overhead accurately.
* [ ] **Refresh Resilience:** Confirm that reloading the React app does not wipe the stats of previously completed jobs in `localStorage`.