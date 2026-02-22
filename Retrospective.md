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


### 2026-01-31 - JSON Escape Failure in Stitcher
*   **Incident:** `stitch_to_markdown.py` failed to export `page_027.md` (Separated File).
*   **Error:** `Invalid \escape: line 9 column 2141`.
*   **Root Cause:** The new "Separated File" loop used a strict `json.loads`, whereas the main stitching loop had a robust fallback mechanism (Regex extraction) that wasn't reused.
*   **Action Taken:** Documented failure. Refactored `stitch_to_markdown.py` to use a shared `load_and_repair_json` function (2026-02-01).
*   **Resolution:** Confirmed 1:1 parity and recovery of `page_027.md`.

### 2026-02-01 - Silent OCR Failure (Config Drift)
*   **Incident:** OCR Worker reported success but produced 0 pages of markdown, leading to a broken frontend.
*   **Root Cause:**
    1.  **Config Drift:** `services/google_vision.py` had a hardcoded model name (`gemini-2.0-flash-exp`) which was deprecated/deleted by Google, causing 404s. It ignored the correct `gemini-2.0-flash` setting in `.env`.
    2.  **Silent Failure:** `worker.py` and `batch_ocr.py` caught exceptions but didn't fail the job if *all* pages failed.
*   **Action Taken:**
    1.  Updated `services/google_vision.py` to use `config.MODEL_NAME`.
    2.  Updated `config.py` to enforce `.env` loading (`override=True`).
    3.  Hardened `batch_ocr.py` to return success/failure stats.
    4.  Hardened `worker.py` to raise an Exception if 0 pages are successfully processed.
*   **Rule Added:** (@Engineer) Hardcoded configuration values (except defaults) are forbidden. Always use `config.py`.

