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
│   ├── db/                     ★ Relational Database Engine (SQLAlchemy 2.0)
│   │   ├── database.py         Base, sessionmaker, SQLite WAL pragma, get_db
│   │   └── models.py           JobModel, JobMetadataModel, JobResultModel
│   ├── core/
│   │   ├── config.py           ★ Single source of truth for all config/env vars
│   │   ├── security.py         API Key verification dependency & Redis RateLimiter
│   │   ├── prompts.py          Gemini vision prompt template
│   │   └── image_utils.py      Deskew + padding preprocessing (stateless)
│   ├── services/
│   │   ├── ocr_interface.py    Abstract base class OCRProvider
│   │   ├── ocr_factory.py      Factory: returns Google or Mock provider
│   │   ├── google_vision.py    Gemini 3.1 Flash Lite / 3.8 Flash implementation
│   │   ├── pdf_converter.py    PDF → PNG via pdf2image + ThreadPoolExecutor
│   │   ├── ocr_processor.py    Per-page OCR with exponential-backoff retry
│   │   └── stitcher.py         Assembles page JSON → final Markdown
│   └── workers/
│       └── celery_worker.py    ★ ENTRY POINT — Celery app + all task definitions
│
├── frontend/
│   └── src/
│       ├── App.tsx             ★ ENTRY POINT — root component, SSE subscriptions
│       ├── components/         UI components (JobCard, DiffViewer, UploadZone, SettingsModal, NotificationToast …)
│       ├── hooks/
│       │   └── useJobPersistence.ts  localStorage job history (max 50 entries)
│       └── lib/
│           ├── api.ts          ★ HTTP + SSE client for the backend API (with auth interceptor)
│           └── utils.ts        Shared utilities
│
├── frontend-v2/                Experimental dark-theme document editor UI (React + Vite + Tailwind, :5174) — not yet the default
│
├── tests/                      Pytest unit + integration tests (209 tests, 100% green)
│   └── redteam_artifacts/      ★ RedTeam chaos campaigns, mock vision provider, fuzzer & stress suites
├── scripts/                    CLI verification + debug helpers
│
├── docker-compose.yml          ★ Defines redis / web / worker services
├── docker-compose.redteam.yml  ★ Dedicated RedTeam test harness (isolated mock environment)
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
       │    └─ google_vision: call Gemini 3.1 Flash Lite → page JSON
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

### 5b. Dual-Layer State Persistence & Recovery (Set B)

CleanOCR combines an ephemeral Redis fast-path with durable SQLAlchemy 2.0 relational persistence:

1. **Redis (Fast-Path):** Active progress counters (`cache:{job_id}:completed_pages`), task coordination chords, token-bucket rate limits, and real-time SSE broadcasts.
2. **Relational Database (Durable System of Record):** Persists jobs, citation metadata, and final Markdown extractions across container and Redis restarts.
   - **Default:** SQLite (`workspaces/cleanocr.db`) with zero manual setup.
   - **Production:** PostgreSQL configured via `DATABASE_URL=postgresql://user:pass@host:5432/cleanocr`.
   - **Concurrency Hardening:** For multi-worker environments, `database.py` enforces SQLite `PRAGMA journal_mode=WAL;` and `timeout=30.0` on connection.
   - **ORM Mapping Convention:** The child relationship on `JobModel` is named `citation_metadata` internally (because Declarative Base reserves `Base.metadata`) and serialized as `"metadata"` to preserve exact API backward compatibility.

```mermaid
erDiagram
    JOBS ||--o| JOB_METADATA : has
    JOBS ||--o| JOB_RESULTS : produces
    JOBS {
        string id PK "UUID4"
        string status "queued | processing | completed | failed"
        string file_hash "SHA-256"
        string original_filename
        int file_size_bytes
        int total_pages
        int processed_pages
        string model_name
        float upload_time
        float end_time
        float duration_seconds
        datetime created_at
        datetime updated_at
    }
    JOB_METADATA {
        int id PK
        string job_id FK
        string title
        string volume
        string issue
        string publication_date
    }
    JOB_RESULTS {
        int id PK
        string job_id FK
        text markdown_text
        int total_words
        float confidence_score
    }
```

```mermaid
sequenceDiagram
    autonumber
    actor Client as Web Frontend
    participant API as FastAPI Gateway
    participant Redis as Redis (Fast-Path)
    participant DB as SQLite / PostgreSQL (Durable)

    Note over Client, DB: Dual-Layer Status Fallback Flow
    Client->>API: GET /api/status/{job_id}
    API->>Redis: Check cache:{job_id}:status
    alt Redis Key Exists
        Redis-->>API: {status, progress, times}
        API-->>Client: 200 OK (Fast-Path Response)
    else Redis Evicted or Restarted (Cache Miss)
        API->>DB: SELECT * FROM jobs WHERE id = job_id
        DB-->>API: JobModel (with metadata and result)
        API-->>Client: 200 OK (DB Fallback Response)
    end
```

