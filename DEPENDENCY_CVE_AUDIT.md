# CleanOCR Dependency CVE Audit — 2026-07-05

Scope: every pinned dependency in `requirements.txt` / `constraints.txt` /
`requirements-local.txt`, plus the system packages the Dockerfile installs
(`poppler-utils`, `libmagic1`) and the frontend `package-lock.json`, checked
against known CVEs. This is a **report only — no versions were changed**.

Method: PyPI advisory API (per pinned version), OSV/GHSA/NVD lookups for the
named CVE classes, `npm audit` on the frontend lockfile, and a source read of
how CleanOCR actually calls each library (`app/services/pdf_converter.py`,
`app/core/image_utils.py`, `app/api/server.py`, `app/services/ocr_processor.py`,
`app/services/gemma_provider.py`).

---

## Bottom line

At the **pinned versions**, the Python application tier (`requirements.txt` +
`constraints.txt`) is **clean** — Pillow, OpenCV, pdf2image, numpy,
python-multipart, starlette, fastapi, requests, httpx, urllib3, redis, celery,
pyyaml, cryptography, google-genai all resolve *above* the fix line for every
CVE in their history. The pins in the recent security commit did their job.

The real exposure is in the layers that `requirements.txt` does **not** pin:

1. **System Poppler** (apt, unversioned) — reachable pre-auth from `/upload`, parses attacker PDF bytes. **Top exploitability.**
2. **`transformers` 4.57.6** (local tier) — three RCE CVEs, one (`CVE-2026-4372`) on the exact `pipeline()`/`from_pretrained` path CleanOCR uses. Gated behind `OCR_TIER=local` + control of the model id.
3. **Frontend npm tree** — `axios` SSRF/auth-bypass is the only runtime-reachable one; the rest are dev/build-time (vite, rollup, esbuild toolchain).

---

## Ranked findings (by real exploitability given CleanOCR's usage)

### 1 — Poppler (system `poppler-utils`, unpinned via apt) — **High / reachable pre-auth**

- **How CleanOCR uses it:** `pdf2image.convert_from_path(dpi=300, …)` and
  `pdfinfo_from_path(…)` shell out to `pdftoppm` / `pdfinfo`
  (`app/services/pdf_converter.py:11,46`; `app/api/server.py:74`). These parse
  the **raw uploaded PDF bytes** — the attacker fully controls the input, and
  the path is reachable **before any OCR/auth** from the public `POST /upload`
  endpoint (page-count probe runs on every upload).
- **CVEs affecting the version the Dockerfile ships** (`python:3.11-slim` is now
  Debian **trixie**, which ships poppler `25.03.0-5`):
  | CVE | Affected range | Effect | Fixed in |
  |---|---|---|---|
  | **CVE-2025-52886** | poppler < 25.06.0 | `std::atomic_int` 32-bit refcount overflow → **use-after-free** (potential RCE) in `Annot/Array/Dict/Stream` | poppler 25.06.0 / Debian `25.03.0-5+deb13u2` |
  | **CVE-2025-43718** | poppler 24.06.1 – < 25.04.0 | stack consumption / SIGSEGV via deeply-nested PDF metadata (`Catalog::getMetadata`) → **DoS** | poppler 25.04.0 / trixie point release |
- **Does CleanOCR trigger it?** **Yes.** Both are triggered by parsing a crafted
  PDF, which is exactly what the upload path does. The subprocess *arguments*
  are server-generated UUID paths (no argument injection — confirmed no
  `shell=True`, no user data in argv), so the risk is entirely in the parser
  eating hostile bytes. The `MAX_UPLOAD_MB`/`MAX_PDF_PAGES` caps blunt volumetric
  DoS but do **not** stop a small malformed PDF from hitting the UAF/recursion.
- **Minimum safe version to pin:** pin the apt package to **poppler ≥ 25.06.0**
  (Debian `25.03.0-5+deb13u2` or later — install `poppler-utils` with an
  explicit `=` version and rebuild on security updates; or move to a base image
  that carries the patched point release). `requirements.txt` cannot fix this —
  it is a `Dockerfile` apt pin.

