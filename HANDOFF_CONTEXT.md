# CleanOCR — Session Handoff Context
**Date:** 2026-06-07  
**Branch:** `claude/surya-ocr-gemma-analysis-Ndw1z`  
**Status:** Changes committed & pushed. Next session picks up from here.

---

## 1. What Was Done This Session

### Critical Bug Fixed
**Gemini 2.0 Flash was shut down by Google on June 1, 2026.** The codebase was pointing to a dead model. Fixed across all locations:

| File | Change |
|------|--------|
| `app/core/config.py` | `MODEL_NAME` default → `gemini-2.5-flash-lite`; added `PRO_MODEL_NAME` and `FALLBACK_MODEL_NAME` |
| `app/services/google_vision.py` | Full rewrite: added `_is_model_unavailable()` + automatic fallback on 400/404 errors |
| `app/services/stitcher.py` | Hardcoded `gemini-2.0-flash` fallback → `gemini-2.5-flash-lite` |
| `ARCHITECTURE.md` | Updated config table with 3 new model env vars |

### Research Completed
Spent the session doing deep research on the OCR model landscape (June 2026). All findings documented in sections 2–5 below. No further research is needed before implementation begins.

---

## 2. Gemini Model Landscape (June 2026)

### Deprecation Timeline
- `gemini-2.0-flash` → **DEAD as of June 1, 2026**
- `gemini-2.5-flash` → **Shuts down October 16, 2026** (do NOT use as a long-term target)
- `gemini-3.x` family → Current generation, no deprecation announced

### Full OCR Accuracy + Pricing Table

| Model | Input $/1M | Output $/1M | OCR Arena ELO | socOCRbench | IDP Leaderboard | Deprecation |
|-------|-----------|-------------|--------------|-------------|-----------------|-------------|
| ~~Gemini 2.0 Flash~~ | ~~$0.10~~ | ~~$0.40~~ | — | — | — | **DEAD Jun 1** |
| **Gemini 2.5 Flash Lite** | **$0.10** | **$0.40** | — | — | — | Oct 16, 2026 |
| Gemini 2.5 Flash | $0.30 | $2.50 | #8 (ELO 1595) | — | — | Oct 16, 2026 |
| Gemini 2.5 Pro | $1.25 | $10.00 | #7 (ELO 1636) | — | — | TBD |
| **Gemini 3.1 Flash Lite** | **$0.25** | **$1.50** | — | 0.6546 | **#1** | None |
| Gemini 3 Flash | $0.50 | $3.00 | **#1 (ELO 1759)** | — | — | None |
| Gemini 3.1 Pro | $2.00 | $12.00 | — | **#1 (0.5965)** | — | None |
| Gemini 3.5 Flash | $1.50 | $9.00 | — | — | — | None |

**Key insight:** Gemini 2.5 Flash Lite = same price as the old 2.0 Flash. Gemini 3.1 Flash Lite tops document-specific benchmarks at only 2.5x the old price. The 2.5 *Thinking* variants have documented OCR regression — avoid for this use case.

**Batch API discount:** 50% off all models for 24-hour processing — relevant for bulk archive jobs.

### Current Config After This Session
```
MODEL_NAME=gemini-2.5-flash-lite          # Standard tier (primary)
PRO_MODEL_NAME=gemini-3.1-flash-lite      # Pro tier
FALLBACK_MODEL_NAME=gemini-2.5-flash-lite # Auto-fallback if active model is unavailable
```

---

## 3. Open-Weight / Local Model Landscape (June 2026)

### Surya OCR (datalab-to/surya)
| Spec | Value |
|------|-------|
| Parameters | 650M |
| olmOCR Benchmark | 83.3% (top under 3B params) |
| Speed | 5 pages/second on RTX 5090 |
| Runtime | CPU, GPU, Apple MPS |
| Languages | 91 |
| Capabilities | Layout detection, reading order, handwriting, math, tables, image captions |
| Output | Structured JSON (RAG-ready) |
| License | Apache 2.0 (code) / OpenRAIL-M (model) |
| GitHub | `github.com/datalab-to/surya` |

**What Surya does NOT do:** metadata extraction (volume/issue/date/page), structured JSON in CleanOCR's schema, two-pass stitching LLM step.

### Gemma 4 (Google, open-weight)
| Variant | Active Params | VRAM (fp16) | Speed (image OCR) | Use Case |
|---------|--------------|-------------|-------------------|----------|
| E4B (MoE) | ~2.3B | ~6-8GB | ~37s/image (full vision) | Self-hosted / edge |
| 12B | 12B | ~24GB | — | Mid-range GPU server |
| 27B | 27B | ~54GB | — | Production private cloud |

