# Context.md

## Project Metadata
*   **Name:** CleanOCR
*   **Goal:** Production-grade historical text extraction for **Academic Research** (Mormon History).
*   **Current Focus:** Generalizing the platform for robust Citation/Metadata handling and Enterprise Production Hardening.

## Tech Stack
*   **Core:** Python 3.11+, FastAPI, Celery, Redis.
*   **Database (Set B):** SQLAlchemy 2.0, SQLite (`workspaces/cleanocr.db`), PostgreSQL (`DATABASE_URL`).
*   **AI:** Google Gemini 3.1 Flash Lite (Standard Tier & Layout Pre-flighting), Gemini 3.8 Flash (Pro Tier), Gemini 3.5 Flash Lite (Fallback).
*   **Image Processing:** OpenCV (Headless), Numpy, PIL (Pillow).
*   **Infra:** Docker, Docker Compose.

## Active Status
*   **Phase:** Production Gaps Hardening — Set C: Validation & Adversarial Testing (Exit Gate In Review — awaiting human manual audit).
*   **Status:** Set C deliverables are verified except two partially evidenced scope items. **Verified:** (1) RedTeam Campaign 3 defended 10/10 attack vectors under armed safety interlock, run in-process via FastAPI `TestClient`; (2) CI/CD workflow `.github/workflows/ci.yml` runs `secret-scan`, `test`, `frontend-build`, and a gated Docker `build`, all green on GitHub Actions; (3) Full test suite stands at 198/198 tests passing locally and in CI; (4) Campaign 2 null-timestamp logging bug fixed; RedTeam scripts capped and interlocked; (5) Historical PDF burst via Poppler verified on Windows; (6) Docs, `walkthrough.md`, and `Retrospective.md` updated. **Deferred:** containerized RedTeam run against `docker-compose.redteam.yml`, and live historical-scan OCR through Gemini with `DiffViewer.tsx` sync check.
*   **Next:** Human project owner performs the manual audit and decides whether to run or formally defer the two items above; `@PM` then closes Set C. Exit gate checklist is tracked in `production_gaps_plan.md` (local only, gitignored).