### 2 — `transformers==4.57.6` (local tier, `requirements-local.txt`) — **High, but gated behind `OCR_TIER=local`**

- **How CleanOCR uses it:** `gemma_provider.py:49` calls
  `transformers.pipeline("text-generation", model=self.model_name, …)` where
  `model_name` defaults to `LOCAL_GEMMA_MODEL` and is **env-overridable**
  (`config.py:15`). Only loaded when `OCR_TIER=local`.
- **CVEs affecting 4.57.6:**
  | CVE | Affected range | Effect | Triggers here? | Fixed in |
  |---|---|---|---|---|
  | **CVE-2026-4372** | transformers < 5.3.0 | Malicious `config.json` `_attn_implementation_internal` field → downloads & **executes arbitrary Python**, *bypasses* `trust_remote_code` | **Yes — on the exact `pipeline()`/`from_pretrained` path**, if an attacker controls `LOCAL_GEMMA_MODEL` or the target Hub repo/revision | 5.3.0 |
  | **CVE-2026-1839** | transformers < 5.0.0rc3 | `Trainer._load_rng_state()` deserialization RCE | **No** — CleanOCR only does inference, never `Trainer` | 5.0.0rc3 |
  | **CVE-2025-14929** (PYSEC-2025-217) | (X-CLIP checkpoint conversion) | Deserialization RCE in X-CLIP checkpoint conversion | **No** — no X-CLIP / checkpoint-conversion code path | (see advisory) |
