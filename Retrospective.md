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

### 2026-01-28 - Server "Silent Success" (Missing Payload)
*   **Incident:** APIs returned "Success" but frontend showed "No Content".
*   **Root Cause:** `server.py` checked job status but failed to extract the `markdown` payload from the Celery result backend. It assumed completion meant success without forwarding the data.
*   **Action Taken:** Patched `server.py` to explicitly unpack `task_result.result.get('markdown')`.

### 2026-01-28 - Frontend "White Screen" (Refactor Error)
*   **Incident:** `App.tsx` failed to load after a refactor.
*   **Root Cause:** Accidental deletion of core logic (`useEffect`, `handleUpload`) while trying to hide a variable.
*   **Lesson:** Always verify `git diff` or file content before applying large replacement chunks. Be careful with "Delete" instructions.

### 2026-01-28 - The "10-Second" Bottleneck (Optimization)
*   **Incident:** Processing 40 pages took 9+ minutes.
*   **Root Cause:** `batch_ocr.py` had a hardcoded `time.sleep(10)` per page.
*   **Action Taken:** Refactored to `ThreadPoolExecutor` (4 workers) + Exponential Backoff. Reduced time to <3 minutes.

### 2026-01-28 - Frontend Page Sync Failure (Delimiter Mismatch)
*   **What went wrong:** The frontend's "Sync Page" feature failed to show any content for pages > 1.
*   **Root Cause:**
    1.  **Backend:** Output used a 3-dash `---` separator, which conflicted with local markdown HRs. Changed to 10-dash `----------`.
    2.  **Frontend:** The parser in `DiffViewer.tsx` was splitting by `\n` and looking for metadata on the same line, but the new backend output put metadata on the *next* line.
*   **Action Taken:** Updated `stitch_to_markdown.py` to use `----------`. Updated `DiffViewer.tsx` to regex-split by `/\n-{10,}\s*\n/`.
*   **Rule Added:** (@Architect) Define explicit separator constants in a shared config or contract when splitting document chunks.

### 2026-01-28 - Small PDF Processing Failure
*   **What went wrong:** Uploading a 16-page PDF failed/warned "Missing 368 source files".
*   **Root Cause:** `stitch_to_markdown.py` had a hardcoded `TOTAL_EXPECTED_PAGES = 384`.
*   **Action Taken:** Updated script to dynamically detect the maximum page number from the file list.
*   **Lesson:** Avoid magic numbers in data processing; verify actual input bounds.

### 2026-01-28 - OCR Layout Hallucination (Single vs Multi Column)
*   **What went wrong:** Page 2 text was out of order (Sidebar "Exhibit A" read before main text).
*   **Root Cause:** Gemini 2.0 hallucinated a "Two Column" layout for a single-column page with a header, causing it to read the "Right Column" (Header) too early.
*   **Action Taken:** Updated `prompts.py` with:
    1.  Explicit "Do not hallucinate columns" instruction.
    2.  Strict "Reading Order" rules (Top-to-Bottom for Single, Left-to-Right for Multi).
### 2026-01-29 - Content Mismatch (Tool Failure)
*   **Incident:** `App.tsx` update failed because the tool couldn't find the target string.
*   **Root Cause:** The `view_file` output was slightly stale or the replace block was too large/imprecise.
*   **Action Taken:** Used smaller, more targeted edits.
*   **Rule Added:** (@Engineer) When replacing large blocks, verify the *exact* context first, or break it into smaller guaranteed chunks.

### 2026-01-29 - Job Pollution (Critical Architecture Flaw)
*   **Incident:** Discovery that `worker.py` deleted the *entire* `output_images` folder at the start of every job.
*   **Impact:** Concurrent users would have deleted each other's data.
*   **Action Taken:** Implemented **Sandboxing** (Phase 9). Moved to `workspaces/{job_id}/`.
### 2026-01-29 - Worker Signature Mismatch (Invisible 500 Error)
*   **Incident:** `test_upload.py` and UI uploads failed with "Internal Server Error" immediately.
*   **Root Cause:** The `worker.py` definition of the Celery task (`run_ocr_pipeline`) accepted 3 arguments, but the `server.py` was updated to send 4 (adding `metadata`). This caused a `TypeError` at the moment of task dispatch, which was swallowed or obscured by noise in the logs.
*   **Action Taken:** Updated `worker.py` to match the signature.
*   **Rule Added:** (@Architect) When changing the argument list of a shared task/function between microservices, YOU MUST update the consumer (Server) AND the provider (Worker) effectively simultaneously.


### 2026-01-29 - Page Sorting Disarray (Lexicographical vs Numerical)
*   **Incident:** Pages sorted as 1, 10, 100, 11... instead of 1, 2, 3... in the final output.
*   **Root Cause:** The system relied on string sorting for metadata/filenames without zero-padding.
*   **Action Taken:** Updated `stitch_to_markdown.py` to zero-pad page numbers in the header (e.g., `Page: 001`).
*   **Rule Added:** (@Architect) Sequential IDs that will be stored as strings or filenames MUST be zero-padded to support lexicographical sorting (e.g., `001`, `002`).

## 6. Project Health Check
*   **Code Quality:** High (Typed, Linted).
*   **Resilience:** High (Persistence + Sandboxing).
*   **UX:** High (One-Click Launcher + Visual Guides).
*   **Architecture:** Validated V1.0 Architecture.

