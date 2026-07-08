"""
tests/test_upload_api.py

Covers upload endpoint: cache hit path, MIME rejection, metadata edge cases,
and Redis stats (upload_time, file_size).
"""
import io
import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Import app once — reuse across tests to avoid Docker OOM from repeated module loads
from app.api.server import app


@pytest.fixture(autouse=True)
def mock_page_count():
    """The hardened /upload asks poppler for a page count, which the fake PDF
    bytes used here can't satisfy. Page-count acceptance/rejection paths are
    covered with real PDFs in test_upload_limits.py."""
    with patch("app.api.server.get_pdf_page_count", return_value=3):
        yield


@pytest.fixture()
def mock_redis():
    """Replace the module-level redis_client singleton with a fresh MagicMock."""
    m = MagicMock()
    m.get.return_value = None  # no cache by default
    with patch("app.api.server.redis_client", m):
        yield m


@pytest.fixture()
def mock_pipeline():
    """Patch run_ocr_pipeline.apply_async so no Celery broker is needed."""
    mock_task = MagicMock()
    mock_task.id = "task-abc"
    with patch("app.api.server.run_ocr_pipeline") as mp:
        mp.apply_async.return_value = mock_task
        yield mp


@pytest.fixture()
def client(tmp_path, mock_redis, mock_pipeline):
    with patch("app.api.server.config.UPLOAD_DIR", str(tmp_path)):
        with TestClient(app, raise_server_exceptions=True) as c:
            c._mock_redis = mock_redis
            c._mock_pipeline = mock_pipeline
            yield c


def _pdf_bytes():
    return b"%PDF-1.4 fake content"


# ---------------------------------------------------------------------------
# Cache hit path
# ---------------------------------------------------------------------------

class TestCacheHit:
    def test_duplicate_file_returns_cached_job_id(self, client):
        """When the file hash matches a completed cached job, return that job_id."""
        def redis_get(key):
            if ":status" in key:
                return b"completed"
            return b"existing-job-id"

        client._mock_redis.get.side_effect = redis_get

        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="deadbeef"):
            response = client.post(
                "/upload",
                files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cached"
        assert data["job_id"] == "existing-job-id"

    def test_cache_hit_on_failed_job_reprocesses(self, client):
        """When cached job has status=failed, ignore cache and reprocess."""
        def redis_get(key):
            if ":status" in key:
                return b"failed"
            if key.startswith("cache:"):
                return b"failed-job-id"
            return None

        client._mock_redis.get.side_effect = redis_get

        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="deadbeef"):
            response = client.post(
                "/upload",
                files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        client._mock_pipeline.apply_async.assert_called_once()

    def test_no_cache_dispatches_new_task(self, client):
        """When no cache entry exists, a new Celery task is dispatched."""
        client._mock_redis.get.return_value = None

        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="newhash"):
            response = client.post(
                "/upload",
                files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "job_id" in data
        client._mock_pipeline.apply_async.assert_called_once()


# ---------------------------------------------------------------------------
# MIME / file type validation
# ---------------------------------------------------------------------------

class TestMimeValidation:
    def test_non_pdf_returns_400(self, client):
        """Non-PDF file must be rejected with HTTP 400."""
        with patch("app.api.server.validate_file_type", return_value=False):
            response = client.post(
                "/upload",
                files={"file": ("evil.txt", io.BytesIO(b"not a pdf"), "text/plain")},
            )

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_valid_pdf_is_accepted(self, client):
        """Valid PDF must pass validation and proceed to queue."""
        client._mock_redis.get.return_value = None

        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="abc123"):
            response = client.post(
                "/upload",
                files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "queued"


# ---------------------------------------------------------------------------
# Redis stats: upload_time and file_size
# ---------------------------------------------------------------------------

class TestUploadStats:
    def test_upload_time_and_file_size_stored_in_redis(self, client):
        """upload_time and file_size must be persisted in Redis on a new job."""
        client._mock_redis.get.return_value = None

        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="statshash"):
            response = client.post(
                "/upload",
                files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            )

        assert response.status_code == 200
        job_id = response.json()["job_id"]

        set_calls = [str(c) for c in client._mock_redis.set.call_args_list]
        upload_time_stored = any(f"cache:{job_id}:upload_time" in c for c in set_calls)
        file_size_stored = any(f"cache:{job_id}:file_size" in c for c in set_calls)

        assert upload_time_stored, "upload_time not stored in Redis"
        assert file_size_stored, "file_size not stored in Redis"


# ---------------------------------------------------------------------------
# Metadata edge cases
# ---------------------------------------------------------------------------

class TestMetadataEdgeCases:
    def _upload(self, client, **form_fields):
        client._mock_redis.get.return_value = None
        with patch("app.api.server.validate_file_type", return_value=True), \
             patch("app.api.server.calculate_sha256", return_value="meta-hash-unique"):
            return client.post(
                "/upload",
                files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
                data=form_fields,
            )

    def test_no_metadata_fields_accepted(self, client):
        """Upload with no optional fields must still succeed (all fields nullable)."""
        response = self._upload(client)
        assert response.status_code == 200

    def test_metadata_passed_to_celery_task(self, client):
        """Provided metadata must be forwarded to run_ocr_pipeline.apply_async."""
        response = self._upload(
            client,
            title="The Messenger",
            volume="3",
            issue="5",
            date="1835-01-01",
        )
        assert response.status_code == 200

        call_kwargs = client._mock_pipeline.apply_async.call_args.kwargs
        metadata_arg = call_kwargs["args"][3]
        assert metadata_arg["title"] == "The Messenger"
        assert metadata_arg["volume"] == "3"
        assert metadata_arg["issue"] == "5"
        assert metadata_arg["date"] == "1835-01-01"

    def test_skip_metadata_flag_forwarded(self, client):
        """skip_metadata=True must be passed through to the worker metadata dict."""
        response = self._upload(client, skip_metadata="true")
        assert response.status_code == 200

        call_kwargs = client._mock_pipeline.apply_async.call_args.kwargs
        metadata_arg = call_kwargs["args"][3]
        assert metadata_arg["skip_metadata"] is True