## Recent Decisions
*   **2026-11-03:** **Set C Exit Gate Review (@QA / @PM):** CI green on `c6e44f7` after fixing test-suite rate limiting against CI's live Redis. Set C exit gate recorded with 9 verified items, 2 deferred scope items (containerized RedTeam run; live Gemini E2E + `DiffViewer.tsx` sync), and a required human manual audit before sign-off.
*   **2026-11-02:** **Documentation Clearinghouse & Set C Verification (@QA):** Evaluated and applied all proactive documentation updates across `ARCHITECTURE.md` (CI/CD pipeline diagram, RedTeam topology, mobile UI standards, 167 tests), `README.md` (chaos testing instructions, CI/CD matrix), and `tests/redteam_artifacts/README.md`. Appended Phase 22 verification proof to `walkthrough.md`. Formulated structured git commit recommendation for human decision gate.
*   **2026-11-02:** **CI/CD Pipeline Matrix & Strict TDD (@Eng):** Wrote failing tests in `tests/test_ci_pipeline.py` asserting `frontend-build` job and build dependency gating. Enhanced `.github/workflows/ci.yml` with Node 20.x build step and gated `build` job on both unit tests and frontend compilation. Re-verified 24/24 CI tests pass.
*   **2026-11-02:** **RedTeam Campaign 3 Adversarial Validation (Set C):** Executed automated chaos suite across 10 attack vectors under armed safety interlock. Verified that: (1) rate limiter throttles burst uploads at 3/min with `Retry-After: 60s`; (2) auth header timing delta across 10k evaluations is 0.0013ms; (3) SQLAlchemy ORM parameterization safely neutralized all search SQL injections (`' OR '1'='1`, `UNION SELECT`); (4) SQLite WAL mode handled 20 concurrent write threads with 0 lock errors; (5) Redis failure degraded gracefully without process termination.
*   **2026-11-02:** **System Architecture & RedTeam Alignment (Set C):** Audited and rectified stale container entry point commands in `docker-compose.redteam.yml` to maintain parity with `app/` package architecture. Fixed latent `NameError` in `mock_vision.py` and implemented `detect_layout_type` on `RedTeamMockProvider`. Established explicit adversarial API contracts, safety interlock state machine, and CI/CD matrix dependencies in `implementation_plan.md`.
*   **2026-11-02:** **Validation & Adversarial Testing Discovery (Set C):** Formulated scope across three core pillars: (1) Phase 13 RedTeam Chaos Campaign targeting isolated `docker-compose.redteam.yml` with strict safety interlock (`GOOGLE_API_KEY == "MOCK_KEY_DO_NOT_CHARGE"`), rate limiting spoofing, auth fuzzing, SQL injection, and Redis/worker fault injection; (2) Live historical PDF E2E verification using `latter_day_saints_messenger_and_advocate_vol_1_and_2.pdf` processed with Gemini 3.1 Flash Lite and dynamic layout padding; (3) CI/CD matrix pipeline automation adding frontend Node 20 build gating to `.github/workflows/ci.yml`.
*   **2026-11-02:** **Persistence & Storage (Set B):** Implemented SQLAlchemy 2.0 dual-engine persistence (SQLite default with WAL pragma, PostgreSQL via `DATABASE_URL`). Built `GET /jobs` and `GET /jobs/{id}` APIs with automatic Redis-to-DB fallback. Built mobile-first responsive `JobHistory.tsx` component and executed Documentation Clearinghouse. Established Human Decision Gate for full-session Git commits.
*   **2026-01-27:** Adopted `AGENTS.md` "Operating System".
*   **2026-01-27:** **Architecture Decision:** Modularize image logic into `image_utils.py` (Functional, Stateless).
*   **2026-01-27:** **Feature Selection:** Proceeding with **Deskew + Padding** to improve OCR. **Split** is reserved as a fallback/debugging tool.
*   **2026-01-27:** **Integration:** `image_utils.py` implemented and integrated into `convert_pdf.py`.
*   **2026-01-28:** **Production Features:** Implemented Sanitization, Smart Caching, and JSON Logging.
*   **2026-01-28:** **Architecture:** Adopted "Optimistic Caching" in `server.py`.
*   **2026-01-28:** **Status API:** Implemented `GET /status/{job_id}` with real-time Polling.
*   **2026-01-28:** **Frontend:** Integrated `react-pdf` for Side-by-Side verification.
*   **2026-01-28:** **Scalability:** Refactored `batch_ocr.py` to use `ThreadPoolExecutor` (4x Concurrency).
*   **2026-01-28:** **Reliability:** Removed hardcoded sleeps in favor of Exponential Backoff.
*   **2026-01-28:** **Tooling:** Added `test_upload.py` for CLI-based end-to-end verification.
*   **2026-01-28:** **Job Isolation:** Implemented directory wiping in `worker.py` to prevent data pollution between jobs.
*   **2026-01-29:** **Resilience:** Implemented Client-Side Persistence (`localStorage`) to recover job history on reload.
*   **2026-01-29:** **UX:** Added "Onboarding Steps" and "Empty States" to Frontend.
*   **2026-01-29:** **Architecture (Critical):** Implemented **Job Sandboxing** (`workspaces/{job_id}/`) to ensure strict isolation for concurrent jobs. Removed global folder wiping.
*   **2026-01-29:** **Refactor:** Migrated all helper scripts to accept dynamic path arguments.
*   **2026-01-29:** **Citation System:** Implemented Metadata-aware stitching.
    *   **Backend:** `POST /upload` accepts optional Form Data.
    *   **Frontend:** Modal Driven Input.
    *   **Worker:** Persists metadata to `workspaces/{job_id}/metadata.json`.
