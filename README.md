# CleanOCR: Cloud-Native Historical Text Extraction

**CleanOCR** is a production-hardened platform for extracting high-fidelity text from complex historical documents (19th-century newspapers) using **Google Gemini Vision** (Gemini 3.1 Flash Lite / Gemini 3.8 Flash).

It features a modern **React Console**, a scalable **FastAPI/Celery Backend**, and real-time processing capabilities.

---

## 🚀 Features

*   **⚡ Real-Time Dashboard:** Watch pages process live (Queued -> Processing -> Completed).
*   **📊 Diagnostic Telemetry:** View job performance metrics including upload size, processing duration, and an at-a-glance complexity score.
*   **👁️ Side-by-Side Verification:** Integrated PDF Viewer + Markdown Diff Tool with mobile-first responsive stacked/split view.
*   **🚀 Accelerated Ingestion:** Concurrent PDF Bursting via hardware-accelerated thread pools natively releasing the GIL.
*   **🧠 Context-Aware Stitching:** Two-Pass Verification automatically detects hyphenation breaks across pages and seamlessly merges them using LLMs.
*   **🛡️ Enterprise-Grade Backend:**
    *   **Streamed Pipeline:** Celery Chords (Producer-Consumer) stream OCR tasks in parallel rather than blocking.
    *   **Input Sanitization:** Blocks malware/fake files via `libmagic`.
    *   **Relational Persistence (SQLAlchemy 2.0):** Zero-config SQLite database (`workspaces/cleanocr.db`), switchable to PostgreSQL via `DATABASE_URL`. Stores complete jobs, metadata, and extracted text.
    *   **Persistent Job History API:** `GET /jobs` (paginated, searchable, status-filtered) and `GET /jobs/{job_id}` with automatic Redis-to-DB fallback.
    *   **Interactive Job Cancellation:** `POST /jobs/{job_id}/cancel` endpoint and one-click UI cancel button revokes in-flight Celery workers cleanly.
    *   **Broadsheet & Multi-Column Newspapers:** Adaptive image normalization downscales oversized 70MB+ broadside scans (capped at 4096px / 36MP), eliminating Gemini 503 payload timeouts on 4, 5, and 6-column historical newspapers.
    *   **Fail-Closed File Integrity:** Atomic file writes eliminate 0-byte cache poisoning, and dropped pages are honestly surfaced as `partial_failure`.
    *   **Security & Access Control:** Optional server API key protection (`CLEANOCR_API_KEY`) with seamless local dev fallback and interactive UI key management.
    *   **Rate Limiting & Quota Guard:** Redis-backed sliding-window throttling (3 uploads/min, 60 status checks/min) to prevent quota exhaustion.
    *   **Smart Caching:** SHA-256 deduplication (Process once, serve forever).
    *   **Robust State Tracking:** Atomic Redis counters accurately calculate pipeline progress across worker nodes.
    *   **Structured Logging:** JSON logs ready for Datadog/ELK.
    *   **Resilience:** Dual-layer state persistence (Redis fast-path + SQL database recovery).
    *   **Isolation:** Per-job sandboxed workspaces (`workspaces/{guid}`) for safe concurrency.
    *   **Research Ready:** Automated citation generation, YAML frontmatter, and metadata management.

---

## 💻 Zero-Code Install (For Researchers)

Designed for usage without touching the command line.

