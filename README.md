# CleanOCR: Cloud-Native Historical Text Extraction

**CleanOCR** is a production-hardened platform for extracting high-fidelity text from complex historical documents (19th-century newspapers) using **Google Gemini 2.0 Flash Vision**.

It features a modern **React Console**, a scalable **FastAPI/Celery Backend**, and real-time processing capabilities.

---

## 🚀 Features

*   **⚡ Real-Time Dashboard:** Watch pages process live (Queued -> Processing -> Completed).
*   **👁️ Side-by-Side Verification:** Integrated PDF Viewer + Markdown Diff Tool with Zoom controls.
*   **🛡️ Enterprise-Grade Backend:**
    *   **Input Sanitization:** Blocks malware/fake files via `libmagic`.
    *   **Smart Caching:** SHA-256 deduplication (Process once, serve forever).
    *   **Async Processing:** Celery + Redis for reliable background jobs.
    *   **Structured Logging:** JSON logs ready for Datadog/ELK.

---

## 🛠 Quick Start

### 1. Prerequisites
*   **Docker & Docker Compose**
*   **Google GenAI API Key** (Set in `.env`)

### 2. Run the Stack
```bash
# 1. Clone & Setup Secrets
cp .env.example .env

# 2. Launch (Builds everything)
docker-compose up --build
```
Access the console at: **http://localhost:5173** (or port 80 based on configuration)
API Documentation at: **http://localhost:8000/docs**

---

## 🏗 Architecture

### Frontend (`/frontend`)
*   **Stack:** React 18, Vite, TailwindCSS, Framer Motion.
*   **Key Components:**
    *   `UploadZone`: Draggable file upload with immediate validation.
    *   `JobCard`: Live polling of job status (`GET /status/{id}`).
    *   `DiffViewer`: `react-pdf` integration for split-screen audit.

### Backend (`/`)
*   **Stack:** Python 3.11, FastAPI, Celery, Redis.
*   **Key Files:**
    *   `server.py`: API Gateway + Static File Serving (`/uploads`).
    *   `worker.py`: Background OCR pipeline (Burst -> OCR -> Stitch).

---

## 🧪 Verification

To verify the installation, you can run the included scripts:
```bash
# Verify API & Worker Lifecycle
python verify_status_api.py

# Verify Static File Serving
python verify_static.py
```

---

## 📜 License
MIT License. Copyright (c) 2026 Diego Lucero.