- **Exploitability:** The dangerous one is **CVE-2026-4372**. CleanOCR pins the
  model *name* in code but the id is env-controlled and the revision is **not**
  pinned (matches audit finding #9). If the local tier is deployed and the env
  var or the upstream Gemma repo is attacker-influenced, loading the config
  alone runs code — no `trust_remote_code` opt-in needed. In the default
  standard/Gemini tier this dependency is never imported, so risk = **0** there.
- **Minimum safe version to pin:** **`transformers==5.3.0`** (clears all three).
  ⚠️ This is a **major-version jump** — `requirements-local.txt` deliberately
  holds the 4.x series the code targets, and `gemma_provider.py` /
  `surya_provider.py` `pipeline()` kwargs must be re-verified for 5.x before
  moving. Interim hardening without the bump: pin `revision=` + `safetensors`
  and lock `LOCAL_GEMMA_MODEL` out of the environment.

### 3 — Frontend npm tree (`frontend/package-lock.json`) — **Mixed; only `axios` is runtime-reachable**

`npm audit` reports 14 advisories (7 high, 6 moderate, 1 low). The lockfile
pins them, so `npm ci` is reproducible, but the pinned versions are vulnerable.

- **Runtime-reachable (ships in the browser bundle):**
  - **`axios` 1.0.0–1.15.2** — **SSRF via `NO_PROXY` hostname-normalization bypass** (+ incomplete-fix follow-up for 127.0.0.0/8), and prototype-pollution auth-bypass in `validateStatus` merge. This is the frontend's HTTP client; the SSRF matters if any axios request target is influenced by page/config data. **Fix: axios ≥ 1.15.3** (or latest 1.x that clears both `NO_PROXY` CVEs).
  - `form-data` 4.0.0–4.0.5 — CRLF injection via unescaped multipart field names. Fix ≥ 4.0.6.
  - `follow-redirects` ≤ 1.15.11 — leaks auth headers across cross-domain redirects. Fix ≥ 1.15.12.
- **Dev/build-time only (not shipped to users; lower real risk):**
  `vite` 7.0.0–7.3.3 (dev-server path traversal / `fs.deny` bypass / WS file read),
  `rollup` ≤ 4.58.0 (path-traversal file write), `postcss` < 8.5.10,
  `minimatch` / `picomatch` / `brace-expansion` (ReDoS), `ajv`, `flatted`,
  `js-yaml` / `yaml` (DoS), `@babel/core` (source-map file read). These only bite
  during `npm run dev` / `build`, not in production served assets.
- **Fix path:** `npm audit fix` clears all 14 with available fixes (verify no
  breaking major bumps for `vite`/`rollup`); prioritize `axios`, `form-data`,
  `follow-redirects`.

---

## Explicitly-requested libraries — verdicts

### Pillow `12.3.0` — **not vulnerable at this pin**
- **Usage:** `PIL.Image.open(img_path)` in `ocr_processor.py:51` opens a **PNG
  that Poppler generated locally**, not an attacker upload; `Image.fromarray`/
  `Image.open(...).convert("RGB")` elsewhere operate on server-produced images.
  There is **no path where an attacker-supplied image file reaches
  `Image.open`** — the untrusted bytes are PDFs, handled by Poppler (finding #1).
- **Decompression-bomb DoS:** the relevant CVE classes and the
  `DecompressionBombError` guard live in Pillow; but 12.3.0 is current and the
  bomb vector in CleanOCR is really *Poppler rendering at 300 DPI* (audit #7),
  capped by `MAX_PDF_PAGES`. `Image.MAX_IMAGE_PIXELS` is left at Pillow's default
  (raises past ~178M px), so a self-generated giant PNG would warn/error rather
  than exhaust memory silently.
- **Malformed-image overflows:** the 2026 Pillow CVEs — **CVE-2026-25990**
  (PSD out-of-bounds write, ≤ 12.1.0, fixed 12.1.1), **CVE-2026-42308/42310/42311**
  (PSD memory corruption, < 12.2.0, fixed 12.2.0), **CVE-2026-42309** (polygon/
  ImagePath nested-list heap overflow, < 12.2.0, fixed 12.2.0) — are **all fixed
  below 12.3.0**, and none of their triggers (PSD parsing, `ImageDraw.polygon`)
  are used by CleanOCR anyway. **No action; keep ≥ 12.2.0.**

### OpenCV `opencv-python-headless==5.0.0.93` — **not vulnerable, and code path not triggered**
- **Usage:** `app/core/image_utils.py` calls `cv2.cvtColor / threshold /
  warpAffine / getRotationMatrix2D` on **numpy arrays converted from
  already-decoded PIL images**. CleanOCR **never** calls `cv2.imread` /
  `imdecode` / `VideoCapture` on attacker bytes — the vulnerable codec decoders
  are never reached.
- The notable recent codec CVE, **CVE-2025-53644** (uninitialized pointer →
  heap write on crafted **JPEG/JPEG2000**, affects 4.10.0/4.11.0, fixed 4.12.0),
  is both (a) fixed far below the pinned 5.0.0.93 and (b) in a decoder CleanOCR
  doesn't invoke. **No action.**

### PyMuPDF / mupdf — **not a dependency**
Not in any requirements file, not imported anywhere (`grep` for `fitz`/`pymupdf`
is empty). The PDF-RCE history for MuPDF does not apply. PDF handling is
exclusively Poppler-via-pdf2image (finding #1).

### pdf2image `1.17.0` — **no CVE in the wrapper itself**
Pure-Python subprocess wrapper; no known CVE at 1.17.0 (PyPI advisories empty).
Its security posture *is* the Poppler binary it drives (finding #1). Arguments
are server-generated paths — **no command injection** (`poppler_path` from
config, filenames are UUIDs; no `shell=True` anywhere in the repo).

### poppler-utils — see finding #1 (the actual risk).

### ImageMagick — **not used at all**
No `Wand`, no `magick`/`convert`/`identify` binary, no subprocess shelling to
ImageGraphicsMagick anywhere in the repo. The **ImageTragick** delegate-RCE
class (`CVE-2016-3714` family) is **N/A** — there is no `convert`/`identify`
shell-out with unsanitized filenames to confirm-or-deny; the delegate surface
simply does not exist here.

### requests `2.34.2` — **clean, and not in the runtime path**
- No CVE at 2.34.2 (well above the `CVE-2024-35195`/`CVE-2024-47081` fix lines).
- **Only imported by `scripts/*.py`** (dev/verification helpers) — **never by
  `app/`**. It does not run in the served application, so SSRF/redirect defaults
  are not exposed to end users.

### httpx `0.28.1` — **clean; no user-controlled URL surface**
- No CVE at 0.28.1. Present because `fastapi.testclient` and `google-genai`
  import classic httpx (the `httpx2` supply-chain concern from the prior audit
  was resolved by replacing it with this pin).
- **SSRF/redirect exposure:** google-genai calls **fixed Google API endpoints**;
  CleanOCR never constructs an httpx request to a user-supplied URL. httpx also
  does **not** follow redirects by default (`follow_redirects=False`), so the
  redirect-handling concern is moot. **No action.**

### urllib3 `2.7.0` / certifi `2026.6.17` / httpcore `1.0.9` — **clean**
Transitive under requests/httpx/google-genai; no advisories at pinned versions.
`certifi 2026.6.17` is current (no stale-CA bundle issue).

### Zip / tar / rar extraction — **no such library, no such code path**
- No `zipfile.extractall`, `shutil.unpack_archive`, `tarfile`, `rarfile`,
  `py7zr`, or any archive-extraction call anywhere in the repo (`grep` empty).
- The committed 45 MB scan `.zip` is **inert data** — no code ever opens it.
- **Zip Slip / path traversal via extraction is N/A** — there is nothing to
  traverse into.

### python-multipart `0.0.32` — **clean at this pin (fixes already included)**
Starlette/FastAPI route form uploads through it. The 2024–2026 DoS/file-write
CVEs are all fixed at-or-below 0.0.32: **CVE-2026-53539** (quadratic querystring
DoS, fixed 0.0.30), **CVE-2026-40347** (preamble/epilogue DoS, fixed 0.0.26),
**CVE-2024-53981**/**CVE-2024-27313** (header DoS, older). PyPI advisories empty
for 0.0.32. **No action** — the upload cap in `save_upload_capped` adds defense
in depth anyway.

### starlette `1.3.1` / fastapi `0.139.0` — **clean at pinned versions**
No advisories at these pins. The multipart-DoS lineage (`CVE-2025-54121`,
`CVE-2024-47874`) and the BadHost `CVE-2026-48710` class are all below the pin
line here. Note CleanOCR runs **no auth/CORS/TrustedHost middleware** (audit
#4/#10) — an *architecture* gap, not a dependency CVE.

### Others scanned, clean at pin
`numpy 2.4.6`, `redis 8.0.1`, `celery 5.6.3`, `kombu 5.6.2`,
`cryptography 49.0.0`, `pyyaml 6.0.3` (used only as `yaml.safe_load` in one
test — no `yaml.load` deserialization sink), `python-magic 0.4.27`,
`uvicorn 0.50.0`, `websockets 16.0`, `cffi 2.0.0`, `pydantic 2.13.4`,
`google-genai 2.10.0`, `surya-ocr 0.20.0`, `accelerate 1.14.0`,
`torch 2.12.1` — no known CVEs at the pinned versions.

---

## Recommended pin actions (do NOT apply yet — report only)

| Priority | Component | Where | Current | Pin to | Why |
|---|---|---|---|---|---|
| **P1** | poppler-utils | `Dockerfile` apt | unversioned (trixie 25.03.0-5) | **≥ 25.06.0** (`25.03.0-5+deb13u2`+) | UAF (`CVE-2025-52886`) + DoS (`CVE-2025-43718`) reachable pre-auth from `/upload` |
| **P2** | transformers | `requirements-local.txt` | 4.57.6 | **5.3.0** (or pin `revision=`+safetensors as interim) | `CVE-2026-4372` RCE on the `pipeline()` path (local tier only) |
| **P3** | axios | `frontend` | ≤ 1.15.2 | **≥ 1.15.3** | SSRF (`NO_PROXY` bypass) + auth-bypass, runtime-reachable |
| P4 | form-data, follow-redirects | `frontend` | vulnerable | latest patch | CRLF injection / header leak |
| P5 | vite/rollup/toolchain | `frontend` | vulnerable | `npm audit fix` | dev/build-time only |

The application-tier Python pins in `requirements.txt`/`constraints.txt` need
**no changes** — they are already above every relevant fix line.
