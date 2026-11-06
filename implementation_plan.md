# Implementation Plan: Phase 19 — Production Hardening: Broadsheet Newspapers, Failsafe Timeouts & Quality Guardrails

> **Status:** 🏗️ System Design & Architecture Completed (@Arch) — Ready for Construction & TDD (@Eng)  
> **Authors:** @PM, @Arch, @Eng, @Des, @QA  
> **Governing Standards:** [`AGENTS.md`](AGENTS.md) — Production First, Strict TDD, Full Observability, Idempotency, Continuous Documentation Continuity, Human Decision Gate  
> **Target Subsystems:** FastAPI API Server, Celery Worker Pipeline, Broadsheet Layout Engine, Stitcher Two-Pass Processor, React Frontend  

---

## 1. Executive Summary & Design Goals (@Arch)

Following the production autopsy of **Job `06ebe4c7`** (5-column Deseret News broadsheet stall) and **Job `5446a1b6`** (silent page drop, 150-word stitching repeats, and blank-page hallucination), this plan codifies the complete architectural overhaul to make CleanOCR robust against large-format broadsides, eliminate silent failure modes, and provide real-time user-driven job cancellation.

### Core Architectural Pillars
1. **Interactive Job Cancellation API & Failsafe Watchdogs:** First-class cancellation contract (`POST /jobs/{job_id}/cancel`) with Celery task revocation and automatic task/stream timeout guardrails.
2. **Broadsheet Layout & Payload Pipeline (4, 5, 6 Columns):** Dynamic DPI / downscaling to eliminate 75MB payloads causing Gemini 503 deadlines, plus deprecation of 2-column-only `width // 2` gutter splitting.
3. **Fail-Closed File Integrity & Partial Success Transparency:** Atomic file writes to eliminate 0-byte cache poisoning (Page 25 drop), and promotion of failed pages into an honest `partial_failure` status rather than fake `completed`.
4. **Boundary Stitching Deduplication:** Seamless splicing of boundary hyphenation without injecting duplicate 300-word `[LLM Boundary Fix]` blockquotes.
5. **Blank Page & Bleed-Through Protocol:** Prompt contract enabling safe empty-string returns on blank or bleed-through scans.
6. **Recalibrated Real-Time Dynamic Estimator:** Formula based on empirical 1.5–2.5s/page throughput with Gemini 3.1 Flash Lite.
7. **Embedded PDF Text-Layer Ratio Guard:** Guardrail flagging pages where OCR words diverge by $>15\%$ from embedded text.

---

## 2. API Contracts & Endpoint Definitions (@Arch)

### A. Job Cancellation Endpoint: `POST /jobs/{job_id}/cancel`

Allows users or automated watchdogs to cleanly abort in-flight jobs, revoking pending Celery tasks and updating persistent records.

*   **URL:** `/jobs/{job_id}/cancel`
*   **Method:** `POST`
*   **Auth:** Required via `verify_api_key` (`X-API-Key` header or `Authorization: Bearer <key>`)
*   **Rate Limiting:** `rate_limit_status` (60 req/min)
*   **Request Headers:**
    *   `Content-Type: application/json`
    *   `X-API-Key: <key>`
*   **Request Body (Optional):**
    ```json
    {
      "reason": "User requested cancellation via UI"
    }
    ```
*   **Success Response (HTTP 200 OK):**
    ```json
    {
      "job_id": "06ebe4c7-33dd-404c-99a2-67b5fc305e64",
      "status": "cancelled",
      "message": "Job successfully cancelled. Active workers revoked.",
      "cancelled_at": 1793946640.85,
      "details": {
        "processed_pages": 2,
        "total_pages": 4,
        "reason": "User requested cancellation via UI"
      }
    }
    ```
*   **Error Responses:**
    *   `HTTP 400 Bad Request`:
        ```json
        {
          "error": {
            "code": "JOB_ALREADY_TERMINAL",
            "message": "Job is already completed and cannot be cancelled.",
            "details": {"status": "completed"}
          }
        }
        ```
    *   `HTTP 404 Not Found`:
        ```json
        {
          "error": {
            "code": "JOB_NOT_FOUND",
            "message": "No job found with id: 00000000-0000-0000-0000-000000000000"
          }
        }
        ```
    *   `HTTP 401 Unauthorized` / `HTTP 429 Too Many Requests` (Standard envelopes).

---

### B. Recalibrated Time Budget & Limits Disclosure: `GET /limits` & Upload Expectations

Update `compute_stream_timeout_seconds` and expectations in `POST /upload`:

*   **Realistic Expected Duration:**
    $$\text{expected\_duration\_seconds} = 20 + \text{pages} \times 3$$
*   **Maximum Stream Timeout (Safety Guardrail):**
    $$\text{stream\_timeout\_seconds} = \max(120, 2 \times \text{expected\_duration\_seconds})$$
