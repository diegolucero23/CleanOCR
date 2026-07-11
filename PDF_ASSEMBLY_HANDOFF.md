# Handoff: Memorial Archive PDF Builder
**Date:** 2026-07-11
**Requested by:** Diego Lucero (repo owner)
**Audience:** The secondary agent (or engineer) who will build the PDF
**Repo baseline:** `main` @ `791f329` (post-sprint, 138 tests green)

---

## 1. Mission

Diego has roughly **2–3 dozen document scans from his late father's life** — certificates,
event paperwork, administrative documents, legal documents, essays, and similar. The scans
are heterogeneous: **different physical sizes, different orientations (portrait/landscape,
some rotated), and likely mixed file formats**.

Your job is to stitch these scans into **one single, correctly ordered PDF** that the
**current CleanOCR build ingests cleanly end-to-end** — through `/upload`, the Celery OCR
pipeline, and the stitcher — so the collection can be transcribed and preserved as text.

This is a personal memorial archive. Treat the source scans as irreplaceable masters:
**never modify or delete the originals; work only on copies.** Prefer lossless or
near-lossless handling at every step.

### Deliverables
1. `scripts/build_archive_pdf.py` — a standalone CLI (same style as the other tools in
   `scripts/`) that assembles the PDF from a folder of scans plus an ordering manifest.
2. A `--verify` preflight mode that validates the output against CleanOCR's actual
   ingestion gates (§3) **before** anything is uploaded.
3. `tests/test_archive_builder.py` — pytest coverage following existing conventions (§7).
4. The built PDF itself (once Diego supplies the scans), verified via a live upload.

---

## 2. Why this document exists: CleanOCR is opinionated about its input

CleanOCR was built for 19th-century newspaper microfilm. It does **not** accept image
uploads — the **only ingestion path is a single PDF** (`POST /upload` accepts exactly one
`application/pdf` file). The pipeline then:

1. **Bursts the PDF back into images** at `PDF_RENDER_DPI=300`
   (`app/services/pdf_converter.py` → `convert_pdf_in_chunks`). Whatever you embed gets
   re-rasterized; the PDF's declared **page geometry in points**, not the embedded image's
   pixel count, determines the raster size.
2. **Preprocesses every page image** (`app/core/image_utils.py::preprocess_image`):
   deskew + a center-gutter split (§4 — this has sharp edges for non-newspaper content).
3. **OCRs each page via Gemini** with a newspaper-tuned prompt
   (`app/core/prompts.py::OCR_PROMPT` — extracts Volume/Issue/Date metadata).
4. **Stitches per-page JSON into one Markdown document**
   (`app/services/stitcher.py::stitch_markdown`), with YAML frontmatter from the
   upload-form metadata.

So "align with the current build" means: build a PDF whose geometry, size, and page
content survive steps 1–2 intact, and choose upload metadata so steps 3–4 produce
sensible output for personal documents (§5.6).

---

## 3. Hard ingestion gates (the PDF is rejected if any fail)

These are enforced in code today. Numbers are the defaults from `app/core/config.py`;
all are env-overridable, but **build to the defaults** — don't ask Diego to loosen caps
for a 30-page file.

| # | Gate | Limit (default) | Enforced in |
|---|------|-----------------|-------------|
| G1 | libmagic MIME check — file content must be `application/pdf` (real `%PDF-` header at byte 0, no leading junk). Fails **closed** if libmagic is missing (503). | strict | `app/api/server.py::validate_file_type` |
| G2 | Upload size, streamed cap | `MAX_UPLOAD_MB=100` → 413 | `app/api/server.py::save_upload_capped` |
| G3 | Poppler `pdfinfo` must read a page count | readable, else 400 | `app/api/server.py::get_pdf_page_count` |
| G4 | Page count | `MAX_PDF_PAGES=500` → 413 | `app/api/server.py` + `pdf_converter.py` |
| G5 | Per-page pixel guard: every page's raster at 300 DPI must be ≤ `MAX_PAGE_PIXELS=150,000,000` px, **and** `pdfinfo` must emit parseable per-page sizes (fail-closed `ValueError` otherwise). One bad page refuses the **entire** PDF (job fails with "PDF conversion generated 0 images"). | 150M px @ 300 DPI | `app/services/pdf_converter.py::find_oversized_pages` |
| G6 | SHA-256 dedup cache: re-uploading byte-identical files returns the **cached** job instead of reprocessing. | 24 h TTL | `app/api/server.py` (Smart Caching) |

