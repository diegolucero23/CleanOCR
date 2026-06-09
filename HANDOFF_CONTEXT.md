# CleanOCR — Session Handoff Context
**Date:** 2026-06-09  
**Branch:** `main`  
**Status:** Phase 1 complete. 101 tests passing (up from 42). Gaps 2, 3, 5 fixed. Next session: Phase 2 feature hardening.

---

## 1. What Was Done This Session

### Phase 0 Quick Wins — All Complete

| File | Change |
|------|--------|
| `requirements.txt` | `httpx2` added (resolves `StarletteDeprecationWarning`) |
| `app/local_setup.py` | New script: `python -m app.local_setup` pre-downloads Gemma model with clear progress output |
| `app/services/gemma_provider.py` | `is_gemma_loaded()` module-level helper added |
| `app/api/server.py` | `GET /system-status` endpoint added — returns `tier`, `two_pass_available`, `gemma_model`; logs WARNING if `OCR_TIER=local` but Gemma not loaded |
| `app/api/server.py` + `app/workers/celery_worker.py` | Fixed `pythonjsonlogger` import: `jsonlogger` → `json as jsonlogger` (deprecation warning eliminated) |
| `.env` | `MODEL_NAME` corrected from dead `gemini-2.0-flash` to `gemini-2.5-flash-lite`; `FALLBACK_MODEL_NAME=gemini-2.5-flash` made explicit |
| `README.md` | Developer install section updated: frontend Vite dev server (`cd frontend && npm run dev`) now documented as a separate step from Docker backend |

**Tests:** 42 passed, 0 failed, 0 warnings (run inside `cleanocr-web-1` container, Python 3.11).

> **Note:** Local Python environment is 3.14.0 on Windows/Cygwin which has a fatal `TP_NUM_C_BUFS too small` crash on some imports. Always run tests inside Docker: `docker exec cleanocr-web-1 python -m pytest tests/ -q`

### Bug Discovered and Fixed Mid-Session
`.env` had `MODEL_NAME=gemini-2.0-flash` — deprecated June 1, 2026. The fallback logic in `google_vision.py` would have caught 404s page-by-page, but this caused one wasted API call per page before falling back. Fixed before the live test run.

---

## 2. Live End-to-End Test (2026-06-09)

### Test File
**Filename:** `BetterUp_AI 1.0 Pilots and Passengers (1).pdf`  
**Original Job ID:** 7c7bd0a8-8d28-4176-8542-a60b54fb4884  
**Location:** User's `Downloads/` folder  
**Size:** 47.2 MB  
**Pages:** 33  
**Content type:** Corporate research slide deck (PowerPoint-style). Full-bleed color backgrounds, infographic stats, callout quotes, brand photography, minimal text density per page. Text was *embedded* in the PDF (not scanned) — the file did not require OCR but was processed through the full pipeline anyway (see Gap 1 below).  
**Processing time:** 18m 48s  
**Reported complexity:** **10.0** (maximum) — driven by large image sizes at 300 DPI (pages ranged from 1.7 MB to 25 MB as PNGs after rasterization)

### Test Results
- **23 of 33 pages extracted successfully** — text quality high, heading hierarchy preserved, stats and footnotes captured accurately
- **9 pages failed** (011, 015, 022, 024, 025, 027, 028, 029, 030) — all hit `Max Retries Exceeded` (5× 429 rate-limit errors in `process_single_image`)
- **1 page (003)** — JSON written but malformed (unterminated string from a truncated API response; stitcher skipped it silently)
- **1 page (031)** — SSL EOF error on first attempt; recovered on retry, JSON present

### Output Quality Notes
- Hallucinated image markdown on page 9: `![Jan-Emmanuel De Neve, PhD](https://...placeholder.png)` — Gemini invented a placeholder URL for a flattened photo. No embedded image existed.
- Pages 003 (table of contents), 011 (definition slide), 015, 022, 024, 025, 027–031 (stats, callout quotes, graphs) all had real text content that was lost.
- Volume/Issue metadata defaulted to `1/1` — expected for non-periodical content.

