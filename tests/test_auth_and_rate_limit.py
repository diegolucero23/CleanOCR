"""
tests/test_auth_and_rate_limit.py

Unit tests for Set A Security & Access Control:
- API Key authentication (X-API-Key and Bearer token).
- Zero-friction open dev mode when CLEANOCR_API_KEY is unset.
- Redis token-bucket / sliding window rate limiting.
- Structured 401 and 429 error responses.
"""
import io
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.server import app


@pytest.fixture(autouse=True)
def mock_common_dependencies():
    """Ensure poppler, mime validation, and celery do not block auth tests."""
    with patch("app.api.server.get_pdf_page_count", return_value=1), \
         patch("app.api.server.validate_file_type", return_value=True), \
         patch("app.api.server.calculate_sha256", return_value="hash-123"), \
         patch("app.api.server.run_ocr_pipeline") as mp:
        mock_task = MagicMock()
        mock_task.id = "task-xyz"
        mp.apply_async.return_value = mock_task
        yield


@pytest.fixture()
def mock_redis():
    """Fresh Redis mock for each test."""
    m = MagicMock()
    m.get.return_value = None
    m.pipeline.return_value = m
    m.execute.return_value = [None, None, 0, None]
    with patch("app.api.server.redis_client", m), \
         patch("app.core.security.redis_client", m):
        yield m


@pytest.fixture()
def client(tmp_path, mock_redis):
    with patch("app.api.server.config.UPLOAD_DIR", str(tmp_path)):
        with TestClient(app, raise_server_exceptions=False) as c:
            c._mock_redis = mock_redis
            yield c


def _pdf_file():
    return {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 test content"), "application/pdf")}


class TestAuthentication:
    def test_open_dev_mode_when_key_unset(self, client):
        """When CLEANOCR_API_KEY is None, requests pass through without auth headers."""
        with patch("app.core.config.CLEANOCR_API_KEY", None):
            res = client.post("/upload", files=_pdf_file())
            assert res.status_code == 200

    def test_request_rejected_without_key_when_configured(self, client):
        """When CLEANOCR_API_KEY is set, unauthenticated requests return 401."""
        with patch("app.core.config.CLEANOCR_API_KEY", "secret-key-123"):
            res = client.post("/upload", files=_pdf_file())
            assert res.status_code == 401
            data = res.json()
            assert data["error"]["code"] == "UNAUTHORIZED"

    def test_request_rejected_with_invalid_key(self, client):
        """Invalid key returns 401."""
        with patch("app.core.config.CLEANOCR_API_KEY", "secret-key-123"):
            res = client.post(
                "/upload",
                files=_pdf_file(),
                headers={"X-API-Key": "wrong-key"}
            )
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHORIZED"

    def test_request_accepted_with_valid_x_api_key(self, client):
        """Valid X-API-Key header allows request."""
        with patch("app.core.config.CLEANOCR_API_KEY", "secret-key-123"):
            res = client.post(
                "/upload",
                files=_pdf_file(),
                headers={"X-API-Key": "secret-key-123"}
            )
            assert res.status_code == 200

    def test_request_accepted_with_valid_bearer_token(self, client):
        """Valid Authorization: Bearer <token> header allows request."""
        with patch("app.core.config.CLEANOCR_API_KEY", "secret-key-123"):
            res = client.post(
                "/upload",
                files=_pdf_file(),
                headers={"Authorization": "Bearer secret-key-123"}
            )
            assert res.status_code == 200

    def test_unprotected_endpoints_accessible_without_auth(self, client):
        """Health and limits endpoints do not require authentication even when key is set."""
        with patch("app.core.config.CLEANOCR_API_KEY", "secret-key-123"):
            res_limits = client.get("/limits")
            assert res_limits.status_code == 200

            res_sys = client.get("/system-status")
            assert res_sys.status_code == 200


class TestRateLimiting:
    def test_upload_rate_limit_exceeded_returns_429(self, client):
        """Exceeding upload rate limit returns 429 with Retry-After header."""
        with patch("app.core.config.CLEANOCR_API_KEY", None), \
             patch("app.core.config.RATE_LIMIT_UPLOADS_PER_MIN", 3), \
             patch("app.core.security.check_rate_limit", return_value=(False, 15)):
            res = client.post("/upload", files=_pdf_file())
            assert res.status_code == 429
            assert res.headers.get("Retry-After") == "15"
            data = res.json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert data["error"]["details"]["retry_after_seconds"] == 15

    def test_status_rate_limit_exceeded_returns_429(self, client):
        """Exceeding status rate limit returns 429."""
        with patch("app.core.config.CLEANOCR_API_KEY", None), \
             patch("app.core.security.check_rate_limit", return_value=(False, 30)):
            res = client.get("/status/550e8400-e29b-41d4-a716-446655440000")
            assert res.status_code == 429
            assert res.headers.get("Retry-After") == "30"
            assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_rate_limiter_in_redis_sliding_window(self):
        """Test the pure sliding window logic with an in-memory/mocked Redis."""
        from app.core.security import RateLimiter
        mock_r = MagicMock()
        limiter = RateLimiter(redis_client=mock_r)

        # Mock Redis pipeline execution: [rem_count, add_count, zcard_result, expire_result]
        pipe = MagicMock()
        mock_r.pipeline.return_value = pipe
        pipe.execute.return_value = [0, 1, 2, True]

        allowed, retry_after = limiter.is_allowed(
            key="test_client",
            max_requests=3,
            window_seconds=60
        )
        assert allowed is True
        assert retry_after == 0

        # Now simulate count exceeding limit (e.g. 4 requests seen in window)
        pipe.execute.return_value = [0, 1, 4, True]
        allowed, retry_after = limiter.is_allowed(
            key="test_client",
            max_requests=3,
            window_seconds=60
        )
        assert allowed is False
        assert retry_after > 0
