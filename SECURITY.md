# CleanOCR Credential Handling

How the Gemini API key (and any future credential) is stored, scoped, scanned
for, and spend-capped. Companion to [SECURITY_AUDIT.md](SECURITY_AUDIT.md)
(point-in-time findings).

---

## 1. Where the key lives

- The **only** supported location is the `.env` file at the repo root
  (`GOOGLE_API_KEY=...`), loaded by `app/core/config.py` via `python-dotenv`.
  Copy [`.env.example`](.env.example) to `.env` and fill it in.
- `.env` and `.env.*` are excluded by both `.gitignore` and `.dockerignore`.
  The two tracked exceptions contain no secrets by design:
  - `.env.example` — placeholders only.
  - `.env.redteam` — mock values only (`MOCK_KEY_DO_NOT_CHARGE`).
- Docker Compose injects the key into containers from your local `.env`
  (`env_file: .env` / `GOOGLE_API_KEY=${GOOGLE_API_KEY}`); it is never baked
  into an image.
- **Never** hardcode a key in source, tests, scripts, compose files, or CI
  YAML. CI and tests use the dummy `test-key-for-ci`; mock mode uses
  `MOCK_KEY_DO_NOT_CHARGE`.

## 2. Secret scanning (pre-commit + CI)

Two layers block key-shaped strings (Google `AIza...` keys, GCP service
accounts, GitHub/Slack/Stripe tokens, private keys, …) from entering history:

1. **Local pre-commit hook** — [gitleaks](https://github.com/gitleaks/gitleaks)
   via [`.pre-commit-config.yaml`](.pre-commit-config.yaml). One-time setup:

   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **CI backstop** — the `secret-scan` job in
   [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs gitleaks over
   the full git history on every push/PR and fails the build on a hit.

Shared config: [`.gitleaks.toml`](.gitleaks.toml). It allowlists only the
known mock/dummy values — the full git history scans clean (see §5), so any
gitleaks hit is a **new** leak. If gitleaks blocks your commit, the fix is
to move the value into `.env`, not to extend the allowlist.

## 3. Key scoping (do this in the Google console)

A default Gemini key is often unrestricted. CleanOCR calls exactly one
Google service — `generativelanguage.googleapis.com`
(`models.generateContent` via the `google-genai` SDK) — so restrict the key
to that surface:

1. Open **Google Cloud Console → APIs & Services → Credentials** and select
   the key (AI Studio keys live in the project AI Studio created).
2. Under **API restrictions**, choose **Restrict key** and select only
   **Generative Language API**. CleanOCR needs nothing else — not Vertex AI,
   not Cloud Vision, not Storage.
3. **Application restrictions**: for a server deployment with a static egress
   IP, add an IP-address restriction. Leave "None" only for local desktop use
   (server-side keys can't use HTTP-referrer restrictions).
4. Belt-and-braces spend controls, independent of the in-app cost guard:
   - **APIs & Services → Generative Language API → Quotas**: lower
     requests-per-minute/day to what you actually need.
   - **Billing → Budgets & alerts**: set a monthly budget with email alerts.
5. Use a **dedicated Google Cloud project** for CleanOCR so the key cannot
   touch resources of other projects and usage is easy to audit.

## 4. Runtime protections in this codebase

- **No key in logs/errors/tracebacks** — `app/core/secrets.py` provides
  `redact()` plus a logging filter installed on the API server, the Celery
  worker, and the Gemini provider. Every site that stringifies an exception
  (`failed_pages.log`, the Redis DLQ entries, structured logs, the upload
  endpoint's traceback dump) passes through it. Full Gemini request/response
  payloads are never logged; responses are written only to per-job JSON
  output files, and requests contain the key in an HTTP header managed by the
  SDK, never in application-visible strings.
- **Cost guard** — `app/core/cost_guard.py` enforces hard caps *before* each
  billed call in `GoogleVisionProvider`:
  - `GEMINI_DAILY_CALL_CAP` (default **2000**) — Redis counter shared by all
    workers, per UTC day.
  - `GEMINI_RUN_CALL_CAP` (default **5000**) — per-process counter that works
    even without Redis (legacy CLI batch mode).
  Set either to `0` to disable. When a cap trips, pages fail fast with a
  `Failed (Budget)` entry instead of retrying, and the run completes without
  further spend. Sizing guide: a full 500-page job ≈ 500 calls + retries +
  boundary-stitch calls, so 2000/day ≈ 3–4 max-size jobs.

## 5. Known historical exposure & rotation procedure

**Status: fully remediated.** An old Gemini key was hardcoded in scripts
committed January 2026. It was **revoked and replaced** (SECURITY_AUDIT.md,
remediation #1), and in July 2026 the repository history was **rewritten to
purge it** — the leaking commits no longer exist on the remote, all commit
SHAs from that era changed, and a full-history gitleaks scan is clean with
no commit allowlist. The current key has never been committed.

Consequences of the rewrite:

- **Clones made before July 2026 are stale and still contain the old key
  in their object store.** Do not fetch/merge across the rewrite — delete
  the stale clone and `git clone` fresh (or `git fetch origin && git
  checkout -B main origin/main && git reflog expire --expire=now --all &&
  git gc --prune=now`).
- The old key itself remains permanently compromised regardless of the
  rewrite (it lived in public history and in old clones) — its revocation,
  not the rewrite, is what made it safe.

If any key is ever exposed again:

1. **Revoke first, investigate second.** Google Cloud Console →
   Credentials → delete the key (or AI Studio → API keys). Creating a
   replacement does *not* disable the old one — delete it.
2. Check **Billing reports** and the Generative Language API metrics for
   usage you don't recognize between exposure and revocation.
3. Put the new key in `.env` only, apply the §3 restrictions, and verify the
   pre-commit hook is installed (`pre-commit install`).
4. History rewrite (`git filter-repo` / BFG + force-push + GitHub support
   ticket to purge cached views) is **optional hygiene once the key is
   dead** — do it before ever making the repo public, and remember every
   collaborator must re-clone. Rewriting history is *never* a substitute for
   revocation.