---

## 6. API Contracts & Security

All endpoints are under the `/api` prefix (Vite proxy) in development,
and behind `/api` in production.

### Endpoint Matrix

| Method | Path | Auth Required | Rate Limit | Request | Response / Errors |
|--------|------|---------------|------------|---------|-------------------|
| `POST` | `/upload` | Yes (if configured) | 3 / min | `multipart/form-data`: `file` (PDF), optional `title`, `volume`, `issue`, `date`, `skip_metadata` | `200`: `{status, job_id, task_id?, message}`<br>`400`, `401`, `413`, `429` |
| `POST` | `/jobs/{job_id}/cancel` | Yes (if configured) | 60 / min | Optional JSON: `{"reason": "string"}` | `200`: `{job_id, status: 'cancelled', message, cancelled_at}`<br>`400` (already terminal), `401`, `404`, `429` |
| `GET` | `/jobs` | Yes (if configured) | 60 / min | `?page=1&limit=20&status=&search=&sort_order=desc` | `200`: Paginated jobs list (`items`, `jobs`, `total`, `page`, `limit`, `total_pages`)<br>`401`, `422`, `429` |
| `GET` | `/jobs/{job_id}` | Yes (if configured) | 60 / min | — | `200`: Detailed record with metadata and extracted markdown text<br>`401`, `404`, `429` |
| `GET` | `/status/{job_id}` | Yes (if configured) | 60 / min | — | `200`: `{job_id, status, progress, message, markdown?, upload_time?, file_size?, processing_time?, complexity?}` (with automatic DB fallback)<br>`401`, `404`, `429` |
| `GET` | `/stream/{job_id}` | Yes (if configured) | 60 / min | `?api_key=` (query param fallback for SSE) | `text/event-stream` — repeated `data: <JSON>` until terminal state<br>`401`, `404`, `429` |
| `GET` | `/limits` | No | None | — | `200`: Ingestion caps (`max_upload_mb`, `max_pdf_pages`, etc.) |
| `GET` | `/system-status` | No | None | — | `200`: Health and active configuration diagnostics |
| `GET` | `/uploads/{job_id}.pdf` | No | None | — | Static PDF binary (for DiffViewer) |
| `GET` | `/docs` | No | None | — | FastAPI Swagger UI |

### Standard Error Response Envelope

All API errors return a uniform, unnested JSON schema:
```json
{
  "error": {
    "code": "UNAUTHORIZED | RATE_LIMIT_EXCEEDED | INVALID_FILE | FILE_TOO_LARGE | NOT_FOUND",
    "message": "Human readable description",
    "details": {
      "retry_after_seconds": 23
    }
  }
}
```

### Mobile-First UI/UX & Responsive Guidelines

In accordance with [`AGENTS.md`](AGENTS.md) design standards:
- **Viewport Resilience (320px to 4k):** Interfaces are built mobile-first. At small viewports (<640px), tabular displays (such as `JobHistory.tsx`) automatically transform into stacked touch cards with 44px minimum tap targets to avoid horizontal truncation.
- **DiffViewer Responsiveness:** On desktop (>=640px), the original PDF scan and extracted Markdown appear side-by-side with synchronized scrolling. On mobile screens (<640px), it flips to a toggleable single-column view.
- **Zero Native Browser Dialogs:** All application feedback (401 Auth Required, 429 Rate Limited, 500 Server Error) renders via animated, accessible inline banners or toast components with actionable retry countdowns or direct links to Settings modal. Raw `window.alert` / `window.confirm` calls are strictly prohibited.

---

