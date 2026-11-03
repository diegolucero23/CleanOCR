# RedTeam Adversarial & Chaos Testing Suite

> **Target:** CleanOCR Enterprise (`FastAPI`, `Celery`, `Redis`, `SQLAlchemy 2.0`)  
> **Governing Standards:** [`AGENTS.md`](../../AGENTS.md) — Section 2: `@RedTeam (The Destroyer)` Rules of Engagement

---

## 🔒 1. Mandatory Safety Interlock ("The Kill Switch")

CleanOCR strictly isolates all adversarial testing from production billable APIs:

*   **Interlock Key:** `GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE`
*   **Safety Rule:** Every adversarial script MUST execute a "Ping Check" before firing any traffic. If `GOOGLE_API_KEY != "MOCK_KEY_DO_NOT_CHARGE"`, the test **aborts immediately** with a fatal `ConfigurationError`.
*   **Factory Binding:** `app/services/ocr_factory.py` automatically binds `RedTeamMockProvider` when `MOCK_KEY_DO_NOT_CHARGE` is detected. **Zero outbound external API calls are made.**

---

## 🚀 2. How to Run the Adversarial Suite

### Automated Chaos Campaign 3 (Python Runner)
Run all 10 attack vectors against the local API testbed:
```bash
python tests/redteam_artifacts/campaign_3_adversarial.py
```

### Isolated Docker RedTeam Network
To run stress tests against a containerized instance capped at 512MB RAM and 0.5 CPU:
```bash
# 1. Prepare environment
cp .env.redteam.example .env.redteam

# 2. Launch isolated compose stack (:8001 / redis :6380)
docker-compose -f docker-compose.redteam.yml up --build

# 3. In another terminal, run fuzzing / flooding scripts:
python tests/redteam_artifacts/fuzz_inputs.py
python tests/redteam_artifacts/flood_queue.py

# 4. Memory stress (stops at STRESS_MAX_MB, default 512 MB, so it is safe on the host too)
STRESS_MAX_MB=256 python tests/redteam_artifacts/stress_test.py
```

> **Script safety:** `fuzz_inputs.py` and `flood_queue.py` resolve `.env.redteam` from the repository root (any working directory works) and abort before sending traffic unless it sets `GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE`. Guardrails are covered by `tests/test_redteam_scripts.py`.
>
> **Note:** `campaign_3_adversarial.py` regenerates `campaign_3_adversarial.md` on every run. Commit the report only when you intend to publish a new snapshot.

---

## 🛡️ 3. Attack Vector Matrix (Campaign 3)

| Vector ID | Attack Name | Target Subsystem | Expected Defense |
| :--- | :--- | :--- | :--- |
| **V-01** | Header Spoofing / IP Tracking | RateLimiter | Peer IP tracked; spoofed `X-Forwarded-For` cannot evade limits |
| **V-02** | Upload Burst Flooding (3/min) | RateLimiter | HTTP 429 Too Many Requests with `Retry-After: 60s` |
| **V-03** | Key Timing Attacks | Auth Module | Constant-time key comparison (`secrets.compare_digest`) |
| **V-04** | Missing / Malformed / SQLi Headers | Auth Module | Structured HTTP 401 `{"error": {"code": "UNAUTHORIZED"}}` |
| **V-05** | SQL Injection on `GET /jobs?search=` | Relational DB | SQLAlchemy 2.0 ORM parameterization neutralizes injections |
| **V-06** | Non-Enum `status` Fuzzing | Relational DB | Pydantic regex validator returns HTTP 422 |
| **V-07** | SQLite WAL Concurrency Stress | Relational DB | 20+ concurrent write threads without database lock errors |
| **V-08** | Corrupted PDF / Broken XREF / 0-byte | Ingestion Engine | HTTP 400 Bad Request (`INVALID_FILE`) without worker crash |
| **V-09** | Path Traversal in Filename | Ingestion Engine | Filenames neutralized; saved strictly via UUID (`{job_id}.pdf`) |
| **V-10** | Redis Disconnect Chaos | Distributed Core | Rate limiter fails open gracefully; status degrades to DB |

---

## 🧹 4. Hygiene & Cleanup Policy
*   All temporary files generated during attacks are written to `tests/redteam_artifacts/uploads/`.
*   Every runner must implement a `finally` block to delete temporary PDFs and databases.
*   `.gitignore` ensures `*.pdf`, `*.db`, `*.log`, and working `.env.redteam` files are never tracked in Git.