---

## 3. Gaps Identified This Session

These are confirmed production gaps discovered during the live test. All are candidates for Phase 1 or Phase 2 work.

### Gap 1 — Embedded-Text PDFs Run Full OCR Pipeline Unnecessarily
PDFs exported from PowerPoint, Word, or slide editors have perfectly good embedded/selectable text. CleanOCR always rasterizes to 300 DPI images and sends them to Gemini Vision regardless, wasting 18+ minutes and significant API cost on a file that could be extracted in seconds.

**Fix:** Prompt user, ask if they want to run full OCR or extract text directly. If they choose direct extraction, add a pre-flight check using `pypdf` or `pdfminer.six` before the PDF burst step. If >80% of pages have extractable text, bypass OCR entirely and write per-page JSON directly. Surface `"text_native": true` in the job status payload.  
**Target:** Phase 1 or Phase 2.

### Gap 2 — Silent OCR Failure in `ocr_page_task`
`process_single_image` (in `app/services/ocr_processor.py`) returns failure *strings* like `"❌ Failed (Max Retries): page_011.png"` instead of raising exceptions. As a result:
- The Celery-level retry (`max_retries=3` in `ocr_page_task`) **never fires** for OCR failures
- `completed_pages` is incremented even for failed pages (progress bar lies)
- The stitcher silently skips missing JSON files — no warning surfaced to the user

**Fix:** In `ocr_page_task`, check the return value and raise if it indicates failure, OR refactor `process_single_image` to raise on failure.  
**Target:** Phase 1 — high priority, this is silent data loss.

### Gap 3 — `failed_pages.log` Has No Job ID or Timestamp
The log accumulates entries from all jobs with format `filename|reason`. There is no way to tell which job a failure belongs to, when it happened, or how many retries it took.

**Fix:** Change format to `job_id|ISO-timestamp|filename|reason`. Update any scripts in `scripts/` that parse this log.  
**Target:** Phase 1.

### Gap 4 — 300 DPI Rasterization Should Be Tier-Gated
300 DPI produces PNG images of 2–25 MB per page for graphic-heavy content. This drives up processing time, memory pressure, and API costs. It is appropriate for Historians and Researchers processing dense 19th-century newspaper microfilm, but wasteful for general/hobbyist use.

**Decision (to be ratified):** Gate DPI by tier:
- `standard` (Free): 150 DPI — fast, lower API payload, sufficient for most modern documents
- `pro`: 300 DPI — full resolution for archival/research-grade accuracy
- `local`: configurable via env var `OCR_DPI`, default 150

**File to change:** `app/services/pdf_converter.py` — `convert_from_path(..., dpi=300, ...)` → read from `config.OCR_DPI`.  
**Target:** Phase 2 (requires tier enforcement to be meaningful).

### Gap 5 — Gemini Hallucinates Image Markdown for Flattened Photos
When a page contains a photo that is flattened into the PDF (no embedded image object), Gemini occasionally generates a fabricated `![alt](url)` markdown tag with a placeholder or invented URL. This corrupts the output.

**Fix:** Post-process `markdown_content` in the stitcher (or in `ocr_processor.py`) to strip any `![...]()` tags where the URL is not a real accessible resource, or simply strip all image markdown tags entirely (CleanOCR is a text extraction tool — images in output are never useful).  
**Target:** Phase 1 — low effort, high output quality impact.

### Gap 6 — Rate Limits Exhaust on Large Concurrent Jobs
With 12 Celery workers all hitting the Gemini API simultaneously, rate limits are depleted by the time later-processed pages arrive (those from PDF chunks that finished converting after the earlier chunks). The 9 failed pages in the test run were all from chunks that finished converting last.

**Related to Gap 2** — fixing the silent failure so Celery retries engage (with longer backoff) would absorb most of this. Additionally, consider reducing default `MAX_WORKERS` in `ocr_processor.py` from 4 to 2 for standard tier.  
**Target:** Phase 1 (fix via Gap 2 + backoff tuning).

---

## 4. Gemini Model Landscape (June 2026)

