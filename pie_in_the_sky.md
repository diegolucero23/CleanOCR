# Pie in the Sky: Roadmap to Production 🚀

This document serves as the backlog for "CleanOCR-Enterprise". It tracks ideas, improvements, and features required to take the system from a working prototype to a robust, scalable, and user-friendly product.

## 1. Infrastructure & DevOps (The Foundation)
- [/] **CI/CD Pipeline Matrix (Set C Active):** Implement GitHub Actions for automated testing (pytest with Redis service), frontend TypeScript/Vite compilation gating, and Docker image building on push/PR.
- [ ] **Nightly Automated Fuzzing:** Run scheduled RedTeam fuzz campaigns in headless CI against mock endpoints to detect regression vulnerabilities.
- [ ] **Infrastructure as Code (IaC):** Use Terraform or Pulumi to define cloud resources (AWS/GCP) to avoid manual configuration drift.
- [ ] **Centralized Logging:** Move beyond local logs. Ship logs to a centralized aggregator (ELK Stack, Loki, or Datadog) for analysis.
- [ ] **Monitoring & Alerting:**
    - Prometheus exporters for FastAPI and Celery.
    - Grafana dashboards for Queue Depth, Error Rates, and Latency.
    - PagerDuty/Slack alerts for critical failures (e.g., Celery worker crash, Gemini API outage).
- [ ] **Seamless Launcher:** `start.bat` / `start.sh` scripts to abstract Docker commands for non-techies.
- [ ] **Secret Management:** Move `.env` files to a secure vault (HashiCorp Vault, AWS Secrets Manager) for production.

## 2. Backend & Architecture (Robustness)
- [x] **Structured Logging:** Convert all log output to JSON format for better parsing and querying.
- [ ] **Dead Letter Queues (DLQ):** Configure Celery to send permanently failed tasks to a separate queue for manual inspection.
- [x] **Rate Limiting:** Implement Token Bucket algorithms (via Redis) to prevent API abuse and manage Gemini API quotas.
- [ ] **Circuit Breakers:** Wrap external calls (Gemini API) in circuit breakers to fail fast during outages and prevent cascading failures.
- [ ] **Idempotency Keys:** Ensure that resubmitting the same file/request doesn't trigger duplicate processing costs.
- [x] **Input Sanitization:** "Trust No One." Validate magic numbers of uploaded files (not just extensions) to prevent malware uploads.
- [x] **Pipeline Concurrency (Celery/Redis):** Transition from sequential blocking (`Burst -> OCR -> Stitch`) to a streamed Producer-Consumer pipeline. As soon as a single page is rendered to PNG, it is dispatched to a Celery worker pool for immediate OCR, drastically reducing total job turnaround time.
- [x] **Concurrent PDF Bursting:** Refactor `pdf_converter.py` to use `ThreadPoolExecutor`, bursting multiple chunks of the PDF into images simultaneously.
- [x] **Workspace Cleanup (Set B Completed):** TTL-based periodic Celery Beat task to delete stale job workspaces, uploaded PDFs, and Redis keys while preserving relational database extraction records. Configurable via `WORKSPACE_TTL_HOURS` env var.
- [x] **Authentication & Authorization:** Add API keys / Bearer tokens to `/upload`, `/status`, and `/stream` endpoints with zero-friction local fallback.
- [ ] **Hardened Archive Ingestion (ZIP/TAR batch upload):** Accept an archive of scans/PDFs as a single upload for batch processing. Must be built hardened from day one — no extraction code exists today, so this is new attack surface: validate extracted paths stay inside the job workspace (Zip Slip), cap total decompressed size and expansion ratio (zip bombs), cap member count and nesting depth (no archives-in-archives), sanitize member filenames before they touch the filesystem, and run every extracted file through the same magic-byte/page-count/pixel-cap checks as a direct upload.
- [ ] **Metadata Input Validation:** Add a Pydantic schema to validate `title`, `volume`, `issue`, `date` fields on upload — currently unvalidated. (Frontmatter escaping is now handled in `stitcher.py`, so malformed YAML is no longer a risk; schema validation for field semantics is still open.)
- [x] **Structured Error Responses:** Standardized error schema with top-level error codes, messages, and details across all API routes.
- [ ] **Dynamic Worker Concurrency:** `MAX_WORKERS=4` is hardcoded in `ocr_processor.py`. Auto-detect via `os.cpu_count()` and expose as a config value so it scales with the host machine.
- [x] **Remove Hardcoded Repair Targets:** `REPAIR_TARGETS` is now an env-driven config value (comma-separated list, empty default); the stitcher audit skips the target check when unset.
- [ ] **Conditional Image Preprocessing:** Deskew adds ~30% overhead on already-clean scans. Add a config flag (or auto-detect scan quality) to skip preprocessing when it isn't needed.
- [ ] **LLM Response Schema Validation:** Replace the 4-layer regex fallback in `stitcher.py::load_and_repair_json()` with strict response schema validation + retry-on-parse-failure to reduce brittleness.

