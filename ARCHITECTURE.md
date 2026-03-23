# CleanOCR — Architecture Guide

> **Audience:** AI agents and developers dropped into this codebase cold.
> For agent roles and workflow rules see [`AGENTS.md`](AGENTS.md).
> For the product roadmap see [`pie_in_the_sky.md`](pie_in_the_sky.md).
> For historical decisions see [`Context.md`](Context.md).

---

## 1. One-Paragraph Summary

CleanOCR is a three-process distributed system: a **FastAPI web server** accepts PDF uploads and serves results, a **Celery worker** runs the OCR pipeline in the background, and **Redis** acts as both the message broker and the ephemeral state store. The frontend is a standalone **React 18 / Vite** SPA served by a separate dev server (proxied in dev, served statically in production). A job moves through the states `queued → processing → completed | failed`, and progress is pushed to the browser in real time via **Server-Sent Events (SSE)**.

---

## 2. Repository Map

```
CleanOCR/
│
├── app/                        ← Python backend package
│   ├── api/
│   │   └── server.py           ★ ENTRY POINT — FastAPI app, all HTTP endpoints
│   ├── core/
│   │   ├── config.py           ★ Single source of truth for all config/env vars
│   │   ├── prompts.py          Gemini vision prompt template
│   │   └── image_utils.py      Deskew + padding preprocessing (stateless)
│   ├── services/
│   │   ├── ocr_interface.py    Abstract base class OCRProvider
│   │   ├── ocr_factory.py      Factory: returns Google or Mock provider
│   │   ├── google_vision.py    Gemini 2.0 Flash implementation
│   │   ├── pdf_converter.py    PDF → PNG via pdf2image + ThreadPoolExecutor
│   │   ├── ocr_processor.py    Per-page OCR with exponential-backoff retry
│   │   └── stitcher.py         Assembles page JSON → final Markdown
│   └── workers/
│       └── celery_worker.py    ★ ENTRY POINT — Celery app + all task definitions
│
├── frontend/
│   └── src/
│       ├── App.tsx             ★ ENTRY POINT — root component, SSE subscriptions
│       ├── components/         UI components (JobCard, DiffViewer, UploadZone …)
│       ├── hooks/
│       │   └── useJobPersistence.ts  localStorage job history (max 50 entries)
│       └── lib/
│           ├── api.ts          ★ HTTP + SSE client for the backend API
│           └── utils.ts        Shared utilities
│
├── tests/                      Pytest unit + integration tests
├── scripts/                    CLI verification + debug helpers
│
├── docker-compose.yml          ★ Defines redis / web / worker services
├── Dockerfile                  Single image used by both web and worker
├── requirements.txt            Python dependencies
└── .env                        Secrets (never committed) — see §8 for all vars
```

★ = best starting point for a given concern.

---

## 3. Process Architecture

Three Docker services share the same image and the same mounted volume:

```
┌─────────────────┐      HTTP       ┌─────────────────────────────────┐
│  Browser        │ ◄────────────── │  web  (uvicorn / FastAPI :8000) │
│  React SPA      │ ◄── SSE stream  │  app/api/server.py              │
│  :5173 (dev)    │                 └──────────────┬──────────────────┘
└─────────────────┘                                │ enqueue task
                                                   ▼
                                   ┌─────────────────────────────────┐
                                   │  redis  (:6379)                 │
                                   │  • Celery broker + backend      │
                                   │  • Ephemeral job state store    │
                                   └──────────────┬──────────────────┘
                                                   │ consume task
                                                   ▼
                                   ┌─────────────────────────────────┐
                                   │  worker  (celery)               │
                                   │  app/workers/celery_worker.py   │
                                   └─────────────────────────────────┘
```

The `web` and `worker` containers mount the project root at `/app`, so they
share the `workspaces/` and `uploads/` directories on the host filesystem.

To run a **Celery Beat scheduler** for periodic cleanup (optional):
```bash
celery -A app.workers.celery_worker.celery_app beat --loglevel=info
```

---

## 4. End-to-End Request Lifecycle

### 4a. Upload

```
Browser
  └─ POST /api/upload  (multipart: file + optional metadata fields)
       │
       ├─ Validate MIME type via libmagic (rejects non-PDFs with 400)
       ├─ SHA-256 hash  →  Redis cache lookup
       │    └─ Cache hit on a completed/processing job?  →  return cached job_id
       ├─ Save to  uploads/{job_id}.pdf
       ├─ Write    workspaces/{job_id}/metadata.json
       ├─ redis: SET cache:{file_hash}       = job_id        (TTL 24h)
       │         SET cache:{job_id}:upload_time              (TTL 24h)
       │         SET cache:{job_id}:file_size                (TTL 24h)
       └─ Enqueue  run_ocr_pipeline.apply_async(task_id=job_id)
            └─ Returns  {status: "queued", job_id: "…"}
```

