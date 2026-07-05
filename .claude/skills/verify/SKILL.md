---
name: verify
description: Build, launch, and drive the CleanOCR FastAPI app to verify changes end-to-end without docker.
---

# Verifying CleanOCR without docker-compose

## Prereqs
- Python 3.11 venv: `pip install -r requirements.txt -c constraints.txt`
- System packages: `poppler-utils` (pdfinfo/pdftoppm), `libmagic1`, `redis-server`
- `redis-server --daemonize yes --port 6379 --bind 127.0.0.1`

## Launch the API (no worker needed for /upload verification)
```bash
GOOGLE_API_KEY=dummy REDIS_URL=redis://localhost:6379/0 \
UPLOAD_DIR=/tmp/v/uploads WORKSPACES_DIR=/tmp/v/workspaces \
MAX_UPLOAD_MB=1 MAX_PDF_PAGES=2 \
uvicorn app.api.server:app --host 127.0.0.1 --port 8123
```
Run from the repo root (imports resolve via cwd). `config.py` hard-exits at
import if `GOOGLE_API_KEY` is unset (non-local tier) — always pass a dummy.

## Generate test PDFs (Pillow, no extra deps)
- Valid: `Image.new("RGB",(200,300),"white").save("one.pdf")`
- Multi-page: `img.save("three.pdf", save_all=True, append_images=[...])`
- Oversize: save a `os.urandom` noise image ~2000x2000, quality=98 (≈6 MB;
  small noise images compress below 1 MB — check size)
- Fake: text bytes named `.pdf` (magic rejects); `%PDF-1.4` + garbage
  (magic accepts, pdfinfo rejects)
- Decompression bomb: hand-write a minimal PDF whose page declares a huge
  `/MediaBox [0 0 14000 14000]` (see tests/test_ingestion_hardening.py
  `_write_pdf`). Upload accepts it; the worker must refuse it at PHASE 1
  ("would exceed MAX_PAGE_PIXELS") and mark the job failed.

## Drive
`curl -F "file=@x.pdf;type=application/pdf" http://127.0.0.1:8123/upload`
Expected: 200 queued / 200 cached (dup) / 413 size / 413 pages / 400 type /
400 corrupt. Check `redis-cli llen default` for the queued Celery task
(queue name is `default`, not `celery`) and that rejected uploads leave no
file in UPLOAD_DIR.

## Drive the worker (converter/OCR phases, no real API key needed)
```bash
GOOGLE_API_KEY=dummy REDIS_URL=redis://localhost:6379/0 \
UPLOAD_DIR=/tmp/v/uploads WORKSPACES_DIR=/tmp/v/workspaces \
timeout 75 celery -A app.workers.celery_worker worker --loglevel=warning --concurrency=2
```
PDF burst (PHASE 1) runs for real; OCR calls fail on the dummy key but the
chord still completes and stitches, so a valid PDF reaches
`cache:{job_id}:status = completed` with images in the workspace. Check
per-job outcomes with `redis-cli get cache:<job_id>:status`.

## Gotchas
- `docker compose config` validates port bindings without a daemon, but
  needs a `.env` file to exist (touch/rm one) and `GOOGLE_API_KEY` set.
- Tests need `REDIS_URL=redis://localhost:6379/0` exported (default points
  at the compose hostname `redis`).