### G5 is the one you can silently get wrong — do the geometry math

The guard computes `width_pts / 72 × 300` by `height_pts / 72 × 300` pixels per page.
The ceiling is therefore a page **area of ~1,667 in² (~8.64M pt²)** — enormous (US Letter
is 93.5 in², ~8.4M raster px, i.e. ~5% of the limit), **unless you declare pixels as
points**.

Worked failure case: an A4 sheet scanned at 600 DPI is 4961×7016 px. Naively writing it
as a PDF page of 4961×7016 **points** declares a 69″×97″ page; at 300 DPI that
re-rasterizes to ~604M px → G5 refuses the whole file.

**Rule: page size in points = `pixels / scan_dpi × 72`** — i.e., the page's true physical
size. Get the DPI from the image metadata when present, from a manifest override when not,
and default to 300 as a last resort (§5.3).

### G6 practical note
During testing you will upload near-identical builds. Byte-identical re-uploads return the
old job. Any content change (even one metadata byte) produces a new hash, so normal
iteration is fine; to force reprocessing of an identical file use
`python scripts/test_upload.py --flush-job <job-prefix>` or `--flush` (see README
"Clearing Cache").

---

## 4. Pipeline interactions you must design around (not gates, but quality traps)

These are behaviors of the current build that heterogeneous personal documents will hit.
The PDF builder can neutralize the first two; the rest are flagged so nobody is surprised.

### 4.1 Deskew fixes small tilts only — **you must normalize orientation before assembly**
`image_utils._deskew` estimates skew via `cv2.minAreaRect` and corrects within roughly
±45°. A page that is sideways (90°) or upside-down (180°) is **not** fixed — and because
`warpAffine` keeps the original canvas size, any large correction crops content at the
corners. Gemini also transcribes rotated text far worse.

**Requirement:** every page in the assembled PDF must already be upright in reading
orientation. Apply `PIL.ImageOps.exif_transpose()` first (phone photos of documents carry
EXIF orientation), then honor per-file manifest rotation overrides (§5.2) for scanner
output with no EXIF. Genuinely landscape documents (many certificates) stay landscape —
"upright" means readable without turning your head, not "portrait".

### 4.2 The 300 DPI re-raster means embedded resolution above ~300 DPI is wasted
Pages are re-rendered at 300 DPI regardless of source resolution. Downsampling masters
above 300 DPI to ~300 DPI before embedding loses nothing downstream and keeps the file
comfortably under G2. Never upsample low-res scans — declare their true size and let
poppler do the scaling.

### 4.3 Known risk — the center-gutter split (`_add_padding`) runs on **every** page
After deskew, `image_utils._add_padding` cuts each page image vertically down the middle
and inserts a 50 px white gutter — a newspaper-spread assumption. On single-column
letters, essays, and certificates this injects a white band through the middle of every
line of text. The OCR prompt explicitly guards against hallucinating columns and Gemini
generally reads across the band, but expect occasional mid-word artifacts.

**Do not "fix" this inside the builder** (it operates on the pipeline side, not the PDF
side) and do not change pipeline behavior unilaterally. If output quality is poor, the
right change is a config flag (e.g. `GUTTER_SPLIT=off`) in `app/core/image_utils.py` +
`config.py` — propose it to Diego first (HITL, per §8 conventions).