*   **Response Payload Contract (`POST /upload`):**
    ```json
    {
      "job_id": "9738c86f-...",
      "task_id": "9738c86f-...",
      "status": "queued",
      "expectations": {
        "page_count": 52,
        "estimated_duration_seconds": 176,
        "stream_timeout_seconds": 352,
        "limits": {
          "max_upload_mb": 500,
          "max_pdf_pages": 1000,
          "render_dpi": 200,
          "max_page_pixels": 89478485
        }
      }
    }
    ```

---

## 3. System Architecture & Component Design (@Arch)

### A. End-to-End Processing Flow with Failsafes

```mermaid
flowchart TD
    User["Client (Browser / API)"] -->|POST /upload| Web["FastAPI Web API"]
    User -->|POST /jobs/{id}/cancel| Web
    
    Web -->|Enqueue Chord| Broker["Redis Broker"]
    Web -->|Write Job(queued)| DB["SQLite / PostgreSQL DB"]
    
    subgraph CeleryWorker["Celery Worker Pool"]
        WorkerChild["ocr_page_task<br/>(soft_limit: 150s, hard_limit: 180s)"]
        Watchdog["Task Revocation & Watchdog"]
        
        Broker --> WorkerChild
        WorkerChild -->|1. Check DPI & Pixels| Downscaler["Adaptive Image Normalizer<br/>(Cap at 4096px / 36MP)"]
        Downscaler -->|2. Gemini API Call| Gemini["Google Gemini 3.1 Flash Lite"]
        Gemini -->|3. Validate String & JSON| Validator["Atomic JSON Writer<br/>(.tmp -> .json)"]
        Validator -->|4. Return Result Dict| ChordCallback["stitch_markdown_task"]
    end
    
    ChordCallback -->|Audit Missing/Failed Pages| Evaluator{"All Pages Succeeded?"}
    Evaluator -->|Yes| Complete["Job Status: completed"]
    Evaluator -->|No (Some Failed)| Partial["Job Status: partial_failure<br/>(List Dropped Pages)"]
    Evaluator -->|All Failed| Failed["Job Status: failed"]
    
    Complete --> DB
    Partial --> DB
    Failed --> DB
```

---

### B. Detailed Subsystem Specifications

#### 1. Broadsheet Image Normalization (`app/core/image_utils.py`)
*   **Problem:** 75MB PNGs with 114 Million Pixels cause `DecompressionBombWarning` in Pillow and trigger `503 UNAVAILABLE: Deadline expired` from Gemini's payload gateway.
*   **Specification:**
    ```python
    MAX_IMAGE_DIMENSION = 4096
    MAX_SAFE_PIXELS = 36_000_000  # 36 Megapixels (~6000x6000)

    def normalize_broadsheet_image(pil_img: Image.Image) -> Image.Image:
        """Downscales oversized broadside scans while maintaining 100% text legibility."""
        width, height = pil_img.size
        total_pixels = width * height
        if total_pixels > MAX_SAFE_PIXELS or max(width, height) > MAX_IMAGE_DIMENSION:
            scale = min(MAX_IMAGE_DIMENSION / width, MAX_IMAGE_DIMENSION / height)
            new_size = (int(width * scale), int(height * scale))
            return pil_img.resize(new_size, Image.Resampling.LANCZOS)
        return pil_img
    ```
*   **Multi-Column Padding Deprecation:**
    *   Remove destructive `_add_padding` (`width // 2`) from multi-column execution path.
    *   For broadsheet documents (4, 5, 6 columns), the downscaled normalized image is sent directly with the enhanced reading-order prompt, allowing Gemini's spatial attention to read columns sequentially without artificial midline cuts.

#### 2. Atomic Output Writing (`app/services/ocr_processor.py`)
*   **Problem:** `open(json_path, "w")` creates a 0-byte file before checking if `response_text` is non-null. On retry, `os.path.exists()` skips the 0-byte file.
*   **Specification:**
    ```python
    def write_atomic_json(output_path: str, data_str: str) -> None:
        if not data_str or not isinstance(data_str, str) or len(data_str.strip()) == 0:
            raise ValueError("Cannot write empty OCR response")
        # Validate JSON parseable before touching disk
        json.loads(data_str)
        tmp_path = output_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data_str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, output_path)
    ```
*   **Skip Condition:**
    ```python
    if os.path.exists(json_path) and os.path.getsize(json_path) > 10:
        return f"[{index+1}/{total_files}] Skipped {filename} (Exists)"
    ```

#### 3. Celery Task Timeouts & Honest Job Reporting (`app/workers/celery_worker.py`)
*   **Task Configuration:**
    ```python
    @celery_app.task(
        name="ocr_page_task",
        bind=True,
        max_retries=2,
        default_retry_delay=15,
        time_limit=180,       # SIGKILL hard limit
        soft_time_limit=150,  # SoftTimeLimitExceeded exception
    )
    def ocr_page_task(self, job_id, img_filename, input_images_dir, ocr_json_dir):
        ...
    ```