| Model | Input $/1M | Output $/1M | OCR Arena ELO | Deprecation |
|-------|-----------|-------------|--------------|-------------|
| ~~Gemini 2.0 Flash~~ | ~~$0.10~~ | ~~$0.40~~ | — | **DEAD Jun 1** |
| **Gemini 2.5 Flash Lite** | **$0.10** | **$0.40** | — | Oct 16, 2026 |
| Gemini 2.5 Flash | $0.30 | $2.50 | #8 (ELO 1595) | Oct 16, 2026 |
| Gemini 2.5 Pro | $1.25 | $10.00 | #7 (ELO 1636) | TBD |
| **Gemini 3.1 Flash Lite** | **$0.25** | **$1.50** | — | None |
| Gemini 3 Flash | $0.50 | $3.00 | **#1 (ELO 1759)** | None |
| Gemini 3.1 Pro | $2.00 | $12.00 | — | None |

**Current `.env` / config defaults:**
```
MODEL_NAME=gemini-2.5-flash-lite          # standard tier (corrected this session)
PRO_MODEL_NAME=gemini-3.1-flash-lite      # pro tier
FALLBACK_MODEL_NAME=gemini-2.5-flash      # auto-fallback on 404 (now explicit in .env)
LOCAL_GEMMA_MODEL=google/gemma-4-E4B-it   # local tier
```

---

## 5. Four-Tier Model Architecture

