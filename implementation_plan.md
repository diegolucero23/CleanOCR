# implementation_plan.md - RedTeam Safety Infrastructure

**Status:** 🏗️ Draft
**Author:** @Architect
**Target:** `CleanOCR-Enterprise` Security Layer

## 1. Executive Summary
We are establishing a "Live Fire Range" for the `@RedTeam` agent. This requires a dedicated infrastructure configuration that physically restricts the agent's ability to consume funds (Wallet Safety) or crash the host machine (Resource Safety).

**Core Philosophy:** "Trust, but Verify." We do not trust the agent to be careful; we constrain the environment so it *cannot* be dangerous.

## 2. System Architecture Changes

### A. The Container Strategy (Hard Isolation)
We will create a parallel deployment specifically for stress testing. This prevents "configuration drift" in the main `docker-compose.yml` while allowing extreme settings for the RedTeam.

| Feature | Production (`docker-compose.yml`) | RedTeam (`docker-compose.redteam.yml`) |
| :--- | :--- | :--- |
| **Port (Web)** | `8000` | `8001` (Avoids conflict) |
| **Port (Redis)** | `6379` | `6380` (Avoids pollution) |
| **Source Code** | Read/Write (Development) | **Read-Only** (`:ro`) |
| **Google API** | Live Credentials | **Mocked** (`MOCK_KEY_DO_NOT_CHARGE`) |
| **CPU Limit** | Unbounded | **0.5 CPUs** (Hard cap) |
| **RAM Limit** | Unbounded | **512MB** (Hard cap) |

### B. The Mocking Layer (Logical Isolation)
We will inject a shim into the OCR service. Instead of relying on an external mocking library (which adds dependency bloat), we will implement a "Mode Switch" directly in the service logic.

* **Trigger:** `GOOGLE_API_KEY == "MOCK_KEY_DO_NOT_CHARGE"`
* **Behavior:**
    1.  Log warning: `⚠️ MOCK MODE DETECTED`.
    2.  `time.sleep(1.5)`: **Crucial.** Simulates network latency to stress-test Redis queue handling. Instant returns would not accurately test the worker logic.
    3.  Return static JSON payload compliant with the `google.cloud.vision` schema.

## 3. Component Design Specs

### 3.1. Infrastructure: `docker-compose.redteam.yml`
* **Services:** `redis`, `web`, `worker`.
* **Network:** Default bridge network (isolated from prod network).
* **Volumes:**
    * Root: `./:/app:ro` (Prevents `rm -rf /` from working on source code).
    * Sandbox: `./tests/redteam_artifacts:/app/output` (The **only** writeable zone).
* **Directives:**
    * Use `deploy.resources.limits` to enforce 512MB RAM cap. Docker will `OOMKill` the container if RedTeam leaks memory, saving the Host OS.

### 3.2. Configuration: `.env.redteam`
A distinct environment file loaded *only* by the RedTeam compose file.

```ini
# Security Interlocks
MODE=REDTEAM
LOG_LEVEL=DEBUG

# The Kill Switch - If this is missing, the app should fail safe
GOOGLE_API_KEY=MOCK_KEY_DO_NOT_CHARGE

# Mocked 3rd Party Services (Future Proofing)
STRIPE_KEY=mock_stripe
SMTP_PASSWORD=mock_smtp
```

### 3.3. Application Logic: `services/ocr.py` (or `worker.py`)
We need a unified entry point for OCR that checks the environment.

**Pseudocode Flow:**
```python
def process_document(doc):
    if config.GOOGLE_API_KEY == "MOCK_KEY_DO_NOT_CHARGE":
        # 1. Latency Simulation (Stress the Queue)
        sleep(1.5)
        # 2. Return Schema-Compliant Mock
        return MockObject(text="MOCK OCR RESULT", confidence=0.99)
    else:
        # Real Execution
        return google_vision_client.detect_text(doc)
```

## 4. Verification Plan (The "Exit Gate")

Before declaring this task complete, `@QA` must verify the following scenarios manually:

### Test Case A: The "Wallet Saver"
1.  Start RedTeam container: `docker-compose -f docker-compose.redteam.yml --env-file .env.redteam up`
2.  Trigger a job via API.
3.  **Verify:** Logs show `⚠️ MOCK MODE DETECTED`.
4.  **Verify:** Google Cloud Console shows **0** requests.

### Test Case B: The "Filesystem Shield"
1.  Exec into worker: `docker exec -it <container_id> /bin/bash`
2.  Attempt: `rm server.py`
3.  **Verify:** System returns `Read-only file system`.
4.  Attempt: `touch /app/output/test.log`
5.  **Verify:** Success (Sandbox is writeable).

### Test Case C: The "Resource Ceiling"
1.  (Optional) Run a Python script inside the container to consume RAM.
2.  **Verify:** Container crashes/restarts at ~512MB usage. Host machine remains responsive.

## 5. Next Steps for @Engineer
1.  Create `tests/redteam_artifacts/` and add `.gitignore`.
2.  Create `.env.redteam`.
3.  Create `docker-compose.redteam.yml` using the specs above.
4.  Modify the Python OCR service to handle the Mock Key.