# Retrospective Log

## Purpose
This file serves as the project's long-term memory for mistakes, lessons learned, and process improvements. It allows the AI to "learn" from previous contexts and avoid repeating errors.

## Format
### [Date] - [Task Name]
*   **What went wrong:** (Specific error or inefficiencies)
*   **Root Cause:** (Why did it happen? Process? Code? Assumption?)
*   **Action Taken:** (Fix applied to Code or AGENTS.md)
*   **Rule Added:** (New rule for the future)

---

## Log
### 2026-01-27 - OCR Experiments Implementation
*   **What went wrong:** Tried to use CMD syntax (`set VAR=val && cmd`) in PowerShell, causing parser error.
*   **Root Cause:** Assumption that shell was CMD or generic, ignored checking `run_command` tool definition.
*   **Action Taken:** Standardized on PowerShell syntax (`$env:VAR='val'; cmd`).
*   **Rule Added:** Always verify the active shell environment before running compound commands.

### 2026-01-27 - QA Verification Blocked (Environment)
*   **What went wrong:** `convert_pdf.py` failed with `Unable to get page count`. Poppler path in `.env` (`C:\Program Files\poppler-25.12.0...`) does not exist.
*   **Root Cause:** Environment configuration mismatch. Use of absolute paths in `.env` without verification.
*   **Action Taken:** Searched `C:\`, `C:\Program Files`, `C:\Users` for `pdftoppm.exe` but found 0 results.
*   **Follow-up:** Blocked on user input to locate dependency.

### 2026-01-28 - Logging Key Conflict in `server.py`
*   **What went wrong:** 500 Error on upload. `KeyError: "Attempt to overwrite 'filename' in LogRecord"`.
*   **Root Cause:** Used reserved key `filename` in the `extra` dictionary of the Python logger.
*   **Action Taken:** Renamed key to `uploaded_filename`.
*   **Rule Added:** Avoid using generic keys like `filename`, `funcName` in logging `extra` dicts.

### 2026-01-28 - Race Condition in Smart Caching
*   **What went wrong:** Sequential rapid uploads were not deduped. Worker hadn't finished T1 when T2 arrived.
*   **Root Cause:** Caching was only set *after* worker completion.
*   **Action Taken:** Implemented "Optimistic Locking" / "Debounce" by setting cache key immediately in `server.py` (with TTL) before enqueueing.

### 2026-01-28 - Frontend Build Failure
*   **What went wrong:** `npm run build` failed with 19 TypeScript errors (unused imports, prop mismatches).
*   **Root Cause:** Rapid code generation without intermediate Type Checks.
*   **Action Taken:** Fixed all type errors and verified with `npm run build`.
*   **Rule Added:** (@Engineer) Run `tsc -b` or build check *before* declaring "Implementation Complete".

### 2026-01-28 - "Mock" Integration (Design Gap)
*   **What went wrong:** Frontend "Progress Bar" is fake. Backend lacks a status endpoint.
*   **Root Cause:** (@Architect) missed the explicit requirement for an Async Status API in the `implementation_plan.md`.
*   **Action Taken:** Documented as a limitation.
*   **Rule Added:** (@Architect) Frontend-Backend contracts (API definitions) must be explicitly listed in `implementation_plan.md`.

### 2026-01-28 - Celery Task ID Mismatch (Status API Stuck)
*   **What went wrong:** `verify_status_api.py` stuck in "QUEUED" forever. Worker logs showed "Ready", Redis queue empty.
*   **Root Cause:** `server.py` polled status using our custom `job_id`, but Celery ran the task with a random `task_id`. Querying `AsyncResult(job_id)` returned empty "PENDING".
*   **Action Taken:** Modified `server.py` to use `apply_async(..., task_id=job_id)` to force synchronization.
*   **Action Taken:** Modified `server.py` to use `apply_async(..., task_id=job_id)` to force synchronization.
*   **Rule Added:** Always force `task_id` when using custom IDs for external tracking.

### 2026-01-28 - React-PDF Worker Configuration
*   **What went wrong:** `react-pdf` often fails silently or with 404s if the worker isn't loaded correctly in Vite.
*   **Verification:** Verified that `pdfjs.GlobalWorkerOptions.workerSrc` pointing to `unpkg` (CDN) is the most robust zero-config method for Vite, avoiding complex build-step copying.
*   **Rule Added:** (@Engineer) Use CDN for `pdf.worker` in prototypes; move to local asset copy for strict offline requirements.