*   **2026-01-29:** **Protocol:** Updated Source Control Ignores (`workspaces/` and logs) to prepare for Main Branch merge.
*   **2026-01-29:** **RedTeam Infra:** Established `docker-compose.redteam.yml` for isolated stress testing. Mock mode implemented.
*   **2026-02-20:** **Investigation (@PM):** Completed investigation into concurrency and accuracy. Drafted `implementation_plan.md` to shift from sequential processing to a Celery-based Producer-Consumer pipeline, and to introduce context-aware prompts block-by-block.
*   **2026-02-20:** **Milestone (@Eng & @QA):** Completed Implementation of Phase 14 (Concurrency & Accuracy). Refactored backend to use Celery Chords, ProcessPoolExecutor, Redis counters, and introduced Context-Aware Two-Pass Verification. Implemented Test-Driven Development (TDD) mandate.
*   **2026-02-20:** **Bugfix (@Eng/Arch):** Converted `ProcessPoolExecutor` to `ThreadPoolExecutor` because Celery daemon processes are forbidden from spawning children. `pdf2image` releases GIL, so performance remains identical.
*   **2026-02-20:** **Bugfix (@QA):** Identified Edge-Case in Smart Caching logic. Updated `server.py` to bypass cache if the previously cached job has a "failed" status, preventing infinite loops of failed jobs.
*   **2026-02-20:** **Script Fix:** Standardized `start.bat` and `start.sh` to automatically launch the Vite frontend server in the background for zero-code users.
*   **2026-02-20:** **Milestone (@Eng & @QA):** Completed Implementation of Phase 15 (Front-Facing Diagnostic Stats). Instrumented the backend to capture file sizes and processing intervals, exposed these via the `GET /status/{job_id}` endpoint, and integrated "Glassmorphic" stat badges into the frontend `JobCard`.
*   **2026-02-21:** **Cleanup (@PM & @Arch):** Executed "Option 4: Consolidation & Code Cleanup" from the roadmap. Purged legacy sequential output directories (`CleanOCR_Finalv2`, `ocr_jsonv2`, `output_images`, `_archive`, `output`, `services`) in favor of the sandboxed `workspaces/` pipeline. Migrated legacy scripts to `scripts/debug/` and enforced `app/core/config.py` as the ultimate source of truth.
*   **2026-02-21:** **System Arch:** Consolidated redundant IDE AI/Agent configuration directories (`.agent`, `.agents`, `.antigravity`) into a single unified `.agents/` structure to govern AI behavior and `AGENTS.md` adherence. Verified only one `AGENTS.md` exists globally.
*   **2026-07-12:** **Dynamic Layout Detection:** Swapped static pre-padding for dynamic, per-page layout detection. Exposes `add_padding` separately and invokes pre-flight layout classification via `LAYOUT_PROMPT` inside `GoogleVisionProvider` to conditionally apply padding only on multi-column pages.
*   **2026-10-02:** **Model Research & Lineup Optimization (@PM / @Arch):** Identified imminent hard retirement of Gemini 2.5 family on October 20, 2026. Evaluated Gemini 3 series (`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-3.1-pro`), pricing, `media_resolution`, and thinking token cost dynamics. Selected `gemini-3.1-flash-lite` ($0.25 in / $1.50 out) as Standard workhorse for minimum per-page cost (~$0.0028/page), `gemini-3.8-flash` (`thinking_level=LOW`) as Pro tier, and decoupled low-res layout detection. Documented multi-milestone upgrade roadmap in `pie_in_the_sky.md` Section 9.
*   **2026-10-02:** **Milestone 0 Executed (@Eng / @QA):** Applied Gemini 3 model upgrade across `app/core/config.py`, `.env`, `.env.example`, `app/services/google_vision.py`, unit tests, and `ARCHITECTURE.md`. Decoupled layout pre-flighting with `MEDIA_RESOLUTION_LOW` and enforced `LOW` thinking level on 3.8. All unit tests green.
*   **2026-11-01:** **Operational Readiness & Test Stabilization (@QA / @Eng):** Configured `norecursedirs` in `pytest.ini` to exclude adversarial stress tests (`stress_test.py`) from automated discovery, patched `app/core/config.py` to gracefully fall back `POPPLER_PATH` to system PATH when invalid on Windows, reinstalled `python-magic-bin` for host Windows environments, and confirmed all 144 backend tests and frontend Vite builds pass cleanly.
*   **2026-11-02:** **Production Gaps Set A: Security & Access Control (@Eng / @QA):** Implemented API Key verification (`verify_api_key`) and Redis token-bucket rate limiting (`RateLimiter`) with custom exception unwrapping in `app/api/server.py`. Added dual frontend key support with Axios interceptor and `SettingsModal.tsx`. Authored test-first TDD tests (`tests/test_auth_and_rate_limit.py`) and verified all 153 tests pass with 0 regressions.
*   **2026-11-02:** **Production Gaps Set B Sprint Activated (@PM):** Formally closed Set A upon HITL sign-off. Initiated Set B (Persistence & Storage). Aligned model roadmap metadata tracking (Gemini 3.1/3.8/3.5, token usage, layout classifications) into relational database schema specs.
*   **2026-11-02:** **Operating System Expansion & Set B Approval (@PM / HITL):** Formally approved Set B Implementation Plan. Enshrined the Continuous Documentation Continuity protocol, `@QA` Clearinghouse mandate, and Human Decision Gate for Git commit strategies across `AGENTS.md`. `@PM` cleared exit gate and handed off to `@Arch`.
*   **2026-11-02:** **Set B System Design & Architecture Completed (@Arch):** Established SQLAlchemy 2.0 database models (`JobModel`, `JobMetadataModel`, `JobResultModel`), defined dual-layer Redis fast-path with graceful DB fallback, codified explicit API contracts for `GET /jobs` and `GET /jobs/{job_id}`, and validated that Celery Beat retention daemon preserves relational records while purging disk workspaces. Cleared `@Arch` exit gate and handed off to `@Eng`.

## Next Objectives
1.  **Production Gaps Set B: Persistence & Storage (@Eng / @Des / @QA):**
    *   **Goal:** Implement SQLAlchemy 2.0 relational database persistence (SQLite default / PostgreSQL ready), persistent `GET /jobs` pagination and filtering API, React job history sync, and Celery Beat workspace cleaner daemon.
2.  **Production Gaps Set C: Validation & Adversarial Testing (@RedTeam / @QA):**
    *   **Goal:** Phase 13 RedTeam chaos test, live historical E2E verification, and GitHub Actions CI/CD pipeline.