**1. Install Docker Desktop**
*   Download and install [Docker Desktop for Windows/Mac](https://www.docker.com/products/docker-desktop/).
*   Open it and wait for the whale icon to stop animating.

**2. Configure**
*   Double-click **`start.bat`** (Windows) or **`start.sh`** (Mac/Linux).
*   *First Run:* It will create a `.env` file and ask you to paste your Google API Key.
*   Open `.env` with Notepad, paste your key (`GOOGLE_API_KEY=AI...`), and save.
*   🔒 Restrict the key to the Generative Language API only, and never commit `.env` — see [SECURITY.md](SECURITY.md) for key scoping, secret scanning, and the built-in API spend caps.

**3. Launch**
*   Double-click **`start.bat`** again.
*   The system will auto-build and open your browser to **http://localhost:5173** when ready.
*   *Note: Taking a while? Check the black window for progress!*

---

## 🛠️ Developer Install (Terminal)

For engineers who want full control.

### 1. Prerequisites
*   **Docker & Docker Compose**
*   **Node.js 20+** (for the frontend dev server)
*   **Google GenAI API Key** (Set in `.env`)

### 2. Start the Backend (Docker)
```bash
# 1. Clone & Setup Secrets
cp .env.example .env
# (Edit .env with your API Key)

# 2. Launch API + Worker + Redis
docker-compose up --build
```
API live at: **http://localhost:8000**  
API docs at: **http://localhost:8000/docs**

### 3. Start the Frontend (Vite dev server)

The React frontend runs **outside Docker** as a local Vite dev server:

```bash
cd frontend
npm install      # first time only
npm run dev
```
Frontend live at: **http://localhost:5173**

> The frontend proxies API calls to `localhost:8000`, so the Docker backend must be running first.

> **Experimental:** a next-generation dark-theme document editor UI lives in [`frontend-v2/`](frontend-v2/) — `cd frontend-v2 && npm install && npm run dev`, served at **http://localhost:5174** (proxies `/api` and `/uploads` to the backend). The frontend above remains the default.

---

## 🏗 Architecture

### Frontend (`/frontend`)
*   **Stack:** React 18, Vite, TailwindCSS, Framer Motion.
*   **Key Components:**
    *   `UploadZone`: Draggable file upload with immediate validation.
    *   `JobHistory`: Paginated, searchable, status-filtered history with mobile-first responsiveness (stacked cards <640px, full table >=640px).
    *   `JobCard`: Live polling of job status (`GET /status/{id}`).
    *   `DiffViewer`: `react-pdf` integration for split-screen audit with 320px mobile viewport support.
    *   `NotificationToast`: Animated structured error toasts with live second-by-second 429 countdown.

### Backend (`/app`)
*   **Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Celery, Redis.
*   **Key Packages:**
    *   `app/api/server.py`: API Gateway + Static File Serving.
    *   `app/db/`: Relational persistence models (`JobModel`, `JobMetadataModel`, `JobResultModel`) with SQLite WAL pragma and PostgreSQL support.
    *   `app/core/security.py`: API Key verification and Redis-backed sliding-window rate limiting.
    *   `app/workers/celery_worker.py`: Background OCR pipeline configuration & Celery Beat workspace retention daemon.
    *   `app/services/`: Core logic (PDF conversion, OCR processing, Markdown stitching, layout detection).

---

## 🧪 Testing & Verification

### 1. Automated Test Suite (Pytest)
Run the full backend regression suite (all 209 tests):
```bash
# Using project virtualenv
python -m pytest

# Run specific suites
python -m pytest tests/test_ci_pipeline.py
python -m pytest tests/test_persistence_db.py
python -m pytest tests/test_auth_and_rate_limit.py
```

> **Windows Note:** Ensure Poppler is installed (`winget install oschwartz10612.Poppler`). `config.py` automatically detects Poppler in your system PATH.

> **Match CI before pushing:** CI runs the tests against a live Redis. Start Redis locally first (for example `docker run -d -p 6379:6379 redis:7-alpine`, or `redis-server`). Without it, rate limiting and caching quietly fail open, so a green local run can still fail in CI.

### 2. Live Verification Scripts
To verify against a running Docker stack:
```bash
# Verify API & Worker Lifecycle
python scripts/verify_status_api.py

# Verify Static File Serving
python scripts/verify_static.py

# Advanced Test CLI (Supports Cache Flushing & Mock PDF)
python scripts/test_upload.py --flush --dummy
``` 

### 3. Adversarial & Chaos Testing (@RedTeam)
Run the automated chaos campaign (10 attack vectors) under mandatory safety interlock:
```bash
# Execute local RedTeam Chaos Suite
python tests/redteam_artifacts/campaign_3_adversarial.py

# Run containerized RedTeam stress network (capped at 512MB RAM, 0.5 CPU)
cp .env.redteam.example .env.redteam
docker-compose -f docker-compose.redteam.yml up --build
```
> See [`tests/redteam_artifacts/README.md`](tests/redteam_artifacts/README.md) for safety interlocks, fuzzing vectors, and cleanup guidelines.

### 4. CI/CD Matrix Pipeline (GitHub Actions)
Continuous integration is orchestrated via [`.github/workflows/ci.yml`](.github/workflows/ci.yml):
*   **`secret-scan`:** Gitleaks scans entire git history against leaked keys.
*   **`test`:** Python 3.11 test matrix runs full pytest suite against a live Redis service container.
*   **`frontend-build`:** Node.js 20.x executes TypeScript check (`tsc -b`) and Vite production bundle (`npm run build`).
*   **`build`:** Docker container build executes, gated on passing backend tests and passing frontend build.

---

## 🧹 Troubleshooting & Clearing Cache

CleanOCR uses a **Smart Caching** system to deduplicate uploads and save AI processing costs. If you need to re-process a file that was already uploaded (for example, to test new OCR logic or if a job failed), clear the Redis cache:

```bash
docker-compose exec redis redis-cli FLUSHALL
```

---

## 📜 License
MIT License. Copyright (c) 2026 Diego Lucero.
