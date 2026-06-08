# CleanOCR — Session Handoff Context
**Date:** 2026-06-08  
**Branch:** `claude/handoff-context-review-RSsh8`  
**Status:** Changes committed & pushed. All 42 tests passing. Next session picks up from here.

---

## 1. What Was Done This Session

### Self-Hosted Tier Implemented
Full `OCR_TIER=local` pipeline built. No Google API key required.

| File | Change |
|------|--------|
| `app/services/surya_provider.py` | New `SuryaOCRProvider` — lazy Surya OCR, reading-order assembly, regex metadata, Gemma structuring with regex fallback |
| `app/services/gemma_provider.py` | New `GemmaTextProvider` — lazy transformers pipeline, module-level singleton |
| `app/services/ocr_factory.py` | Added `tier` param; routes `tier="local"` → `SuryaOCRProvider` |
| `app/core/config.py` | `OCR_TIER` and `LOCAL_GEMMA_MODEL` defined before the API key guard; guard is now conditional (`OCR_TIER != "local"`) |
| `app/services/stitcher.py` | `verify_boundary_text` checks `OCR_TIER`; uses `SuryaOCRProvider` (Gemma) for two-pass stitching on local tier |
| `requirements-local.txt` | `surya-ocr`, `transformers>=4.47`, `torch`, `accelerate` |
| `docker-compose.local.yml` | Compose override: GPU passthrough, shared HuggingFace model-cache volume |
| `Dockerfile.local` | CUDA 12.1 image with base + local requirements |

### Environment Errors Diagnosed and Fixed

Three errors surfaced during test-run investigation. All resolved.

| # | Symptom | Root Cause | Fix Applied |
|---|---------|-----------|-------------|
| 1 | `ModuleNotFoundError: No module named '_cffi_backend'` → cascade: `cryptography` → `google-auth` → `google-genai` all fail to import | System `_cffi_backend.so` is compiled for Python 3.12; container runs Python 3.11. `cffi` was not listed in `requirements.txt` so pip never installed it. | Added `cffi` to `requirements.txt` |
| 2 | `ModuleNotFoundError: cv2`, `fastapi`, etc. in bare container | These packages ARE in `requirements.txt` but were not installed in the test container session. CI runs `pip install -r requirements.txt` and works correctly. | No code change needed — pure environment setup; documented below |
| 3 | `AttributeError: module 'app.services.stitcher' has no attribute 'genai'` in `test_two_pass_verification.py` | Test patched `app.services.stitcher.genai.Client` — valid when `verify_boundary_text` called `genai.Client()` directly. After refactor to `get_provider()`, `stitcher.py` no longer imports `genai` at all. Stale mock path. | Updated test to patch `app.services.stitcher.get_provider` instead — cleaner boundary |

**Test result after fixes:** 42 passed, 0 failed.

---

## 2. Gemini Model Landscape (June 2026)
*(Carried forward from previous session — no changes needed)*

| Model | Input $/1M | Output $/1M | OCR Arena ELO | Deprecation |
|-------|-----------|-------------|--------------|-------------|
| ~~Gemini 2.0 Flash~~ | ~~$0.10~~ | ~~$0.40~~ | — | **DEAD Jun 1** |
| **Gemini 2.5 Flash Lite** | **$0.10** | **$0.40** | — | Oct 16, 2026 |
| Gemini 2.5 Flash | $0.30 | $2.50 | #8 (ELO 1595) | Oct 16, 2026 |
| Gemini 2.5 Pro | $1.25 | $10.00 | #7 (ELO 1636) | TBD |
| **Gemini 3.1 Flash Lite** | **$0.25** | **$1.50** | — | None |
| Gemini 3 Flash | $0.50 | $3.00 | **#1 (ELO 1759)** | None |
| Gemini 3.1 Pro | $2.00 | $12.00 | — | None |

**Current config defaults:**
```
MODEL_NAME=gemini-2.5-flash-lite          # standard tier
PRO_MODEL_NAME=gemini-3.1-flash-lite      # pro tier
FALLBACK_MODEL_NAME=gemini-2.5-flash      # auto-fallback on 404
LOCAL_GEMMA_MODEL=google/gemma-4-E4B-it   # local tier
```

---

## 3. Four-Tier Model Architecture
*(Decided last session — implementation status updated)*