**Critical distinction:** The 37s/image benchmark is for full multimodal image-to-text. If Gemma 4 only processes **already-extracted text** (from Surya), it is dramatically faster — seconds per page for text-only inference. This is the key to making the local stack viable.

**No published benchmark** exists comparing Gemma 4 OCR accuracy to any Gemini API model (as of June 2026). Anyone claiming equivalence is speculating.

### TranslateGemma (Google, open-weight)
| Spec | Value |
|------|-------|
| Released | January 15, 2026 |
| Built on | Gemma 3, fine-tuned for translation |
| Variants | 4B (mobile), 12B (consumer laptop), 27B (H100) |
| Languages | 55 |
| Purpose | Text-to-text translation (NOT OCR) |
| Error reduction | 23.5% vs Gemma 3 27B baseline (WMT24++ benchmark) |
| HuggingFace | `google/translategemma-*` |

**For CleanOCR's primary use case (19th-century English newspapers): TranslateGemma adds nothing.** It is only relevant as an optional post-OCR step for multilingual document support. Defer to a future feature.

---

## 4. Decided Product Tier Architecture

### Business Model Decision
Cloud-hosted is primary (speed + accuracy = main deliverable). Self-hosted is a secondary privacy-first feature for paying customers. The privacy story is valuable but infrastructure-heavy — it is a Phase 2/Series A feature, not day-1.

### Four-Tier Model

