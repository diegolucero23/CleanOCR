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
- [ ] **Circuit Breakers:** Wrap external calls (Gemini API) in circuit breakers to fail fast during outages and prevent cascading failures.
- [ ] **Idempotency Keys:** Ensure that resubmitting the same file/request doesn't trigger duplicate processing costs.
- [x] **Input Sanitization:** "Trust No One." Validate magic numbers of uploaded files (not just extensions) to prevent malware uploads.
- [x] **Pipeline Concurrency (Celery/Redis):** Transition from sequential blocking (`Burst -> OCR -> Stitch`) to a streamed Producer-Consumer pipeline. As soon as a single page is rendered to PNG, it is dispatched to a Celery worker pool for immediate OCR, drastically reducing total job turnaround time.
- [x] **Concurrent PDF Bursting:** Refactor `pdf_converter.py` to use `ThreadPoolExecutor`, bursting multiple chunks of the PDF into images simultaneously.

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
- [x] **"Diff" View:** A split-screen interface showing the original PDF page next to the extracted Markdown for easy verification.
- [x] **Drag & Drop Zone:** smooth, animated upload area with file validation warnings.
- [ ] **Issue Explorer:** A dedicated UI for browsing the new `output/issues/` folder structure (Volume/Issue navigation).
- [ ] **Dark Mode:** specific toggle and consistent theme application.
- [ ] **Human-in-the-Loop Interface:** A specific UI for reviewing and correcting "low confidence" pages flagged by the backend.

## 5. Data & Storage (Persistence)
- [ ] **Cloud Storage:** Migrate from local `uploads/` to S3/GCS buckets with lifecycle policies (auto-delete after 30 days).
- [ ] **Relational Database:** Introduce PostgreSQL for structured data (User accounts, Job history, Billing) instead of relying solely on Redis/Files modules.
- [ ] **Data Retention Policy:** Automated cleanup scripts for old artifacts to manage storage costs.

## 6. Consolidation & Refactoring (Clean Code)
- [x] **Package Structure:** Move root scripts (`batch_ocr.py`, `convert_pdf.py`, `worker.py`) into a proper `app/` or `core/` package to reduce root clutter.
- [x] **Script Modernization:** Move legacy debug scripts (`debug_ocr.py`, `stitch_debug.py`) into `scripts/debug/` or `tests/legacy/`.
- [x] **Unified Config:** Audit codebase to ensure `config.py` is the *single* source of truth (remove local constants).

## 7. Documentation & Manuals (Knowledge Base)
- [ ] **Deployment Manual:** Create `manual/deployment.md` for Docker/Cloud deployment steps.
- [ ] **Troubleshooting Guide:** Create `manual/troubleshooting.md` for common errors (Redis connection, API quotas).
- [ ] **Architecture Decision Records (ADR):** Document key decisions (Gemini, Celery, React) in `docs/adr/`.