### 4.4 The OCR prompt and stitcher are periodical-flavored
`OCR_PROMPT` asks for Volume/Issue/Date; the stitcher groups pages into "issues" and
defaults missing values to 1/1 (a known non-periodical behavior — see
`HANDOFF_CONTEXT.md` §2, "Volume/Issue metadata defaulted to 1/1 — expected"). Harmless
for this collection; §5.6 tells you what to pass at upload so the output frontmatter and
title are right.

### 4.5 Partial-output semantics
If a page permanently fails OCR (rate limits, malformed JSON), the chord still completes
and the stitcher emits **partial output** from the pages that succeeded
(`celery_worker.py::ocr_page_task`). After a live run, reconcile the stitched Markdown
against the manifest page count and check `failed_pages.log`
(format: `job_id|ISO-timestamp|filename|reason`) before declaring the job done.

---

## 5. Builder specification

### 5.1 CLI shape
```
python scripts/build_archive_pdf.py \
    --scans   path/to/scans/            # copies of the masters, never the originals
    --manifest path/to/manifest.yaml \
    --out     lucero_family_archive.pdf \
    [--verify-only]                     # run §6 preflight on an existing PDF
    [--dry-run]                         # report per-page decisions without writing
```
Standalone script under `scripts/`, `print`-based output like its siblings
(`test_upload.py`, `repair_pages.py`) — the structured-JSON logging setup is an `app/`
convention, not a `scripts/` one. Use `pyyaml` (already pinned) for the manifest.

### 5.2 Manifest — explicit ordering, never filesystem order
Page order in the PDF **is** page order in the archive (`page_001…` after burst, and the
stitcher reads pages in filename order). Alphabetical directory listings of scanner
output (`IMG_2041.jpg`, `Scan0003.tif`) are meaningless — require a manifest:

```yaml
title: "Lucero Family Archive — Documents of [Father's Name]"
default_dpi: 300          # fallback when an image carries no DPI metadata
pages:
  - file: certs/birth_certificate.jpg
    label: "Birth certificate, 1948"
    rotate: 0             # 0 | 90 | 180 | 270 (CW), applied after EXIF transpose
  - file: legal/property_deed_p1.tif
    label: "Property deed, p.1"
    dpi: 400              # per-file override when metadata is missing/wrong
  # ...
```

Ordering is Diego's call (§9 open questions); a sensible default he can reorder is
**by document category, chronological within category** (certificates → legal →
administrative → event paperwork → essays). `label` is for the build report and any
future bookmarking — it does not enter the PDF content.

Fail loudly on: a manifest entry whose file is missing, files in `--scans` not listed in
the manifest (unless `--allow-unlisted`), and unreadable/zero-byte images.

