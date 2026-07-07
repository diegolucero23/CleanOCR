# CleanOCR Security Audit — 2026-07-05

Read-only audit. No code changes were made. Scope: dependency tree, Gemini API key handling, network exposure, file-ingestion paths, dangerous primitives, and git history secrets.

---

## Summary of findings

| # | Finding | File/Location | Risk Level | Why it matters |
|---|---------|---------------|------------|----------------|
| 1 | **Live Gemini API key committed to git history** (`AIzaSyCy…CxYSw`, hardcoded in `batch_ocr.py`, `repair_pages.py`, `transcribe_targets.py`) | Commits `07548ef`, `dc79b51`, `bd036d4`, `c72b6ba` (Jan 2026); removed in `2d2467a` ("removed exposed keys") | **Critical** | The key is still fully retrievable via `git show` on any clone. Anyone with repo access (or anyone at all, if the repo was ever public) can bill this Google account. Removal in a later commit does not help — the key must be **revoked/rotated** and ideally the history rewritten (BFG/`git filter-repo`) + GitHub cache purged. |
| 2 | **All Python dependencies unpinned, no lockfile** — `fastapi`, `uvicorn`, `celery`, `redis`, `google-genai`, `pillow`, `pdf2image`, `opencv-python-headless`, `numpy`, `python-magic`, `python-json-logger`, `pyyaml`, `pytest`, `kombu`, `cffi`, `httpx2`, `python-multipart` all float to latest | `requirements.txt` (17 pkgs, zero version specifiers); installed unpinned in `Dockerfile:18` and CI (`.github/workflows/ci.yml:52`) | **High** | Every build (Docker, CI, user install) pulls whatever PyPI serves that day. A single malicious or broken release of any of these compromises the pipeline that holds the API key. No reproducibility, no audit trail of what actually ran. |
| 3 | **`httpx2`: brand-new, low-provenance package** — first PyPI release 2026-05-11, added to requirements 2026-06-09, unpinned; claims to be the httpx successor under `github.com/pydantic/httpx2` | `requirements.txt:21`; added in commit `2c492da` | **High** | A weeks-old package pulled unpinned into a container that holds `GOOGLE_API_KEY` is a textbook supply-chain risk (typosquat/impersonation pattern — metadata author fields are free-form). Provenance should be verified against the official encode/pydantic announcement before trusting it; note the app code never imports `httpx` directly (it was added only to silence a Starlette deprecation warning). |
| 4 | **Unauthenticated network-facing API with no upload size/page limits or rate limiting** — this is *not* a pure local batch tool: FastAPI + uvicorn on `0.0.0.0:8000`, port published by compose | `app/api/server.py` (POST `/upload`, GET `/status/{id}`, GET `/stream/{id}`, GET `/system-status`, static `/uploads`); `docker-compose.yml:16-17`; `start.sh` launches it for end users | **High** | Anyone who can reach port 8000 can upload unlimited-size, unlimited-page PDFs. Each page becomes a billed Gemini call (`ocr_page_task`), so an attacker or accident converts network access directly into Google API spend and disk/CPU exhaustion (300 DPI PNG per page). No auth, no CORS middleware, no request-size cap anywhere (`shutil.copyfileobj` streams to disk unbounded, `server.py:98-99`). |
| 5 | **Unauthenticated Redis published to the host** (`6379:6379`), doubling as the Celery broker & result backend | `docker-compose.yml:7-8`; broker wiring in `app/workers/celery_worker.py:34-38` | **High** | Anything on the host/LAN that reaches 6379 can read/poison job state (`cache:*` keys, dedupe cache, DLQ) and inject Celery task messages with attacker-controlled arguments (e.g., arbitrary `pdf_path`/output paths for `run_ocr_pipeline`, forced API-billing work). Redis needs no password by default. The redteam compose (`docker-compose.redteam.yml`) publishes a second instance on 6380. |
| 6 | **API key runtime handling (current code)** — read from `.env`/env in exactly one place, passed in-memory to the SDK; **not logged or persisted** | Read: `app/core/config.py:18` (`load_dotenv` + `os.getenv`). Passed: `ocr_factory.get_provider()` → `GoogleVisionProvider.__init__` → `genai.Client(api_key=…)` (`app/services/google_vision.py:29`); also `ocr_processor.py:48`, `stitcher.py:178`, `scripts/repair_pages.py:42`. Injected via `docker-compose.yml` `env_file: .env` + explicit `GOOGLE_API_KEY=${GOOGLE_API_KEY}`; CI uses dummy `"test-key-for-ci"` (`ci.yml:31`), `tests/conftest.py:14` likewise | **Low** (current handling is sound) | `.env` is in both `.gitignore` and `.dockerignore`, the key never appears in log statements, and mock/dummy values are used in CI and tests. Residual notes: `.:/app` bind mounts expose `.env` inside both containers (fine locally, bad if containers are ever shared), and `HUGGING_FACE_HUB_TOKEN` is passed through `docker-compose.local.yml`. |
| 7 | **Untrusted PDF parsing by native code (Poppler) at 300 DPI, plus Pillow/OpenCV image handling — all unpinned** | `app/services/pdf_converter.py` (`pdf2image.convert_from_path` / `pdfinfo_from_path` → `pdftoppm`/`pdfinfo` subprocesses); `app/core/image_utils.py` (OpenCV/numpy); `PIL.Image.open` in `ocr_processor.py:51`; system `poppler-utils` from `Dockerfile:6-9` (whatever Debian slim ships) | **Medium** | Poppler has a long CVE history for crafted PDFs; it processes attacker-supplied bytes from the public upload endpoint. Rendering at 300 DPI also makes decompression-bomb pages cheap DoS. Arguments to the subprocess are server-generated paths (UUID filenames), so no injection — the risk is in the parser itself and the unpinned versions. |
| 8 | **File-type validation degrades silently to extension checking** if `python-magic` fails to import | `app/api/server.py:9-13`, `56-69` (`validate_file_type` falls back to `.endswith(".pdf")`) | **Medium** | On a host missing `libmagic` the only gate on uploads is the filename, so arbitrary bytes reach Poppler. Even with magic present, MIME sniffing checks the header only — a polyglot valid-PDF remains possible (acceptable, but the silent fallback isn't). |
| 9 | **Local tier downloads and executes ML models from HuggingFace Hub, model id fully env-controlled** | `app/services/gemma_provider.py:49-54` (`transformers.pipeline(model=LOCAL_GEMMA_MODEL, …)`), `surya_provider.py` (Surya weights), `LOCAL_GEMMA_MODEL` override in `config.py:15`, `HUGGING_FACE_HUB_TOKEN` passthrough in `docker-compose.local.yml` | **Medium** | Whoever controls the env var (or the compose file) picks an arbitrary Hub repo; `transformers`/`torch`/`surya-ocr` are unpinned (`requirements-local.txt` uses only `>=` floors). Malicious model repos can carry pickled weights / custom code. Pin versions and the exact model revision (`revision=` + safetensors-only). |
| 10 | **Uploaded PDFs are served back publicly via static mount, and job results are readable without auth** | `app/api/server.py:43` (`app.mount("/uploads", StaticFiles…)`); `/status/{job_id}` returns full extracted markdown (`server.py:200-202`) | **Medium** | Anyone who learns/guesses a `job_id` (UUIDv4 — unguessable in practice, but they appear in logs, browser history, and the SSE URL) can fetch someone else's source document and full OCR output. Fine for single-user localhost; a data-exposure hole the moment this is hosted anywhere. |
| 11 | **Content derived from input files and API responses flows into LLM prompts and repaired-JSON parsing** (no eval/exec/pickle, though) | `stitcher.py:163-198` (`verify_boundary_text` embeds OCR'd page text in a Gemini prompt), `surya_provider.py:205-211` (raw OCR text into Gemma prompt), `stitcher.py:43-114` (regex "repair" of raw model output written verbatim to output files) | **Medium** | A scanned page containing adversarial text is a prompt-injection vector: it can steer the boundary-fix/structuring calls and thus corrupt output (and burn extra tokens). Model responses are written to disk unsanitized and returned to the frontend as `markdown` — currently rendered without `dangerouslySetInnerHTML` (no XSS found in `frontend/src`), so impact is output-integrity, not code execution. |
| 12 | **Dangerous-primitive scan: clean.** No `eval`/`exec`/`pickle`/`os.system` anywhere; only `subprocess` uses are fixed-argv | `scripts/test_upload.py:16` (`docker-compose exec redis redis-cli FLUSHALL`, static args); Poppler subprocesses via `pdf2image` (see #7); Celery uses JSON serialization (default), not pickle | **Low** | Nothing interpolates input-file- or API-derived data into shell commands or deserializes pickles. The only subprocess exposure to untrusted data is Poppler parsing PDF *bytes* (covered in #7). |
| 13 | **`.env.redteam` committed (tracked despite `.gitignore`'s `.env.*` rule) — mock values only** | `.env.redteam` (`GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE`, `STRIPE_KEY=mock_stripe`, `SMTP_PASSWORD=mock_smtp`); added in commit `7ed34b5` | **Low** | Values are intentional mocks, so no exposure today — but the file being tracked proves the `.env.*` ignore rule doesn't protect already-tracked files, normalizing a pattern where a real `.env.something` could be committed the same way. Rename to `.env.redteam.example` or explicitly un-ignore. |
| 14 | **Runtime artifacts committed to the repo**: `logs.txt` (UTF-16 uvicorn access log with internal IPs/job ids), `failed_pages.log` (stack-trace snippets), 45 MB scan ZIP | Repo root; staged in commit `f73405c` ("stage live test artifacts") | **Low** | Minor information leakage (internal topology, historical job ids, error internals) and repo bloat. No secrets found in them. `.gitignore` has `*.log` but these were force-added/pre-dated it. Note: no code in the repo ever extracts the ZIP (`zipfile`/`extractall` absent) — it's inert data. |
| 15 | **Git-history secret sweep beyond the Gemini key: nothing else found** | Searched all 37 commits for `sk-…`, `ghp_…`, `xox[bp]-…`, private-key blocks, hardcoded passwords | **Low** (informational) | Only hits were the Gemini key (#1), CI's dummy `test-key-for-ci`, and the mock values in `.env.redteam`. |

---

## Detail by audit question

### 1. Dependency tree

**`requirements.txt` (backend, production)** — *all 17 entries unpinned*:
`fastapi`, `uvicorn`, `python-multipart`, `celery`, `redis`, `google-genai`, `pillow`, `pdf2image`, `python-dotenv`, `opencv-python-headless`, `numpy`, `python-magic`, `python-magic-bin` (win32 marker), `python-json-logger`, `pyyaml`, `pytest`, `kombu`, `cffi`, `httpx2`.

**`requirements-local.txt` (self-hosted tier)** — floor-pins only, no upper bounds, no lock:
`surya-ocr` (unpinned), `transformers>=4.47.0`, `accelerate>=0.34.0`, `torch>=2.3.0`.

**Python lockfile:** none (`pip freeze`/`pip-tools`/`uv`/poetry absent). No `pyproject.toml`.

**Frontend (`frontend/package.json`)** — caret ranges (`axios ^1.13.4`, `react ^19.2.0`, `react-pdf ^10.3.0`, `vite ^7.2.4`, etc.), **but** `package-lock.json` is present (lockfileVersion 3, 338 packages) → effectively pinned for `npm ci`.

**System layer:** `Dockerfile` uses floating tags `python:3.11-slim` and unversioned `apt-get install poppler-utils libmagic1`; CI mirrors this on `ubuntu-latest`.

### 2. Gemini API key surface

| Where | What happens |
|---|---|
| `app/core/config.py:8,18` | `load_dotenv(BASE_DIR/.env, override=True)` then `os.getenv("GOOGLE_API_KEY")`; hard-exits if missing (non-local tier) |
| `app/services/ocr_factory.py:37` → `google_vision.py:29` | Passed in-memory to `genai.Client(api_key=…)` |
| `ocr_processor.py:48`, `stitcher.py:175-178`, `scripts/repair_pages.py:38-42` | Read from `config.GOOGLE_API_KEY`; `startswith("MOCK")` gates mock mode |
| `docker-compose.yml:21-22,36-38` | Injected into web + worker via `env_file: .env` and `GOOGLE_API_KEY=${GOOGLE_API_KEY}` |
| `.github/workflows/ci.yml:31`, `tests/conftest.py:14` | Dummy literal `test-key-for-ci` (no real CI secret used) |
| Logging | **Never logged** in current code (verified by grep across the repo) |
| Git history | **Real key hardcoded** in commits `07548ef` → `c72b6ba` (see finding #1) — Critical |
| `.gitignore` / `.dockerignore` | `.env` and `.env.*` excluded from both git and the Docker build context (good); but `.:/app` bind mounts re-expose `.env` inside running containers |

### 3. Network exposure

Not a pure local script. Components: **FastAPI/uvicorn on 0.0.0.0:8000** (published), **Redis on host 6379** (published, no auth), **Celery worker** (consumes from that Redis), **Vite dev frontend on 5173**, SSE streaming endpoint, static `/uploads` file server. A legacy interactive CLI batch mode also exists (`app/main.py`, `Dockerfile` CMD). Redteam compose adds 8001/6380 variants with read-only mounts and resource caps. No webhook receivers.

### 4. File-ingestion paths

1. **HTTP upload** → `uploads/{uuid4}.pdf` (unbounded `copyfileobj`) → `python-magic` MIME check (extension-only fallback) → SHA-256 dedupe via Redis → Celery `run_ocr_pipeline`.
2. **Local batch** → `PDF_SOURCE` from `.env` → same converter.
3. **Parsing chain:** `pdf2image` (**Poppler** `pdfinfo`/`pdftoppm`, 300 DPI, threaded chunks) → **Pillow** → **OpenCV/numpy** deskew + gutter padding (`image_utils.py`) → PNG per page → `PIL.Image.open` → Gemini (`google-genai`), or Surya (torch) + Gemma (transformers) on the local tier.
4. **No archive extraction anywhere** — the committed 45 MB ZIP is inert data. ImageMagick and PyMuPDF are not used.

### 5. eval/exec/pickle/subprocess

None of `eval`, `exec`, `pickle`, `os.system`, `shell=True` in application code. `subprocess.run` appears once, in a dev script with a fixed argv (`scripts/test_upload.py:16`). Poppler subprocesses (via `pdf2image`) receive server-generated paths but parse untrusted PDF bytes. Celery uses JSON task serialization. Input-file-derived data does reach **LLM prompts** and lax JSON "repair" parsing (finding #11), but never a code-execution sink.

### 6. Git history secrets

- **Gemini key `AIzaSyCy…CxYSw`** in 4 commits (finding #1) — assume compromised; **revoke immediately**, then rewrite history if the repo will ever be shared.
- No other credential material found across all 37 commits (patterns searched: OpenAI/GitHub/Slack tokens, private keys, hardcoded passwords). `.env.redteam` (mock) and CI dummy key are the only other "secret-shaped" strings.

---

## Remediation status (updated 2026-07-05)

1. ✅ **Exposed Gemini key** — owner confirms the key was revoked and replaced months ago.
2. ✅ **Dependency pinning** — `requirements.txt` now uses exact pins resolved on Python 3.11; full transitive lock in `constraints.txt` (used by both Dockerfiles and CI); `requirements-local.txt` pinned exactly (transformers kept on the 4.x series the code targets).
   ✅ **`httpx2` resolved** — investigation showed it is *likely legitimate* (Starlette's own deprecation warning recommends it; hosted under the pydantic GitHub org), but FastAPI's TestClient still hard-imports classic `httpx` (which google-genai also requires), so `httpx2` added nothing. Replaced with pinned `httpx==0.28.1`; revisit once the FastAPI/Starlette migration completes.
3. ✅ **Redis exposure** — published port removed from `docker-compose.yml` (services reach it via the compose network); redteam compose ports bound to `127.0.0.1`.
4. ✅ **Upload limits + binding** — streaming size cap (`MAX_UPLOAD_MB`, default 100) and page-count cap (`MAX_PDF_PAGES`, default 500) enforced in `/upload` before any OCR work is dispatched; corrupt/unreadable PDFs rejected. API host port now binds to `127.0.0.1`. Verified live against a running server (413/400 responses, rejected files cleaned up, no task dispatched).
5. ✅ **History purge** — performed July 2026. The repository history was rewritten to remove the old (revoked) key; the commits cited in finding #1 no longer exist and all SHAs from that era changed. Full-history gitleaks scan is clean with no commit allowlist. All pre-rewrite clones are stale and must be re-cloned (they still carry the old key in their object stores); see SECURITY.md §5. Residual: ask GitHub Support to purge cached views of the old commits if that hasn't been done, and remember the old key stays compromised-by-assumption forever — revocation is what neutralized it.

6. ✅ **Fail-closed file-type validation (#8)** — fixed 2026-07-07. `validate_file_type` no longer falls back to extension matching when libmagic is unavailable; `/upload` now rejects with 503 (a server-side condition, not a client error) and removes the temp file. Covered by `tests/test_upload_limits.py::test_upload_fails_closed_without_libmagic`.
7. ✅ **Unredacted exception reflected by `/status`** — fixed 2026-07-07 (found in the follow-up OWASP pass). The FAILURE branch of `_build_status_payload` returned `str(task_result.info)` — the raw exception Celery stored in its result backend — to the client, the one client-facing path that skipped `redact()`. Now redacted; covered by `tests/test_credential_hardening.py::test_status_endpoint_redacts_celery_failure_message`.

Still open (lower priority, from the findings table): pinning the HuggingFace model revision (#9), auth in front of `/uploads` and `/status` for any hosted deployment (#10 — deferred by owner decision 2026-07-07: deployment is single-user loopback-only; auth + CSRF + strict CORS become prerequisites if the bind ever moves off `127.0.0.1`), renaming `.env.redteam` to an `.example` (#13), and removing committed runtime artifacts (#14).