### 4b. OCR Pipeline (Celery worker)

```
run_ocr_pipeline  (coordinator task)
  │
  ├─ Phase 0: mkdir workspaces/{job_id}/{images,ocr_json,output}
  │            redis SET cache:{job_id}:status = "processing"
  │
  ├─ Phase 1: pdf_converter.convert_pdf_in_chunks(pdf_path, images_dir)
  │            └─ ThreadPoolExecutor, 10-page chunks, 300 DPI
  │            └─ image_utils.preprocess_image() per page (deskew + pad)
  │            redis SET cache:{job_id}:total_pages   = N
  │                  SET cache:{job_id}:completed_pages = 0
  │
  └─ Phase 2+3: Celery Chord
       ├─ Header (parallel): ocr_page_task × N
       │    └─ google_vision: call Gemini 2.0 Flash → page JSON
       │    └─ redis INCR cache:{job_id}:completed_pages
       │    └─ save workspaces/{job_id}/ocr_json/page_NNN.json
       │
       └─ Callback (sequential): stitch_markdown_task
            ├─ load_and_repair_json() — 4-level JSON recovery fallback
            ├─ Two-Pass Verification — LLM fixes hyphenation at boundaries
            ├─ Forward-fill Vol/Issue metadata across pages
            ├─ Generate YAML frontmatter + citation block
            ├─ Write workspaces/{job_id}/output/full_extracted_content.md
            ├─ Write per-issue folders:
            │    workspaces/{job_id}/output/issues/Vol_NNN_Issue_NNN/pages/
            └─ redis SET cache:{job_id}:status  = "completed"
                     SET cache:{job_id}:end_time = <timestamp>
```

### 4c. Status / SSE

```
Browser
  └─ EventSource  GET /api/stream/{job_id}
       │
       └─ server._build_status_payload(job_id)  every 0.5 s
            ├─ Emits a JSON event only when (status, progress) changes
            ├─ Sends ": heartbeat" comment every 15 s (proxy keep-alive)
            └─ Closes stream on terminal state (completed | failed)

  GET /api/status/{job_id}  still available for one-shot checks
```

---

## 5. Job State Machine

```
                ┌──────────────────────────────────────────┐
                │  Redis key: cache:{job_id}:status        │
                └──────────────────────────────────────────┘

  (new upload)
       │
       ▼
   [ queued ]  ──── worker picks up ────►  [ processing ]
                                                  │
                          ┌───────────────────────┤
                          │                       │
                          ▼                       ▼
                     [ completed ]           [ failed ]
```

A **cached** upload short-circuits the pipeline and the browser receives
`{status: "cached", job_id: <existing_id>}` — the frontend treats this
identically to a fresh completed job.

---

## 6. API Contracts

All endpoints are under the `/api` prefix (Vite proxy) in development,
and behind `/api` in production.

| Method | Path | Request | Response |
|--------|------|---------|----------|
| `POST` | `/upload` | `multipart/form-data`: `file` (PDF), optional `title`, `volume`, `issue`, `date`, `skip_metadata` | `{status, job_id, task_id?, message}` |
| `GET` | `/status/{job_id}` | — | `{job_id, status, progress, message, markdown?, upload_time?, file_size?, processing_time?, complexity?}` |
| `GET` | `/stream/{job_id}` | — | `text/event-stream` — repeated `data: <JSON>` (same shape as `/status`) until terminal state |
| `GET` | `/uploads/{job_id}.pdf` | — | Static PDF binary (for DiffViewer) |
| `GET` | `/docs` | — | FastAPI Swagger UI |

---

## 7. Key Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Factory + Strategy** | `ocr_factory.py` + `ocr_interface.py` | Swap between Google Gemini and `RedTeamMockProvider` by setting `GOOGLE_API_KEY=MOCK_KEY` |
| **Celery Chord** | `celery_worker.py` | Fan-out N parallel OCR tasks; fan-in to one stitching callback |
| **SHA-256 Smart Cache** | `server.py::POST /upload` | Identical PDFs (by content hash) skip re-processing |
| **Per-Job Sandbox** | `workspaces/{job_id}/` | Concurrent jobs never touch each other's files |
| **Exponential Backoff** | `ocr_processor.py` | Retry on Gemini 429 rate-limit: 5 s, 10 s, 20 s, 40 s, 80 s (max 5 retries) |
| **Two-Pass Verification** | `stitcher.py::stitch_markdown()` | LLM re-checks page boundary text to fix split hyphenated words |
| **SSE Push** | `server.py::GET /stream` + `App.tsx` | Live progress without polling; browser `EventSource` + `useRef` map prevents reconnect churn on re-render |
| **TTL Cleanup** | `celery_worker.py::cleanup_old_workspaces` | Celery Beat runs at the top of every hour; deletes workspaces, PDFs, and Redis keys older than `WORKSPACE_TTL_HOURS` |