## 7. Key Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Factory + Strategy** | `ocr_factory.py` + `ocr_interface.py` | Swap between Google Gemini and `RedTeamMockProvider` by setting `GOOGLE_API_KEY=MOCK_KEY` |
| **Safety Interlock State Machine** | `tests/redteam_artifacts/campaign_3_adversarial.py` | Aborts chaos testing immediately if `GOOGLE_API_KEY != MOCK_KEY_DO_NOT_CHARGE` or external egress detected |
| **CI/CD Build Matrix Dependency Gating** | `.github/workflows/ci.yml` | Strict TDD-enforced pipeline gating container packaging on Python matrix (3.11, 3.12) and Node 20.x `frontend-build` |
| **Relational Persistence** | `app/db/` (`database.py`, `models.py`) | SQLAlchemy 2.0 dual-engine (SQLite default, PostgreSQL ready) with cascade relationships for jobs, metadata, and extracted text |
| **Redis-to-DB State Fallback** | `app/api/server.py` | Graceful state recovery: queries Redis fast-path; falls back to relational DB if keys expire or Redis restarts |
| **SQLite WAL Concurrency** | `app/db/database.py` | Automatically sets `PRAGMA journal_mode=WAL;` and 30s timeout on connect to eliminate lock contention during concurrent worker writes |
| **Responsive History (Card/Table)** | `frontend/src/components/JobHistory.tsx` | Mobile-first design: renders stacked touch cards on mobile (<640px) and full sortable table on desktop (>=640px) with zero horizontal clipping |
| **API Key Authentication** | `app/core/security.py` | Header-based verification (`X-API-Key` or `Authorization: Bearer`) with SSE query param fallback (`?api_key=`) and open local dev fallback |
| **Sliding-Window Rate Limiting** | `app/core/security.py` | Redis-backed sliding window counter per client IP / API key hash (3 uploads/min, 60 status polls/min) |
| **Celery Chord** | `celery_worker.py` | Fan-out N parallel OCR tasks; fan-in to one stitching callback |
| **SHA-256 Smart Cache** | `server.py::POST /upload` | Identical PDFs (by content hash) skip re-processing |
| **Per-Job Sandbox** | `workspaces/{job_id}/` | Concurrent jobs never touch each other's files |
| **Exponential Backoff** | `ocr_processor.py` | Retry on Gemini 429 rate-limit: 5 s, 10 s, 20 s, 40 s, 80 s (max 5 retries) |
| **Two-Pass Verification** | `stitcher.py::stitch_markdown()` | LLM re-checks page boundary text to fix split hyphenated words |
| **SSE Push** | `server.py::GET /stream` + `App.tsx` | Live progress without polling; browser `EventSource` + `useRef` map prevents reconnect churn on re-render |
| **Job Cancellation & Revocation** | `app/api/server.py::POST /jobs/{id}/cancel` | First-class endpoint revoking Celery tasks (`revoke(terminate=True)`), transitioning Redis & DB state to `cancelled` |
| **Broadsheet Image Normalization** | `app/core/image_utils.py` | Caps broadside newspaper scans at 4096px / 36MP via Lanczos downscaling, preventing 75MB payload 503 deadlines |
| **Atomic JSON Writing** | `app/services/ocr_processor.py` | Validates non-null JSON before writing to `.json.tmp` and atomically replacing, eliminating 0-byte cache poisoning |
| **Honest Partial Failure** | `app/workers/celery_worker.py` | Celery chord flags incomplete extractions as `partial_failure` and lists dropped pages rather than falsely marking `completed` |
| **TTL Cleanup** | `celery_worker.py::cleanup_old_workspaces` | Celery Beat runs at the top of every hour; deletes workspaces, PDFs, and Redis keys older than `WORKSPACE_TTL_HOURS` |

---

## 8. Configuration Reference