## 3. Core Logic & AI (Accuracy & Cost)
- [ ] **Prompt Experimentation Framework:** automated A/B testing for system prompts to optimize for accuracy vs token cost.
- [x] **Context-Aware OCR Prompting:** Improve accuracy of hyphenated words and sentence breaks across pages by passing the trailing ~50 words of the **previous** page into the Gemini prompt for the **next** page.
- [ ] **Confidence Scoring:** Parse model logprobs (if available) or ask the model to self-evaluate confidence to flag pages for human review.
- [x] **Two-Pass Verification:** Introduce an LLM-powered verification step during the `stitcher.py` phase to fix hallucinated columns, adjust formatting drift, and perform grammar/spell checks on the stitched markdown.
- [ ] **Cost Control:** Implement hard limits on daily API spend.
- [x] **Smart Caching:** Compute SHA-256 hashes of input images. Check DB for existing results before calling AI.
- [ ] **Type Safety:** Enforce strict type hinting (mypy) across the entire codebase.

## 4. Frontend & UX (The "Wow" Factor)
- [x] **Real-Time Feedback:** Replace polling with WebSockets or Server-Sent Events (SSE) for live progress bars. *(Implemented via Smart Polling)*
- [ ] **True Real-Time Push:** Current 1-second polling loop runs unconditionally for all jobs. Replace with Server-Sent Events (SSE) or WebSockets to eliminate wasted connections and enable instant push updates.
- [x] **"Diff" View:** A split-screen interface showing the original PDF page next to the extracted Markdown for easy verification.
- [x] **Drag & Drop Zone:** smooth, animated upload area with file validation warnings.
- [ ] **Issue Explorer:** A dedicated UI for browsing the new `output/issues/` folder structure (Volume/Issue navigation).
- [ ] **Dark Mode:** specific toggle and consistent theme application.
- [ ] **Human-in-the-Loop Interface:** A specific UI for reviewing and correcting "low confidence" pages flagged by the backend.
- [x] **Job History Pagination & Filtering (Set B Completed):** Replaced unbounded `localStorage` job history with a backend-persisted, paginated, searchable, and status-filterable grid/table.

## 5. Data & Storage (Persistence)
- [ ] **Cloud Storage:** Migrate from local `uploads/` to S3/GCS buckets with lifecycle policies (auto-delete after 30 days).
- [x] **Relational Database (Set B Completed):** Introduced SQLAlchemy 2.0 with SQLite default (`workspaces/cleanocr.db`) and PostgreSQL switch via `DATABASE_URL` for structured data (Job history, metadata, and results). Eliminates volatile state loss when Redis restarts.
- [x] **Data Retention Policy (Set B Completed):** TTL-based Celery Beat cleanup task for workspaces, uploads, and Redis keys (`WORKSPACE_TTL_HOURS`) while preserving permanent database records.
- [ ] **Full-Text Search:** No ability to search across extracted documents. Add Elasticsearch or SQLite FTS5 integration for searchable document libraries.

## 6. Consolidation & Refactoring (Clean Code)
- [x] **Package Structure:** Move root scripts (`batch_ocr.py`, `convert_pdf.py`, `worker.py`) into a proper `app/` or `core/` package to reduce root clutter.
- [x] **Script Modernization:** Move legacy debug scripts (`debug_ocr.py`, `stitch_debug.py`) into `scripts/debug/` or `tests/legacy/`.
- [x] **Unified Config:** Audit codebase to ensure `config.py` is the *single* source of truth (remove local constants).

## 7. Testing (Confidence at Scale)
- [ ] **Load Testing:** No tests for concurrent uploads or high-volume PDFs. Add `pytest-asyncio` scenarios with 50+ simultaneous jobs to find Celery queue limits and Redis memory ceilings.
- [/] **Negative / Adversarial Tests (Set C Active):** Broaden coverage for corrupted PDFs, empty files, invalid metadata, SQL injection payloads, rate limit header spoofing, and simulated Redis disconnects.
- [ ] **Historical Transcription Accuracy Benchmarking:** Automated WER/CER (Word Error Rate / Character Error Rate) scoring of Gemini 3.1 Flash Lite transcription against ground-truth transcriptions of 19th-century Mormon history periodicals.
- [ ] **Richer Mock Provider:** `RedTeamMockProvider` returns static fixtures. Generate realistic, dynamic OCR responses keyed to page content so mock-mode tests better reflect real API behavior.