*   **Honest Failure Tracking:**
    *   If a page permanently fails, return `{"page": img_filename, "success": False, "error": str(exc)}`.
    *   DO NOT increment `cache:{job_id}:completed_pages` for failed pages; increment `cache:{job_id}:failed_pages`.
*   **Chord Callback (`stitch_markdown_task`):**
    *   If `succeeded == total_pages`: `status = "completed"`.
    *   If `0 < succeeded < total_pages`: `status = "partial_failure"`, store missing page list in `JobModel.error_message`.
    *   If `succeeded == 0`: `status = "failed"`.

#### 4. Stitcher Boundary Deduplication (`app/services/stitcher.py`)
*   **Problem:** Two-pass verification injects the entire 300-word blockquote `[LLM Boundary Fix]` into the text, duplicating 150 words from the previous page and 150 words from the current page.
*   **Specification:**
    *   When hyphenation is detected between `prev_sample` (trailing 150 words of Page $N-1$) and `next_sample` (leading 150 words of Page $N$):
    *   Ask LLM to return strictly the resolved connecting sentence (e.g. "dis- / course" $\to$ "discourse").
    *   Splice the resolved connecting word directly into Page $N-1$'s tail and trim Page $N$'s head.
    *   Remove the duplicate `> **[LLM Boundary Fix]**` markdown blockquote insertion entirely.

#### 5. Blank Page & Bleed-Through Protocol (`app/core/prompts.py`)
*   **Prompt Contract Update:**
    ```text
    3. **Blank / Empty Page Protocol**:
       - If the page contains NO intentional printed text (e.g. blank page, illustration, or faint bleed-through from reverse side):
         Set "is_blank": true and "markdown_content": "".
       - DO NOT invent, hallucinate, or extrapolate names, directories, or text from faint bleed-through.
    ```
*   **Stitcher Handling:**
    *   If `data.get("is_blank") is True` or `data.get("markdown_content", "").strip() == ""`:
        Insert an explicit visual indicator: `*<!-- Page {num} is blank -->*` without failing the stitcher.

#### 6. PDF Embedded Text-Layer Ratio Guard (`app/services/pdf_validator.py`)
*   **Specification:**
    *   Using Poppler `pdftotext` (already installed and verified in PATH), extract text per page into memory if available.
    *   Calculate embedded word count: `pdf_words = len(page_text.split())`.
    *   If `pdf_words >= 50`:
        Compute ratio: $R = \frac{\text{ocr\_words}}{\text{pdf\_words}}$.
        If $R < 0.85$ or $R > 1.15$:
        Append warning flag to page JSON metadata:
        `"quality_warning": "Word count divergence detected (ratio: {R:.2f}). Possible missing or hallucinated text."`

---

## 4. UI/UX Design Standards & Interaction Contracts (@Des)

1. **Job Cancellation Micro-Interaction:**
   * In `JobCard.tsx` and `JobHistory.tsx`:
   * Render an interactive "Cancel Job" button with a red/amber outline when `status === "queued" || status === "processing"`.
   * On click: Show an inline confirmation popover (zero `window.confirm`!).
   * On confirmation: Send `POST /jobs/{id}/cancel`, disable button, show spinner, and animate status transition to `cancelled` with a styled badge.
2. **Partial Failure Transparency:**
   * If `status === "partial_failure"`: Render an amber warning badge with tooltip: `"Completed with 2 dropped pages (Pages 1, 2). Click to inspect error."`
3. **Realistic Time Estimates:**
   * Display realistic duration in `JobCard`: `"Estimated: ~2 min (Timeout: 4 min)"`.

---

## 5. Proactive Documentation Suggestions (@Arch)

1. **`ARCHITECTURE.md` (§3 Processing Pipeline & §8 Configuration):**
   * Document `POST /jobs/{job_id}/cancel` API contract and Celery revocation sequence.
   * Document broadsheet downscaling policy (`MAX_IMAGE_DIMENSION=4096`, `MAX_SAFE_PIXELS=36M`).
   * Document new `partial_failure` status semantics in relational database schema.
2. **`README.md` (Operational Limits):**
   * Update the Supported Document Formats section to highlight broadsheet newspaper support (up to 6 columns) and explain automated downscaling.

---

## Persona Exit Gate Checklist (@Arch)
- [x] **`implementation_plan.md`:** Updated with complete architecture, algorithms, and specifications.
- [x] **API Contracts:** `POST /jobs/{job_id}/cancel` and `POST /upload` expectations explicitly defined.
- [x] **Architecture Diagrams:** Mermaid flowcharts detailing worker lifecycle, failsafes, and chord aggregation.
- [x] **Documentation Suggestions:** Suggested updates for `ARCHITECTURE.md` and `README.md`.

*Handoff to @Eng to begin construction and strict test-first development.*