| Tier | Backend | DPI | Status |
|------|---------|-----|--------|
| **Free** | Gemini 2.5 Flash Lite (API) | 150 (proposed, see Gap 4) | ✅ Backend done |
| **Pro** | Gemini 3.1 Flash Lite (API) | 300 (proposed, see Gap 4) | ✅ Backend done (`OCR_TIER=pro`) |
| **Private Cloud** | Gemma 4 27B on CleanOCR GPU infra | 300 | ❌ Phase 2 / post-revenue |
| **Self-Hosted** | Surya + Gemma 4 E4B (user's machine) | configurable | ✅ Done (`OCR_TIER=local`) |

---

## 6. Repo State at Handoff

```
Branch:  main
Commits: (Phase 1 complete — see git log)
Clean:   yes
Tests:   101 passed, 0 failed, 1 warning (StarletteDeprecationWarning — cosmetic, not a bug)
```

### What Works Right Now
- Full Gemini API pipeline: standard (2.5 Flash Lite) and pro (3.1 Flash Lite) tiers
- Automatic model fallback in `google_vision.py` on 404 deprecation errors
- Self-hosted tier: `OCR_TIER=local` routes to `SuryaOCRProvider` — no API key required
- GPU-enabled Docker override: `docker-compose.local.yml` + `Dockerfile.local`
- `GET /system-status` endpoint: tier, `two_pass_available`, `gemma_model`
- `python -m app.local_setup` pre-download script for Gemma
- All 42 tests green, zero deprecation warnings

### What Does Not Exist Yet
- Frontend tier-selection UI
- User authentication / tier enforcement
- Private Cloud tier (Gemma 4 27B)
- End-to-end test with real Surya + Gemma (GPU required)
- DPI tier-gating (Gap 4) — Phase 2
- Embedded-text PDF fast-path (Gap 1) — Phase 2

---

## 7. Environment Setup Notes

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. For local/self-hosted tier only:
pip install -r requirements-local.txt

# 3. Set environment (.env)
GOOGLE_API_KEY=your-key          # not needed when OCR_TIER=local
OCR_TIER=standard                # standard | pro | local
MODEL_NAME=gemini-2.5-flash-lite
FALLBACK_MODEL_NAME=gemini-2.5-flash

# 4. Start backend
docker compose up -d

# 5. Start frontend (separate step — NOT part of Docker)
cd frontend && npm run dev       # http://localhost:5173

# 6. Run tests (must be inside container — local Python 3.14 crashes)
docker exec cleanocr-web-1 python -m pytest tests/ -q
```

---

## 8. Development Roadmap

### Phase 0 — Quick Wins ✅ COMPLETE
- [x] `httpx2` in `requirements.txt`
- [x] `python -m app.local_setup` pre-download script
- [x] `GET /system-status` endpoint + `is_gemma_loaded()` helper
- [x] Fix `pythonjsonlogger` deprecation warning
- [x] Correct `MODEL_NAME` in `.env` (was dead `gemini-2.0-flash`)
- [x] README: document frontend Vite dev server as separate step

### Phase 1 — Test Coverage + Critical Bug Fixes ✅ COMPLETE
- [x] **[GAP 2] Fix silent OCR failure** — `OCRPageFailure` exception class added; `process_single_image` raises instead of returning failure strings; `completed_pages` only incremented on confirmed success
- [x] **[GAP 3] Add job_id + timestamp to `failed_pages.log`** — new format: `job_id|ISO-timestamp|filename|reason`; `scripts/repair_pages.py` updated to parse new format (backward compatible with legacy 2-field lines)
- [x] **[GAP 5] Strip hallucinated image markdown** — `re.sub(r'!\[[^\]]*\]\([^)]*\)', '', page_text)` applied in both stitch passes (full doc + per-issue files)
- [x] Move `REPAIR_TARGETS` from `stitcher.py` hardcode to `config.py`; `scripts/audit_collection.py` updated to import from config
- [x] `tests/test_ocr_retry.py` — 12 tests: raise on failure, completed_pages accuracy, log format
- [x] `tests/test_stitcher_json_repair.py` — 28 tests: all 4 repair strategies, hallucination detection, Roman numerals, YAML frontmatter, image stripping *(HITL: assertions need human review before merge)*
- [x] `tests/test_upload_api.py` — 9 tests: cache hit, MIME rejection, Redis stats, metadata passthrough
- [x] `tests/test_google_vision.py` — 11 tests: fallback chain, pro tier model selection

**Tests:** 101 passed, 0 failed (run inside `cleanocr-web-1` container)

### Phase 2 — Feature Hardening (2–3 sessions)
Prerequisites for any public-facing use. Auth before Postgres; Postgres before tier UI.

- [ ] **[GAP 1] Embedded-text PDF fast-path** — pre-flight `pypdf` check; skip OCR for text-native PDFs
- [ ] **[GAP 4] DPI tier-gating** — 150 DPI for standard/free, 300 DPI for pro; `OCR_DPI` config var
- [ ] **Auth** — JWT or API key on `/upload` and `/status`; job ownership enforcement *(HITL: human approves auth model)*
- [ ] **Postgres** — persistent job history *(HITL: human approves schema)*
- [ ] **Frontend tier selector** — Free / Pro / Local picker in MetadataModal
- [ ] **Metadata validation** — Pydantic schema for `title`, `volume`, `issue`, `date`; structured 422 errors

### Phase 3 — Observability (1–2 sessions)
- [ ] Prometheus exporters for FastAPI + Celery
- [ ] Grafana dashboard: Queue Depth, OCR Error Rate, Latency P95
- [ ] Alerting: worker crash, Gemini error rate > 5%, DLQ depth > 10
- [ ] Rate limiting on `/upload` via Redis token bucket
- [ ] Circuit breaker on Gemini API calls

### Phase 4 — Scale & Enterprise (ongoing)
- [ ] Private Cloud tier (Gemma 4 27B on CleanOCR GPU infra) — blocked on revenue
- [ ] Cloud storage (S3/GCS for `uploads/` + `workspaces/`)
- [ ] IaC (Terraform)
- [ ] Load testing (50+ concurrent jobs)
- [ ] Confidence scoring + HITL review queue in frontend
- [ ] Full-text search across extracted documents

---

## 9. Session Strategy
- One phase = one session maximum. Split if scope grows.
- HANDOFF_CONTEXT.md must be updated and committed before any session ends.
- When a source file is >200 lines, spawn an isolated sub-agent rather than loading it into the main context.
- HITL gates listed above are non-negotiable human review points before merge.
- Always run tests inside Docker (`docker exec cleanocr-web-1`) — local Python 3.14 on Windows/Cygwin has a fatal crash on some imports.