### 5.3 Per-page normalization (in this order)
1. **Load** via Pillow. Accept JPEG/PNG/TIFF (multi-frame TIFFs: each frame becomes a
   page, in frame order, inserted at the entry's position). HEIC/HEIF requires
   `pillow-heif`, which is **not** in the locked dependency set — if Diego's scans
   include HEIC, follow the dependency procedure in §5.5 or ask him to export JPEG.
2. **EXIF transpose** (`ImageOps.exif_transpose`).
3. **Manifest rotation override** (`rotate:`), for scans with no/incorrect EXIF.
4. **Color mode**: convert `RGBA`/`P`/`LA` → flatten onto white → `RGB`;
   `CMYK` → `RGB`; keep `L` (grayscale) as-is — smaller and OCRs fine.
   Grayscaling color documents is **not** allowed (seals, stamps, and letterheads carry
   meaning in this collection).
5. **Resolve DPI**: image metadata (`img.info["dpi"]`) → manifest `dpi:` → manifest
   `default_dpi` → 300. Reject absurd values (<50 or >1200) with a clear error naming
   the file.
6. **Cap resolution**: if effective DPI > 300, downsample to 300 DPI (Lanczos), per §4.2.
7. **Compute page box**: `w_pt = px_w / dpi × 72`, likewise height (§3/G5).
8. **Pixel-guard preflight per page**: assert
   `(w_pt/72×300) × (h_pt/72×300) ≤ config.MAX_PAGE_PIXELS` — import the constant, don't
   hardcode 150e6. With steps 6–7 done right this can't fire; keep it as a tripwire.

### 5.4 Assembly — use `img2pdf`
Recommendation: **`img2pdf`** (plus the already-pinned Pillow for normalization).
It embeds JPEG streams **bit-perfectly** (no recompression generation loss — this is the
archival argument), writes clean page boxes from explicit sizes, and its output passes
libmagic/poppler trivially. Feed it per-page `layout_fun` sizes from step 5.3.7, or
save normalized pages as JPEG (quality ≥ 90, `dpi=` set) and let img2pdf read the DPI.

Fallback if adding a dependency is vetoed: pure Pillow
(`first.save(out, save_all=True, append_images=rest, resolution=dpi)`) — acceptable, but
it re-encodes and forces a single `resolution` for all pages, which fights the
mixed-size requirement. Prefer img2pdf.

**Size budget (G2):** 100 MB ÷ ~36 pages ≈ 2.7 MB/page average. Letter-size 300 DPI JPEG
at q85–90 runs 0.3–2 MB/page, so the budget is comfortable — but PNG/TIFF masters embed
as FlateDecode and can blow it. Transcode non-JPEG sources to JPEG q90 before embedding;
report the final size in the build summary and fail the build if it exceeds
`config.MAX_UPLOAD_MB`.

### 5.5 Dependency procedure (repo is exact-pinned)
`requirements.txt` header is the law: exact pins resolved on **Python 3.11**, transitive
deps locked in `constraints.txt`, install with
`pip install -r requirements.txt -c constraints.txt`. To add `img2pdf`:
1. Add an exact pin (e.g. `img2pdf==0.6.1`) with a one-line comment saying what it's for.
2. Reinstall in a fresh 3.11 venv (or the Docker image) and regenerate `constraints.txt`
   via `pip freeze`, per the header instructions.
3. Note: img2pdf pulls in `pikepdf` → check `DEPENDENCY_CVE_AUDIT.md` conventions and add
   the new pins there if that document tracks them.

### 5.6 Upload metadata for this collection
When uploading (via the frontend MetadataModal or `scripts/test_upload.py`):
- `title`: `"Lucero Family Archive — Documents of [Father's Name]"` (drives the YAML
  frontmatter `title:` and the H1 in the stitched Markdown — see
  `stitcher.py::stitch_markdown`).
- `volume` / `issue`: leave empty (periodical fields; stitcher tolerates null).
- `date`: optional; a range string like `"1948–2019"` is fine, it's free text.
- `skip_metadata`: **false** — setting it true drops the citation frontmatter and titles
  the output with the raw filename, which is worse for an archive.

---

## 6. Verification — required before handing the PDF to Diego

### 6.1 Preflight (`--verify-only` mode; also runs automatically after every build)
Reuse the repo's own guards instead of re-implementing them:
```python
import magic
from pdf2image import pdfinfo_from_path
from app.core import config
from app.services.pdf_converter import find_oversized_pages

assert magic.Magic(mime=True).from_file(out_path) == "application/pdf"          # G1
assert os.path.getsize(out_path) <= config.MAX_UPLOAD_MB * 1024 * 1024          # G2
info = pdfinfo_from_path(out_path, first_page=1, last_page=config.MAX_PDF_PAGES,
                         timeout=config.PDF_INFO_TIMEOUT)                       # G3
assert info["Pages"] == expected_page_count <= config.MAX_PDF_PAGES             # G4
assert find_oversized_pages(info, config.PDF_RENDER_DPI) == []                  # G5
```
Calling `find_oversized_pages` directly is the point: if the shipped guard changes, the
preflight changes with it. Print a per-page table (page #, source file, size in pts,
projected 300 DPI raster px) in the verification report.

### 6.2 Visual spot-check
Burst the built PDF locally with the repo's own converter
(`convert_pdf_in_chunks(out_path, tmp_dir)`) and eyeball a sample: every page upright,
nothing cropped, orientation overrides applied. This exercises the exact poppler + 
preprocessing path production will use (including the §4.3 gutter, so you see what
Gemini will see).

### 6.3 Live end-to-end
`python scripts/test_upload.py --file lucero_family_archive.pdf` against the running
stack (`docker-compose up`), then confirm: job completes, stitched Markdown page count
matches the manifest, `failed_pages.log` has no entries for this job_id (§4.5). The
`/upload` response's `expectations` block echoes the limits — sanity-check them against
this document. A ~30-page job at 300 DPI is well within the default stream budgets
(600 s base + 30 s/page) and the Gemini daily call cap (2000).

---

## 7. Tests
Add `tests/test_archive_builder.py`, mirroring existing suites (`test_upload_limits.py`,
`test_ingestion_hardening.py` are the closest models):
- manifest parsing: ordering respected, missing file → error, unlisted file → error
- normalization: EXIF-rotated fixture comes out upright; RGBA flattens to white; DPI
  resolution chain (metadata → manifest → default)
- geometry: synthetic 600 DPI image yields correct point dimensions; the
  pixels-as-points failure case from §3 is **prevented** (build a tiny high-DPI fixture,
  assert `find_oversized_pages` returns `[]` on the result)
- G1/G3: built PDF passes libmagic and `pdfinfo`
- size-budget failure path errors cleanly

Generate small fixtures with Pillow at test time; don't commit binary scan fixtures.
**Run tests inside Docker** — `docker exec cleanocr-web-1 python -m pytest tests/ -q` —
Diego's local Python 3.14/Cygwin crashes on some imports (see `HANDOFF_CONTEXT.md` §9).

---

## 8. Repo conventions that bind you
- **Branching:** feature branch → PR → merge; never push to `main`.
- **`HANDOFF_CONTEXT.md` must be updated and committed before your session ends** (§9 of
  that file — standing rule).
- **HITL gates:** anything touching pipeline behavior (`image_utils`, prompts, tiers) or
  new dependencies needs Diego's sign-off before merge. Auth is deliberately deferred —
  do not add any (audit item #10, owner decision 2026-07-07).
- **Pre-commit hooks** are configured (`.pre-commit-config.yaml`) — run them.
- **CI** (`.github/workflows/ci.yml`) must be green on the PR.
- Files >200 lines: read via targeted excerpts / sub-agent rather than loading whole
  (session strategy in `HANDOFF_CONTEXT.md`).

---

## 9. Open questions for Diego (ask before building; block only on Q1–Q2)
1. **Source formats & delivery** — what are the scans (JPEG/PNG/TIFF/HEIC/phone photos?)
   and where will they land (a folder in the repo workspace? Google Drive?). HEIC
   changes the dependency plan (§5.3.1).
2. **Ordering** — approve or amend the category-then-chronological default (§5.2); best
   answered by Diego editing the generated manifest draft.
3. **Multi-page documents** — any double-sided or multi-sheet documents that must stay
   contiguous? (Manifest handles it; just needs his ordering.)
4. **Title/name** — exact archive title and his father's name for the metadata (§5.6).
5. **Gutter risk acceptance** — is he OK running with the §4.3 center-gutter behavior
   for the first pass, or should the config-flag proposal be made first?

---

## 10. Suggested execution order
1. Read this doc + `app/api/server.py`, `app/services/pdf_converter.py`,
   `app/core/image_utils.py`, `app/core/config.py` (they are the contract).
2. Resolve §9 Q1–Q2 with Diego.
3. Dependency PR prep: pin `img2pdf`, regenerate `constraints.txt` (§5.5).
4. Implement `scripts/build_archive_pdf.py` + manifest handling + preflight (§5–6.1).
5. Tests (§7); green inside Docker.
6. Build the real PDF from Diego's scans; run §6.2–6.3 verification.
7. Update `HANDOFF_CONTEXT.md`; open the PR with the build report (per-page table,
   final size, live job_id) in the description.
