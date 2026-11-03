"""
tests/test_rate_limit_isolation.py

Reproduction for the 2026-11-03 CI failure (see Retrospective.md): with a live
Redis, the API rate limiter in app.core.security throttled the test suite's own
requests and 15 upload tests got HTTP 429. Locally it was hidden because the
limiter fails open when Redis is absent.

Coverage:
  - With the real limiter forced to deny (a full Redis window), requests made
    by tests are still not throttled, because conftest.py disables rate
    limiting by default.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app.core.security as security
from app.api.server import app


def test_suite_requests_not_throttled_when_limiter_window_is_full():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    with patch.object(security._limiter, "is_allowed", return_value=(False, 60)), \
         patch("app.api.server.redis_client", redis_mock), \
         patch("app.core.config.CLEANOCR_API_KEY", None):
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(5):
            res = client.get("/status/550e8400-e29b-41d4-a716-446655440000")
            assert res.status_code != 429, "test-suite traffic was rate limited"
