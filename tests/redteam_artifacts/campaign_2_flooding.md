# RedTeam Campaign 2: Queue Flooding

**Date:** 2026-01-29
**Target:** `http://localhost:8001/upload`
**Agent:** @RedTeam

## 1. Objectives
Test the system's resilience to rapid job submissions (DoS simulation).

## 2. Attack Vectors & Results

| Vector | Payload | Rate | Result | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Burst Flood** | 100 Concurrent Requests | ~90 RPS | **200 OK (Queued)** | ✅ **RESILIENT** |

## 3. Findings
### A. Architecture Strength
The Celery/Redis design successfully decoupled the web server from the worker. The web server responded instantly (0.5s for 50 reqs), while the worker processed the backlog asynchronously. **No downtime observed.**

### B. Observability Failure (Bug Report)
During high load, the JSON logs emitted by the worker showed broken fields:
```json
{"timestamp": null, "level": null, "message": "Cached result..."}
```
**Impact:** Monitoring tools (Datadog/Splunk) would fail to index these logs correctly due to null timestamps.
**Hypothesis:** The `python-json-logger` configuration in `worker.py` might be missing a default formatter for certain Celery log record types.

> **✅ RESOLVED (2026-11-02):** Root cause was not load-related. Both formatters (`app/workers/celery_worker.py`, `app/api/server.py`) referenced `%(timestamp)s` and `%(level)s`, which are not `LogRecord` attributes, so *every* line emitted nulls. They now use `timestamp=True` (ISO-8601 UTC) and rename `levelname` to `level`. Regression test: `tests/test_structured_logging.py`.

## 4. Recommendations
*   **Rate Limiting:** Implement Nginx or FastAPI middleware rate limiting (e.g., 10 req/min per IP) to prevent simple script flooding. **✅ Done:** Redis sliding-window limiter in `app/core/security.py` (Set A).
*   **Fix Logging:** Investigate `jsonlogger` configuration for Celery worker threads. **✅ Done:** see resolution above.