### 2026-02-20 - Architecture Conflict: Concurrency vs Context-Awareness
*   **What went wrong:** PM proposed Pipeline Concurrency (parallel OCR) and Context-Aware Prompting (Page N requires Page N-1's output) simultaneously.
*   **Root Cause:** Failure to recognize that cross-page dependencies force sequential execution, negating the benefits of concurrency.
*   **Action Taken:** @QA revised the implementation plan to perform OCR purely concurrently, and moved Context-Aware boundary checking to a Two-Pass Verification step during Stitching.
*   **Rule Added:** (@Architect / @QA) Always evaluate feature proposals for execution blocking/dependencies. If a feature requires sequential data flow, it cannot be placed in a concurrent pipeline phase without creating a bottleneck.

### 2026-02-20 - Pytest Hangs on Windows with ProcessPoolExecutor
*   **What went wrong:** During TDD execution for concurrent PDF bursting, `pytest` consistently hung without failing or passing when testing methods involving `concurrent.futures.ProcessPoolExecutor`.
*   **Root Cause:** Windows handles multiprocessing and process pools differently than POSIX systems, often requiring `__name__ == '__main__'` guards even in test environments. Alternatively, deep mocking is required as Celery and Executor thread pools can deadlock the `pytest` runner.
*   **Action Taken:** Extensive context-manager mocking was implemented in `test_concurrency.py`. A note was added to `walkthrough.md` regarding test environment limitations on Windows.
*   **Rule Added:** (@Engineer & @QA) Be highly suspicious of test cases involving true multiprocessing or Celery workers hanging on Windows. Invest in deeper mocking (`patching` the executor context manager itself `__enter__`) rather than fighting the local runner.

### 2026-02-20 - UI Failing to Load on Start
*   **What went wrong:** The user reported they couldn't load the UI at `http://localhost:5173`. `start.bat` launched the browser but didn't actually start the Vite frontend.
*   **Root Cause:** The `docker-compose.yml` only provisions the `web` API, `worker`, and `redis`. The frontend development server was strictly omitted from "Zero-Code" scripts.
*   **Action Taken:** Standardized `start.bat` and `start.sh` to spin up a background node process (`npm run dev`) just before opening the URL.
*   **Rule Added:** (@Engineer) Always verify that launcher scripts encompass all tiers of the application, including development servers, if no production build step is enforced.

### 2026-02-20 - UI Missing "Issue 2" Transcriptions
*   **What went wrong:** When a 32-page PDF uploaded contained Issue 1 (Pages 1-16) and Issue 2 (Pages 1-16), the UI DiffViewer falsely claimed page 17+ had "no content extracted". 
*   **Root Cause:** The `stitcher.py` was generating **Page:** headers using the LLM-extracted *Printed Page Number* instead of the physical PDF sequence number. When Issue 2 began, the LLM extracted "Page 1". The UI's regex parser mapped chunk 17 to `pageMap[1]`, overwriting Issue 1, and leaving `pageMap[17]` empty.
*   **Action Taken:** Hard-modified `stitcher.py` to always generate the `**Page:**` Markdown tag based on the physical file sequence (`page_017.json` -> `017`) rather than the document's printed layout.
*   **Rule Added:** (@Engineer & @QA) Be meticulous with 1:1 mapping definitions. Frontend UI synchronizations must rely on deterministic mechanical data (e.g. physical file iteration) rather than stochastic LLM extractions.

### 2026-02-20 - Pipeline Crash with ProcessPoolExecutor (Celery)
*   **What went wrong:** Uploading the PDF via the UI caused an immediate "Pipeline failed" error. Worker logs showed: `AssertionError: daemonic processes are not allowed to have children`.
*   **Root Cause:** Celery worker processes are daemonic by default. They strictly forbid spawning sub-processes (like `concurrent.futures.ProcessPoolExecutor`) to prevent orphaned children on crash.
*   **Action Taken:** Replaced `ProcessPoolExecutor` with `ThreadPoolExecutor` in `pdf_converter.py`. Because `pdf2image` delegates to the external `poppler` utility, it inherently bypasses the Python GIL, making multithreading just as effective for this IO-bound subprocess task.
*   **Rule Added:** (@Engineer & @Arch) Never use Process-based concurrency (`ProcessPoolExecutor`, `multiprocessing`) *inside* a Celery Task. Use `ThreadPoolExecutor` (if GIL is released) or Celery's native primitives (like `group` or `chord`).

### 2026-02-20 - Adding Front-Facing Job Stats (TDD Unit Test Mocking)
*   **What went wrong:** TDD tests failed because `mock_redis.set.assert_any_call` didn't match the `ex=86400` arguments used in the implementation, and `unittest.mock.mock_open` failed due to a missing `import unittest`.
*   **Root Cause:** Incomplete mocking and syntax in `test_stats.py` during TDD implementation phase.
*   **Action Taken:** Added `import unittest` and updated assertions to precisely match the production target code `ex=86400` parameter.
*   **Rule Added:** (@QA / @Engineer) When using `unittest.mock` for TDD, ensure assertions explicitly match all keyword arguments used in the actual service module, and verify all basic imports like `unittest`.

### 2026-02-21 - Telemetry Placement (UX Bias)
*   **What went wrong:** The user didn't notice the newly added job stats (processing time, complexity) because they were only placed on the `JobCard` dashboard list.
*   **Root Cause:** Users naturally tunnel-vision directly into the `DiffViewer` detail modal the second a job finishes, bypassing the dashboard entirely.
*   **Action Taken:** Cloned the stat badge rendering logic directly into the `DiffViewer.tsx` header toolbar so they are actively visible during document review.
*   **Rule Added:** (@Design / @PM) If a metric or feature is important enough to query, ensure it is surfaced at the final point of user focus (the detail view), rather than exclusively on the aggregate overview (the list view).

### 2026-02-21 - Race Condition in Terminal States (Missing Stats)
*   **What went wrong:** The user uploaded a file, but the frontend only displayed the `file_size` statistic, entirely omitting the `processing_time` and `complexity` metrics, despite the backend implementation being correct.
*   **Root Cause:** Two compounding issues:
    1.  **State Race Condition:** `celery_worker.py` committed `status="completed"` to Redis *before* committing the terminal timestamp `end_time`. The frontend was polling rapidly (1/sec), caught the `completed` flag exactly in between writes, extracted the payload (which lacked processing time), and promptly permanently halted its polling loop.
    2.  **Stale Containers:** The user was running the API backend via `docker-compose`. We implemented Phase 15 code changes, but background Celery processes do not natively auto-reload when Python files modify, meaning the worker was executing the old function signature without the `end_time` logic!
*   **Action Taken:**
    1. Re-ordered the backend code: The terminal state (`status="completed"`) must strictly be the absolute final line of execution.
    2. Executed `docker-compose restart worker` and `web` to force the Docker containers to pick up the updated source code.
*   **Rule Added:** (@Eng / @Arch) When tracking distributed state flows, ALWAYS commit context parameters and payload values *before* invoking the terminal exit flag. Furthermore, whenever patching backend logic on local-dev systems utilizing Docker networks, force a container restart to clear stale worker memory pools!