---

## 8. Configuration Reference

All configuration lives in `app/core/config.py`, loaded from `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Gemini API key. Set to `MOCK_KEY_DO_NOT_CHARGE` to activate mock mode |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + backend URL |
| `MODEL_NAME` | `gemini-2.0-flash` | Gemini model identifier |
| `WORKSPACES_DIR` | `workspaces` | Root directory for per-job sandboxes |
| `UPLOAD_DIR` | `uploads` | Where raw PDFs are stored |
| `WORKSPACE_TTL_HOURS` | `24` | Hours before a job workspace is deleted by cleanup task. `0` disables cleanup |
| `POPPLER_PATH` | `None` (Linux) | Path to Poppler binaries; only needed on Windows |
| `OVERRIDE_IMAGE_FOLDER` | `output_images` | Experiment override for image output dir |
| `OVERRIDE_OCR_JSON_FOLDER` | `ocr_jsonv2` | Experiment override for OCR JSON dir |

---

## 9. Frontend Architecture

```
App.tsx
 ├─ useJobPersistence()          localStorage, max 50 jobs, versioned schema
 ├─ activeStreams (useRef Map)   one EventSource per active job; persists across re-renders
 │
 ├─ UploadZone                  drag-drop → handleFileSelect → MetadataModal
 ├─ MetadataModal               optional citation fields → handleProcess → POST /upload
 │
 ├─ JobCard (active)            real-time status badge + progress bar
 ├─ JobCard[] (history)         completed jobs, click opens DiffViewer
 └─ DiffViewer                  react-pdf (left) vs Markdown (right)
                                10-dash delimiter parsing for page sync
```

**`lib/api.ts`** is the only file that talks to the backend:
- `uploadFile()` — `POST /upload`
- `pollJobStatus()` — `GET /status/{id}` (kept for one-off checks)
- `subscribeToJobStatus()` — `EventSource` wrapper, returns a `() => void` cleanup

**State persistence:** `useJobPersistence` stores jobs in `localStorage` under
`cleanocr_job_history_v1`. On load it re-attaches SSE streams to any jobs
still in `queued` or `processing` state (page-refresh recovery).

---

## 10. Testing & Verification

```bash
# Unit + integration tests
pytest tests/

# Specific suites
pytest tests/test_concurrency.py
pytest tests/test_two_pass_verification.py
pytest tests/test_stats.py

# End-to-end against a running stack
python scripts/verify_status_api.py
python scripts/test_upload.py --flush --dummy   # flushes Redis, uses mock PDF

# Mock mode (no API charges)
GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE docker-compose up
```

Mock mode is activated by setting `GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE`.
The factory in `ocr_factory.py` returns `RedTeamMockProvider`, which replays
fixtures from `tests/redteam_artifacts/` instead of calling Gemini.

Red-team stress tests use a separate compose file:
```bash
docker-compose -f docker-compose.redteam.yml up
```

---

## 11. Common Tasks and Where to Start

| Task | File(s) to read first |
|------|-----------------------|
| Change the OCR prompt | `app/core/prompts.py` |
| Add a new OCR provider (e.g. OpenAI Vision) | `app/services/ocr_interface.py` → implement → `app/services/ocr_factory.py` |
| Change how pages are stitched / formatted | `app/services/stitcher.py::stitch_markdown()` |
| Add a new API endpoint | `app/api/server.py` |
| Change worker concurrency or retry logic | `app/services/ocr_processor.py`, `app/core/config.py` |
| Change PDF conversion quality or chunking | `app/services/pdf_converter.py` |
| Add a new env var | `app/core/config.py` + `.env.example` |
| Add a new frontend page or component | `frontend/src/App.tsx`, `frontend/src/components/` |
| Change how job state is communicated | `app/api/server.py::_build_status_payload()` and `app/api/server.py::stream_job_status()` |
| Change cleanup TTL or schedule | `app/workers/celery_worker.py::cleanup_old_workspaces()`, `app/core/config.py::WORKSPACE_TTL_HOURS` |
| Understand the full data contract | `frontend/src/lib/api.ts` (TypeScript interfaces) |

---

## 12. Known Limitations (as of March 2026)

- **No authentication** — all endpoints are public; see `pie_in_the_sky.md §2`
- **No persistent job database** — job history is Redis (volatile) + browser localStorage; a Redis restart wipes server-side state
- **Hardcoded repair targets** — `REPAIR_TARGETS` in `stitcher.py` is specific to one historical dataset
- **Preprocessing always runs** — deskew adds overhead even on clean scans; no conditional bypass yet
- **No Celery Beat process in `docker-compose.yml`** — workspace cleanup requires manually starting `celery beat` or adding a fourth service
