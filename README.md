# CleanOCR: Cloud-Native Historical Text Extraction

**CleanOCR** is a production-hardened platform for extracting high-fidelity text from complex historical documents (19th-century newspapers) using **Google Gemini 2.0 Flash Vision**.

It features a modern **React Console**, a scalable **FastAPI/Celery Backend**, and real-time processing capabilities.

---

## 🚀 Features

*   **⚡ Real-Time Dashboard:** Watch pages process live (Queued -> Processing -> Completed).
*   **📊 Diagnostic Telemetry:** View job performance metrics including upload size, processing duration, and an at-a-glance complexity score.
*   **👁️ Side-by-Side Verification:** Integrated PDF Viewer + Markdown Diff Tool with Zoom controls.
*   **🚀 Accelerated Ingestion:** Concurrent PDF Bursting via hardware-accelerated thread pools natively releasing the GIL.
*   **🧠 Context-Aware Stitching:** Two-Pass Verification automatically detects hyphenation breaks across pages and seamlessly merges them using LLMs.
*   **🛡️ Enterprise-Grade Backend:**
    *   **Streamed Pipeline:** Celery Chords (Producer-Consumer) stream OCR tasks in parallel rather than blocking.
    *   **Input Sanitization:** Blocks malware/fake files via `libmagic`.
    *   **Smart Caching:** SHA-256 deduplication (Process once, serve forever).
    *   **Robust State Tracking:** Atomic Redis counters accurately calculate pipeline progress across disparate worker nodes.
    *   **Structured Logging:** JSON logs ready for Datadog/ELK.
    *   **Resilience:** Browser-local job history persistence (don't lose jobs on refresh).
    *   **Isolation:** Per-job sandboxed workspaces (`workspaces/{guid}`) for safe concurrency.
    *   **Research Ready:** Automated citation generation, YAML frontmatter, and metadata management.

---

## � Zero-Code Install (For Researchers)

Designed for usage without touching the command line.

**1. Install Docker Desktop**
*   Download and install [Docker Desktop for Windows/Mac](https://www.docker.com/products/docker-desktop/).
*   Open it and wait for the whale icon to stop animating.

**2. Configure**
*   Double-click **`start.bat`** (Windows) or **`start.sh`** (Mac/Linux).
*   *First Run:* It will create a `.env` file and ask you to paste your Google API Key.
*   Open `.env` with Notepad, paste your key (`GOOGLE_API_KEY=AI...`), and save.

**3. Launch**
*   Double-click **`start.bat`** again.
*   The system will auto-build and open your browser to **http://localhost:5173** when ready.
*   *Note: Taking a while? Check the black window for progress!*

---

## 🛠️ Developer Install (Terminal)

For engineers who want full control.

### 1. Prerequisites
*   **Docker & Docker Compose**
*   **Google GenAI API Key** (Set in `.env`)

### 2. Run the Stack
```bash
# 1. Clone & Setup Secrets
cp .env.example .env
# (Edit .env with your API Key)

# 2. Launch (Builds everything)
docker-compose up --build
```
Access the console at: **http://localhost:5173**
API Documentation at: **http://localhost:8000/docs**

---

## 🏗 Architecture

### Frontend (`/frontend`)
*   **Stack:** React 18, Vite, TailwindCSS, Framer Motion.
*   **Key Components:**
    *   `UploadZone`: Draggable file upload with immediate validation.
    *   `JobCard`: Live polling of job status (`GET /status/{id}`).
    *   `DiffViewer`: `react-pdf` integration for split-screen audit.

### Backend (`/app`)
*   **Stack:** Python 3.11, FastAPI, Celery, Redis.
*   **Key Files:**
    *   `app/api/server.py`: API Gateway + Static File Serving.
    *   `app/workers/celery_worker.py`: Background OCR pipeline configuration.
    *   `app/services/`: Core logic (PDF conversion, OCR processing, Markdown stitching).

---

## 🧪 Verification

To verify the installation, you can run the included scripts from the `scripts/` directory:
```bash
# Verify API & Worker Lifecycle
python scripts/verify_status_api.py

# Verify Static File Serving
python scripts/verify_static.py

## 🧹 Troubleshooting & Clearing Cache

CleanOCR uses a **Smart Caching** system to deduplicate uploads and save AI processing costs. If you need to re-process a file that was already uploaded (for example, to test new OCR logic or if a job failed), you must clear the Redis cache first.

**To clear the cache manually via terminal:**
```bash
docker-compose exec redis redis-cli FLUSHALL
```

Alternatively, you can use the test scripts to flush it:
```bash
# Advanced Test CLI (Support Cache Flushing)
# Usage: python scripts/test_upload.py [--flush] [--dummy] [--file path/to/pdf]
python scripts/test_upload.py --flush --dummy
```

---

## 📜 License
MIT License. Copyright (c) 2026 Diego Lucero.