All configuration lives in `app/core/config.py`, loaded from `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Gemini API key. Set to `MOCK_KEY_DO_NOT_CHARGE` to activate mock mode |
| `CLEANOCR_API_KEY` | *(unset / None)* | Secret API key for CleanOCR server access. When unset, dev mode allows open access |
| `DATABASE_URL` | `sqlite:///./workspaces/cleanocr.db` | SQLAlchemy connection string. Set to `postgresql://user:pass@host:5432/dbname` for production PostgreSQL |
| `RATE_LIMIT_UPLOADS_PER_MIN` | `3` | Maximum PDF upload requests permitted per 60-second window per client |
| `RATE_LIMIT_STATUS_PER_MIN` | `60` | Maximum status poll & SSE requests permitted per 60-second window per client |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window duration for rate limiting counters in Redis |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + backend URL |
| `OCR_TIER` | `standard` | `standard` uses `MODEL_NAME`; `pro` uses `PRO_MODEL_NAME`. |
| `MODEL_NAME` | `gemini-3.1-flash-lite` | Model used for standard tier ($0.25 in / $1.50 out). |
| `PRO_MODEL_NAME` | `gemini-3.8-flash` | Model used when `OCR_TIER=pro` ($0.75 in / $3.75 out, with `thinking_level=LOW`). |
| `LAYOUT_MODEL_NAME` | `gemini-3.1-flash-lite` | Dedicated lightweight model for pre-flight layout classification with `MEDIA_RESOLUTION_LOW`. |
| `FALLBACK_MODEL_NAME` | `gemini-3.5-flash-lite` | Auto-fallback on 404 (deprecated/missing model). Must differ from the active model to engage. |
| `WORKSPACES_DIR` | `workspaces` | Root directory for per-job sandboxes |
| `UPLOAD_DIR` | `uploads` | Where raw PDFs are stored |
| `WORKSPACE_TTL_HOURS` | `24` | Hours before a job workspace is deleted by cleanup task. `0` disables cleanup |
| `MAX_UPLOAD_MB` | `100` | Reject uploads larger than this (streamed size cap on `/upload`) |
| `MAX_PDF_PAGES` | `500` | Reject PDFs with more pages than this before any OCR is dispatched |
| `STREAM_BASE_BUDGET_SECONDS` | `20` | Base streaming time allowance for queue wait and Poppler PDF bursting |
| `STREAM_PAGE_BUDGET_SECONDS` | `3` | Per-page processing allowance calibrated for Gemini 3.1 Flash Lite |
| `STREAM_MIN_TIMEOUT_SECONDS` | `120` | Minimum client stream timeout safety floor |
| `MAX_IMAGE_DIMENSION` | `4096` | Downscale ceiling for oversized broadside scans (preserves aspect ratio) |
| `MAX_SAFE_PIXELS` | `36000000` | 36 Megapixel threshold above which broadside images are auto-downscaled |
| `GEMINI_DAILY_CALL_CAP` | `2000` | Hard cap on billed Gemini calls per UTC day, shared across workers via Redis (`app/core/cost_guard.py`). `0` disables |
| `GEMINI_RUN_CALL_CAP` | `5000` | Hard cap on billed Gemini calls per process; works without Redis (CLI batch mode). `0` disables |
| `LOCAL_GEMMA_REVISION` | *(unset = latest)* | Pin the HuggingFace revision (commit hash) of the local Gemma model; safetensors-only loading is enforced |
| `POPPLER_PATH` | `None` (Linux) | Path to Poppler binaries; only needed on Windows (falls back to system PATH if directory is invalid) |
| `OVERRIDE_IMAGE_FOLDER` | `output_images` | Experiment override for image output dir |
| `OVERRIDE_OCR_JSON_FOLDER` | `ocr_jsonv2` | Experiment override for OCR JSON dir |

---

## 9. Frontend Architecture

```
main.tsx
 └─ ErrorBoundary                 catches render-time exceptions; offers 1-click "Clear Cache & Reload"
     └─ App.tsx
         ├─ useJobPersistence()          localStorage, max 50 jobs, schema validation + malformed ID filtering
         ├─ activeStreams (useRef Map)   one EventSource per active job; persists across re-renders
         │
         ├─ UploadZone                  drag-drop → handleFileSelect → MetadataModal
         ├─ MetadataModal               optional citation fields → handleProcess → POST /upload
         │
         ├─ JobCard (active)            real-time status badge, progress bar, interactive cancellation
         ├─ JobHistory                  paginated DB history with status filters (completed, active, failed, partial_failure, cancelled)
         └─ DiffViewer                  react-pdf (left) vs Markdown (right)
                                        10-dash delimiter parsing for page sync
```

**`lib/api.ts`** is the only file that talks to the backend:
- `uploadFile()` — `POST /upload`
- `pollJobStatus()` — `GET /status/{id}` (kept for one-off checks)
- `subscribeToJobStatus()` — `EventSource` wrapper, returns a `() => void` cleanup
- `cancelJob()` — `POST /jobs/{id}/cancel` (revokes background workers)
- `fetchJobs()` / `fetchJobDetail()` — `GET /jobs`, `GET /jobs/{id}` (relational persistence)

**State persistence & resilience:**
1. `useJobPersistence`: stores jobs in `localStorage` under `cleanocr_job_history_v1`. On load, `loadHistory()` rigorously sanitizes stored records, filtering out malformed entries lacking valid string IDs to prevent `TypeError` crashes during render, and re-saving the sanitized list to disk.
2. `ErrorBoundary`: root-level wrapper in `main.tsx`. If any unexpected error occurs during component rendering or lifecycle execution, instead of unmounting to a blank white screen, it displays a themed recovery UI with technical details and a 1-click "Clear Cache & Reload" button.
3. Stream reconnect: On load, `App.tsx` re-attaches SSE streams to any jobs still in `queued` or `processing` state (page-refresh recovery).

---

## 10. Testing & Verification