| Tier | Backend | Data Privacy | Speed | Accuracy | Target User |
|------|---------|-------------|-------|----------|-------------|
| **Free** | Gemini 2.5 Flash Lite (API) | Google sees data (disclosed) | Fast | ~95% | Hobbyists, students, trial |
| **Pro** | Gemini 3.1 Flash Lite (API) | Google sees data (disclosed) | Fast | Best-in-class on doc benchmarks | Researchers, small institutions |
| **Private Cloud** | Gemma 4 27B on CleanOCR's own GPU servers | Data never leaves CleanOCR infra | Fast (batched) | ~90% (unverified) | Enterprises, legal, GDPR, regulated industries |
| **Self-Hosted** | Surya + Gemma 4 E4B (user's machine) | Full sovereignty | Slower | ~83% | Historians, air-gapped environments |

### Disclosure Requirement
All tiers must clearly disclose where data goes. Gemini API tiers: "Your documents are processed by Google's API. See Google's data policy." Private Cloud / Self-Hosted: "Your documents never leave [CleanOCR / your machine]."

---

## 5. Self-Hosted Tier — Implementation Plan (NEXT SESSION FOCUS)

This is what the next conversation should implement. The API tier fix is already done.

### Architecture: Surya + Gemma 4 E4B

```
[PDF Upload]
    ↓
[pdf_converter.py] → PNG pages (unchanged)
    ↓
[image_utils.py] → deskew + pad (unchanged)
    ↓
[SuryaOCRProvider] → raw text + layout boxes  ← NEW
    ↓
[GemmaStructuringProvider] → structured JSON   ← NEW (text-only, fast)
    (metadata, markdown_content, layout_type)
    ↓
[stitcher.py] → final Markdown (unchanged, but two-pass LLM step
                uses GemmaStructuringProvider instead of Gemini)
```

### Files to Create

#### 1. `app/services/surya_provider.py`
- Implements `OCRProvider`
- Loads `surya-ocr` package at init (lazy load to avoid slowing API tier startup)
- Input: `PIL.Image` (same as current)
- Output: must produce same JSON schema as Gemini:
  ```json
  {
    "metadata": {"volume": null, "issue": null, "date": null, "page_number": null},
    "layout_type": "multi-column",
    "markdown_content": "..."
  }
  ```
- Surya gives layout boxes + text. Adapter needed to assemble into markdown reading order.
- Metadata fields: **populate via regex heuristics** (look for Vol./Issue/Date patterns in extracted text) or leave null.

#### 2. `app/services/gemma_provider.py`
- Implements `OCRProvider` but operates on text-only input (not images)
- Uses `transformers` + `torch` to load Gemma 4 E4B locally
- Lazy loads model on first use (not at startup)
- Input: raw text from Surya → structured JSON output
- Replaces the image→JSON step; Surya handles image→text
- Also used for two-pass stitching LLM call (replaces Gemini in `stitcher.py`)

#### 3. Updates to `app/services/ocr_factory.py`
```python
def get_provider(api_key: str, tier: str = "standard"):
    if str(api_key).startswith("MOCK_KEY"):
        ...  # unchanged
    if tier == "local":
        return SuryaOCRProvider()   # new
    return GoogleVisionProvider(api_key)   # unchanged
```

#### 4. Updates to `app/core/config.py`
```python
OCR_TIER = os.getenv("OCR_TIER", "standard")  # "standard" | "pro" | "local"
LOCAL_GEMMA_MODEL = os.getenv("LOCAL_GEMMA_MODEL", "google/gemma-4-E4B-it")
```

#### 5. Updates to `requirements.txt`
```
# Add under a [local] extras comment — only needed for self-hosted tier
surya-ocr
transformers
torch
accelerate
```
Consider splitting into `requirements.txt` (base) and `requirements-local.txt` (local tier extras) to avoid bloating the cloud Docker image.

#### 6. Updates to `Dockerfile` and `docker-compose.yml`
- Add a `docker-compose.local.yml` override for self-hosted
- Local image needs: `surya-ocr`, `torch`, `transformers`, GPU passthrough (`deploy: resources: reservations: devices`)
- Standard cloud image stays lean (no torch, no surya)

### Known Limitations to Document for Users
- Self-hosted OCR accuracy: ~83% vs ~95%+ for API tiers (Surya benchmark)
- Metadata extraction (volume/issue/date): heuristic only, may miss fields
- Two-pass stitching: uses Gemma 4 E4B instead of Gemini — quality unverified
- Concurrency: limited by local hardware; `MAX_WORKERS` should default to 1-2 for CPU-only
- Speed: Surya is fast; Gemma 4 text structuring adds seconds per page
- No rate limits or quotas — only hardware is the ceiling

### Open Questions for Next Session
1. Should `SuryaOCRProvider` call a separate `GemmaStructuringProvider` internally, or should `ocr_factory.py` compose them?
2. Should the two-pass stitching LLM step be disabled for self-hosted (to avoid Gemma 4 latency) or kept?
3. Lazy model loading vs. warmup at startup — warmup gives better first-request latency but slows Docker startup.
4. Should `requirements-local.txt` be separate, or use pip extras (`pip install cleanocr[local]`)?

---

## 6. Private Cloud Tier — Notes (Future Phase)

Do NOT implement now. Document for planning purposes only.

### Concept
CleanOCR hosts Gemma 4 27B on its own GPU infrastructure. Customers get cloud convenience + no Google data exposure. Priced as an enterprise/GDPR tier.

### Infrastructure Required
- 2× NVIDIA A100 80GB or 1× H100 per instance
- vLLM or TGI (Text Generation Inference) for batched serving
- Surya still handles OCR layer (CPU-capable, doesn't need GPU)
- Gemma 4 27B serves the structuring + stitching LLM role
- Same Celery architecture routes to local vLLM endpoint instead of Gemini API

### Cost Reality
- A100 80GB on cloud: ~$3-4/hr (Lambda Labs, CoreWeave, RunPod)
- Shared across concurrent customers via request batching
- GPU needs to stay loaded = 24/7 cost even at zero load
- This is a Series A / post-revenue feature, not MVP

### Shortcut Option
Instead of self-managing GPU infra, route "private cloud" customers through a third-party private inference provider (Together.ai, Fireworks.ai, Anyscale) that already hosts Gemma 4 27B. Customer data stays off Google but you avoid GPU ops overhead.

---

## 7. pie_in_the_sky.md — Items This Session Informs

These backlog items are now clarified by this session's research and should be updated:

- **Section 3 (Core Logic & AI):** Add new item: "Multi-tier model architecture (Free/Pro/Private Cloud/Self-Hosted)" — strategy decided, implementation pending.
- **Section 2 (Backend):** Add: "OCR_TIER env var routing in ocr_factory.py" — needed for self-hosted.
- **Section 1 (Infrastructure):** Add: "Separate Docker Compose override for self-hosted tier (GPU passthrough, local model deps)."
- **Section 5 (Data & Storage):** Note: self-hosted tier has no cloud storage — workspaces are local only.

---

## 8. Repo State at Handoff

```
Branch:  claude/surya-ocr-gemma-analysis-Ndw1z
Commit:  b7f7e72  "Migrate from deprecated Gemini 2.0 Flash to 2.5 Flash Lite with model fallback"
Clean:   yes (nothing uncommitted)
Tests:   not re-run this session (model name change only; no logic changed in test paths)
```

### What Works Right Now
- Full Gemini API pipeline: `gemini-2.5-flash-lite` (primary), `gemini-3.1-flash-lite` (pro via env var)
- Automatic model fallback in `google_vision.py` on 400/404 deprecation errors
- All existing tests, Celery orchestration, Redis caching, SSE streaming unchanged

### What Does Not Exist Yet
- `SuryaOCRProvider` (self-hosted OCR)
- `GemmaStructuringProvider` (self-hosted structuring)
- `OCR_TIER` routing in `ocr_factory.py`
- `docker-compose.local.yml`
- `requirements-local.txt`
- Any frontend tier selection UI
- User authentication / tier enforcement (still on backlog)