| Tier | Backend | Status |
|------|---------|--------|
| **Free** | Gemini 2.5 Flash Lite (API) | ✅ Done |
| **Pro** | Gemini 3.1 Flash Lite (API) | ✅ Done (env var `OCR_TIER=pro`) |
| **Private Cloud** | Gemma 4 27B on CleanOCR GPU infra | ❌ Phase 2 / post-revenue |
| **Self-Hosted** | Surya + Gemma 4 E4B (user's machine) | ✅ Done (`OCR_TIER=local`) |

---

## 4. Repo State at Handoff

```
Branch:  claude/handoff-context-review-RSsh8
Commit:  (see git log — two commits this session)
Clean:   yes
Tests:   42 passed, 0 failed
```

### What Works Right Now
- Full Gemini API pipeline: standard (2.5 Flash Lite) and pro (3.1 Flash Lite) tiers
- Automatic model fallback in `google_vision.py` on 404 deprecation errors
- Self-hosted tier: `OCR_TIER=local` routes to `SuryaOCRProvider` — no API key required
- GPU-enabled Docker override: `docker-compose.local.yml` + `Dockerfile.local`
- All 42 tests green, including the two-pass verification test with corrected mock

### What Does Not Exist Yet
- Frontend tier-selection UI (user can't choose tier from the web UI)
- User authentication / tier enforcement (still backlog)
- Private Cloud tier (Gemma 4 27B on CleanOCR infra) — deferred to Phase 2
- End-to-end test with a real Surya + Gemma installation (local tier code is complete but untested against actual models — only installable in a GPU environment)

---

## 5. Resolved Decisions (2026-06-08)

Previously open questions — all answered, ready to implement.

1. **Deprecation runway on 2.5 Flash Lite** — **DECISION: Keep `gemini-2.5-flash-lite` as default.** It is intentionally the cheapest, fastest, and most accurate model for OCR. Do not migrate. The existing `FALLBACK_MODEL_NAME` handles the Oct 16 deadline automatically if needed.

2. **Frontend tier selection** — **DECISION: Add tier selector to the upload UI.** Backend is complete; surface it in MetadataModal so users can choose Free / Pro / Local. Env var admin override stays. Target: Phase 2.

3. **Gemma model download UX** — **DECISION: Add `python -m app.local_setup` pre-download script.** Silent multi-GB downloads on first request are unacceptable. Script should download the model, verify it, and exit cleanly. Target: Phase 0.

4. **Two-pass stitching fallback on local tier** — **DECISION: Warning + graceful degradation.** When Gemma is not loaded, log a clear warning, surface `"two_pass_available": false` in the `/status` response, and continue with concatenation. Do not hard-fail. Target: Phase 0.

5. **`starlette` / `httpx` deprecation warning** — **DECISION: Fix it.** Add `httpx2` to `requirements.txt`. Target: Phase 0.

---

## 6. Known Limitations of Self-Hosted Tier (for user docs)

- Accuracy: ~83% (Surya olmOCR benchmark) vs ~95%+ for Gemini API tiers
- Metadata extraction (volume/issue/date): regex heuristics only — may miss fields
- Two-pass stitching: uses Gemma 4 E4B for text — quality unverified vs Gemini
- Concurrency: `MAX_WORKERS` should be set to 1-2 for CPU-only setups; `docker-compose.local.yml` already sets `--concurrency=1`
- First request latency: models lazy-load on first use; subsequent requests are fast
- No rate limits or quotas — hardware is the ceiling

---

## 7. Environment Setup Notes (for bare containers / fresh clones)

```bash
# 1. Install all Python deps including cffi (now explicit in requirements.txt)
pip install -r requirements.txt

# 2. For local/self-hosted tier only:
pip install -r requirements-local.txt

# 3. Set environment
export GOOGLE_API_KEY=your-key   # not needed when OCR_TIER=local
export OCR_TIER=standard         # standard | pro | local

# 4. Run tests
pytest tests/ -v
```

**Why `cffi` is now explicit:** The Ubuntu system package `python3-cryptography` ships `_cffi_backend.cpython-312-x86_64-linux-gnu.so` (Python 3.12 only). When running Python 3.11, `cffi` must be pip-installed. `google-auth` depends on `cryptography` which depends on `cffi`; without it, importing `google-genai` panics with a pyo3 rust exception.

---

## 8. Development Roadmap

### Phase 0 — Quick Wins (next session)
All items are small, touch different files, no dependencies between them.

- [ ] Add `httpx2` to `requirements.txt`; verify all 42 tests still pass
- [ ] Add `python -m app.local_setup` — pre-download Gemma model, print progress, exit cleanly
- [ ] Emit `"two_pass_available": false` in `/status` response when Gemma is not loaded; log warning
- [ ] Update this file to reflect completed items

**HITL gate:** None required — all changes are additive and easily reverted.

### Phase 1 — Test Coverage (1–2 sessions)
Fill the three highest-risk gaps before any new feature work. Regressions here corrupt output silently.

- [ ] `tests/test_stitcher_json_repair.py` — 4 repair strategies, hallucination detection, Roman numeral normalization, YAML frontmatter shape  *(spawn isolated sub-agent — stitcher.py is 454 lines)*
- [ ] `tests/test_ocr_retry.py` — 429 backoff sequence, max-retries exhaustion, failed-page logging
- [ ] `tests/test_upload_api.py` — cache hit path, invalid MIME rejection, metadata edge cases
- [ ] `tests/test_google_vision.py` — model fallback chain (404 → retry → all fail)
- [ ] Add `httpx2` to `requirements.txt` if not done in Phase 0
- [ ] Move `REPAIR_TARGETS` from `stitcher.py` hardcode to `config.py`

**HITL gate:** Human reviews assertions in `test_stitcher_json_repair.py` before merge — these define the correctness contract for the most complex logic in the codebase.

**Multi-agent note:** `test_stitcher_json_repair.py` and `test_ocr_retry.py` touch different modules and can be written by parallel sub-agents in the same session.

### Phase 2 — Feature Hardening (2–3 sessions)
Prerequisites for any public-facing use. Auth before Postgres; Postgres before tier UI.

- [ ] **Auth** — JWT or API key on `/upload` and `/status`; job ownership enforcement  *(HITL: human approves auth model before implementation)*
- [ ] **Postgres** — persistent job history (replaces volatile Redis + localStorage as source of truth)  *(HITL: human approves schema before migration)*
- [ ] **Frontend tier selector** — Free / Pro / Local picker in MetadataModal; passes `tier` field to `POST /upload`
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

### Session Strategy
- One phase = one session maximum. Split if scope grows.
- HANDOFF_CONTEXT.md must be updated and committed before any session ends.
- When a source file is >200 lines, spawn an isolated sub-agent rather than loading it into the main context.
- HITL gates listed above are non-negotiable human review points before merge.
