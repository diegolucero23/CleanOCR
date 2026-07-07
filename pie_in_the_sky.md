# Pie in the Sky: Roadmap to Production 🚀

This document serves as the backlog for "CleanOCR-Enterprise". It tracks ideas, improvements, and features required to take the system from a working prototype to a robust, scalable, and user-friendly product.

## 1. Infrastructure & DevOps (The Foundation)
- [ ] **CI/CD Pipeline:** Implement GitHub Actions for automated testing (pytest) and Docker image building on push.
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
- [ ] **Rate Limiting:** Implement Token Bucket algorithms (via Redis) to prevent API abuse and manage Gemini API quotas.
- [ ] **Circuit Breakers:** Wrap external calls (Gemini API) in circuit breakers to fail fast during outages and prevent cascading failures.
- [ ] **Idempotency Keys:** Ensure that resubmitting the same file/request doesn't trigger duplicate processing costs.
- [x] **Input Sanitization:** "Trust No One." Validate magic numbers of uploaded files (not just extensions) to prevent malware uploads.
- [x] **Pipeline Concurrency (Celery/Redis):** Transition from sequential blocking (`Burst -> OCR -> Stitch`) to a streamed Producer-Consumer pipeline. As soon as a single page is rendered to PNG, it is dispatched to a Celery worker pool for immediate OCR, drastically reducing total job turnaround time.
- [x] **Concurrent PDF Bursting:** Refactor `pdf_converter.py` to use `ThreadPoolExecutor`, bursting multiple chunks of the PDF into images simultaneously.
- [x] **Workspace Cleanup:** TTL-based periodic Celery Beat task to delete stale job workspaces, uploaded PDFs, and Redis keys. Configurable via `WORKSPACE_TTL_HOURS` env var.
- [ ] **Authentication & Authorization:** Add JWT tokens or API keys to `/upload` and `/status` endpoints. Without auth, any user can read any job's results and upload arbitrary files.
- [ ] **Hardened Archive Ingestion (ZIP/TAR batch upload):** Accept an archive of scans/PDFs as a single upload for batch processing. Must be built hardened from day one — no extraction code exists today, so this is new attack surface: validate extracted paths stay inside the job workspace (Zip Slip), cap total decompressed size and expansion ratio (zip bombs), cap member count and nesting depth (no archives-in-archives), sanitize member filenames before they touch the filesystem, and run every extracted file through the same magic-byte/page-count/pixel-cap checks as a direct upload.
- [ ] **Metadata Input Validation:** Add a Pydantic schema to validate `title`, `volume`, `issue`, `date` fields on upload — currently unvalidated. (Frontmatter escaping is now handled in `stitcher.py`, so malformed YAML is no longer a risk; schema validation for field semantics is still open.)
- [ ] **Structured Error Responses:** `/upload` currently swallows inner exceptions and returns a generic 500. Log full tracebacks and return structured error JSON with a `code` field.
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
- [ ] **Job History Pagination:** `localStorage` job history is unbounded — UI slows noticeably with 100+ jobs. Cap at the last 50 entries or implement pagination/archival.

## 5. Data & Storage (Persistence)
- [ ] **Cloud Storage:** Migrate from local `uploads/` to S3/GCS buckets with lifecycle policies (auto-delete after 30 days).
- [ ] **Relational Database:** Introduce PostgreSQL for structured data (User accounts, Job history, Billing) instead of relying solely on Redis/Files modules. Currently, all job metadata is volatile (Redis) or client-side only (`localStorage`) — a Redis restart wipes all job history.
- [x] **Data Retention Policy:** TTL-based Celery Beat cleanup task for workspaces, uploads, and Redis keys (`WORKSPACE_TTL_HOURS`).
- [ ] **Full-Text Search:** No ability to search across extracted documents. Add Elasticsearch or SQLite FTS5 integration for searchable document libraries.

## 6. Consolidation & Refactoring (Clean Code)
- [x] **Package Structure:** Move root scripts (`batch_ocr.py`, `convert_pdf.py`, `worker.py`) into a proper `app/` or `core/` package to reduce root clutter.
- [x] **Script Modernization:** Move legacy debug scripts (`debug_ocr.py`, `stitch_debug.py`) into `scripts/debug/` or `tests/legacy/`.
- [x] **Unified Config:** Audit codebase to ensure `config.py` is the *single* source of truth (remove local constants).

## 7. Testing (Confidence at Scale)
- [ ] **Load Testing:** No tests for concurrent uploads or high-volume PDFs. Add `pytest-asyncio` scenarios with 50+ simultaneous jobs to find Celery queue limits and Redis memory ceilings.
- [ ] **Negative / Adversarial Tests:** No coverage for corrupted PDFs, empty files, invalid metadata, or simulated network failures. Untested error paths risk silent crashes in production.
- [ ] **Richer Mock Provider:** `RedTeamMockProvider` returns static fixtures. Generate realistic, dynamic OCR responses keyed to page content so mock-mode tests better reflect real API behavior.

## 8. Documentation & Manuals (Knowledge Base)
- [ ] **Deployment Manual:** Create `manual/deployment.md` for Docker/Cloud deployment steps.
- [ ] **Troubleshooting Guide:** Create `manual/troubleshooting.md` for common errors (Redis connection, API quotas).
- [ ] **Architecture Decision Records (ADR):** Document key decisions (Gemini, Celery, React) in `docs/adr/`.
- [ ] **Inline Docstrings:** Complex logic (Two-Pass Verification, Celery Chord orchestration, JSON repair) has minimal comments. Add docstrings so future maintainers understand intent without reverse-engineering.