## 8. Documentation & Manuals (Knowledge Base)
- [ ] **Deployment Manual:** Create `manual/deployment.md` for Docker/Cloud deployment steps.
- [ ] **Troubleshooting Guide:** Create `manual/troubleshooting.md` for common errors (Redis connection, API quotas).
- [ ] **Architecture Decision Records (ADR):** Document key decisions (Gemini, Celery, React) in `docs/adr/`.
- [ ] **Inline Docstrings:** Complex logic (Two-Pass Verification, Celery Chord orchestration, JSON repair) has minimal comments. Add docstrings so future maintainers understand intent without reverse-engineering.

## 9. Model Lifecycle & Future Upgrades Roadmap 🗓️

This roadmap tracks external model deprecation dates, price adjustments, and scheduled migrations to ensure CleanOCR operates friction-free and cost-efficiently without service interruptions.

### Milestone 0: Immediate Migration (October 2, 2026) - COMPLETED
*   **Trigger / Deadline:** **October 20, 2026** (Retirement of entire Gemini 2.5 family: `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.5-pro`).
*   **Description:**
    *   Transition Standard Tier to **`gemini-3.1-flash-lite`** ($0.25/1M input, $1.50/1M output — cheapest active model, ~40% cheaper output than 3.5).
    *   Transition Pro Tier to **`gemini-3.8-flash`** with `thinking_level=LOW` to eliminate thinking token bloat ($0.75/1M input, $3.75/1M output).
    *   Transition Fallback Model to **`gemini-3.5-flash-lite`** to guarantee service continuity.
    *   Decouple pre-flight layout detection to hard-pinned **`gemini-3.1-flash-lite`** with `MEDIA_RESOLUTION_LOW` (~258 tokens per page vs ~5,160 tokens previously; 95% reduction on layout check calls).
*   **Identified Locations of Change:**
    *   `app/core/config.py` (Default model values & new `LAYOUT_MODEL_NAME`)
    *   `.env` and `.env.example`
    *   `app/services/google_vision.py` (`detect_layout_type` routing + low resolution; thinking level config)
    *   `tests/test_google_vision.py`, `tests/test_layout_detection.py`
    *   `ARCHITECTURE.md` (§8 Configuration Table)

### Milestone 1: Pricing Review & Pro Tier Adjustment (December 31, 2026)
*   **Trigger / Deadline:** **December 31, 2026** (Introductory pricing on `gemini-3.8-flash` expires; rates double to $1.50/1M input, $7.50/1M output).
*   **Description:**
    *   Review Pro tier usage volume and cost metrics.
    *   If Pro tier costs exceed budget thresholds, switch `PRO_MODEL_NAME` to **`gemini-3.5-flash-lite`** configured with `MEDIA_RESOLUTION_HIGH`, maintaining high transcription quality at ~$0.004/page instead of ~$0.015/page.
*   **Identified Locations of Change:**
    *   `.env`: `PRO_MODEL_NAME`
    *   `app/core/config.py`: default `PRO_MODEL_NAME`
    *   `app/core/cost_guard.py`: spend limits and call cap calibrations

### Milestone 2: Gemini 3.1 Retirement Migration (April / May 2027)
*   **Trigger / Deadline:** **May 7, 2027** (Scheduled retirement of `gemini-3.1-flash-lite`).
*   **Description:**
    *   Migrate Standard Tier (`MODEL_NAME`) from `gemini-3.1-flash-lite` to **`gemini-3.5-flash-lite`** (or the latest successor Flash-Lite GA model).
    *   Migrate `LAYOUT_MODEL_NAME` to `gemini-3.5-flash-lite`.
    *   Update Fallback Model to `gemini-3.8-flash`.
    *   Run full historical regression suite on `latter_day_saints_messenger_and_advocate_vol_1_and_2.pdf` to verify character error rates and reading order.
*   **Identified Locations of Change:**
    *   `app/core/config.py`: `MODEL_NAME`, `LAYOUT_MODEL_NAME`, `FALLBACK_MODEL_NAME`
    *   `.env` and `.env.example`
    *   `tests/test_google_vision.py`, `tests/test_layout_detection.py`
    *   `ARCHITECTURE.md` (§8)

### Milestone 3: Gemini 4 Architecture Review (Late 2027)
*   **Trigger / Deadline:** Q3/Q4 2027 (General availability of Gemini 4 / Argon series).
*   **Description:**
    *   Evaluate native PDF direct ingestion in Gemini 4 vs Poppler rasterization at 300 DPI (potential elimination of `pdf2image` and disk bursting).
    *   Audit local tier models (Gemma 5 / Surya updates) for improved offline throughput.
*   **Identified Locations of Change:**
    *   `app/services/pdf_converter.py`
    *   `app/services/google_vision.py`
    *   `requirements.txt`