> **Redis parity:** CI runs the suite against a live Redis service. Start `redis-server` locally before running `pytest` ahead of a push; without Redis, rate limiting and caching fail open and can mask failures. `tests/conftest.py` disables API rate limiting for every test by default (autouse `_disable_rate_limiting`); throttling tests patch `app.core.security.check_rate_limit` themselves.

```bash
# Unit + integration tests
pytest tests/  # 209 tests passing (100% green)

# Specific suites
pytest tests/test_ci_pipeline.py
pytest tests/test_concurrency.py
pytest tests/test_two_pass_verification.py
pytest tests/test_auth_and_rate_limit.py

# RedTeam Adversarial Chaos Suite (10/10 attack vectors verified)
python tests/redteam_artifacts/campaign_3_adversarial.py

# Frontend Build & Typecheck Integrity
cd frontend && npm run build

# End-to-end against a running stack
python scripts/verify_status_api.py
python scripts/test_upload.py --flush --dummy   # flushes Redis, uses mock PDF

# Mock mode (no API charges)
GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE docker-compose up
```

Mock mode is activated by setting `GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE`.
The factory in `ocr_factory.py` returns `RedTeamMockProvider`, which replays
fixtures from `tests/redteam_artifacts/` instead of calling Gemini.

Red-team stress tests use a separate compose file and campaign scripts:
```bash
docker-compose -f docker-compose.redteam.yml up
python tests/redteam_artifacts/campaign_3_adversarial.py
```
See [`tests/redteam_artifacts/README.md`](tests/redteam_artifacts/README.md) for complete details on chaos campaigns and safety interlocks.

---

## 11. CI/CD Pipeline Architecture

The CleanOCR automated test and build pipeline (`.github/workflows/ci.yml`) executes on every push and pull request against `main` and `master`:

```mermaid
flowchart TD
    push(["Git Push / PR"]) --> secretScan["Job: secret-scan<br>(gitleaks / credential check)"]
    push --> testMatrix["Job: test<br>(Python 3.11 & 3.12 Matrix + pytest)"]
    push --> frontendBuild["Job: frontend-build<br>(Node 20.x + npm ci + npm run build)"]

    secretScan --> buildJob["Job: build<br>(Docker Container Build Validation)"]
    testMatrix --> buildJob
    frontendBuild --> buildJob

    buildJob --> deployReady(["Artifacts Verified & Ready for Deployment"])
```

### Pipeline Jobs & Gating Matrix
1. **`secret-scan`**: Checks for hardcoded credentials, API keys, and sensitive tokens.
2. **`test`**: Runs the complete 209-test suite against Python 3.11 with Poppler and libmagic installed.
3. **`frontend-build`**: Validates React 18 / TypeScript / Vite compilation (`tsc -b && vite build`) to prevent production asset regressions.
4. **`build`**: Container packaging verification. **Hard-gated** via `needs: [test, frontend-build]` — docker images are never built or published if backend tests or frontend compilation fails.

---

## 12. Common Tasks and Where to Start

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

## 13. Known Limitations & Active Hardening Status

- **Adversarial Testing & Chaos Verification (Resolved in Set C):** 10/10 attack vectors verified and defended (Rate limiting burst throttling, constant-time key comparison, auth header validation, SQL injection parameterization, SQLite WAL concurrency under load, malformed/0-byte binary rejection, path traversal UUID neutralization, and Redis disconnect graceful degradation) in `tests/redteam_artifacts/campaign_3_adversarial.py`.
- **CI/CD Gating & Frontend Build Matrix (Resolved in Set C):** Automated via `.github/workflows/ci.yml` under strict TDD (`tests/test_ci_pipeline.py`), gating container packaging on Python matrix testing and Node 20.x TypeScript/Vite builds.
- **Authentication & Rate Limiting (Resolved in Set A):** Implemented in `app/core/security.py` via `CLEANOCR_API_KEY` header/bearer checks, SSE query params, and sliding-window Redis rate limits.
- **Relational database & Job History (Resolved in Set B):** Implemented in `app/db/` using SQLAlchemy 2.0, providing persistent job history, metadata, and extraction text across server/Redis restarts with `GET /jobs` and `GET /jobs/{job_id}` endpoints.
- **Hardcoded repair targets:** `REPAIR_TARGETS` in `stitcher.py` is now env-driven, but defaults to Mormon historical publications if unset.
- **Preprocessing always runs:** deskew adds overhead even on clean scans; conditional bypass based on layout detection is planned.
- **No Celery Beat process in `docker-compose.yml`:** workspace cleanup requires manually starting `celery beat` or adding a dedicated scheduler container.
