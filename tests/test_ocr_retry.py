"""
tests/test_ocr_retry.py

Covers Gap 2 (silent OCR failure / Celery retry) and Gap 3 (failed_pages.log format).
"""
import os
import re
import json
import tempfile
import threading
from unittest.mock import patch, MagicMock

import pytest

from app.services.ocr_processor import (
    OCRPageFailure,
    log_failure,
    process_single_image,
)
from app.core import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_error(code, message="error"):
    """Build a google.genai ClientError with the given code."""
    from google.genai.errors import ClientError
    err = ClientError(code=code, response_json={"error": {"code": code, "message": message}})
    return err


# ---------------------------------------------------------------------------
# Gap 2 — process_single_image raises on failure (no more silent strings)
# ---------------------------------------------------------------------------

class TestProcessSingleImageRaises:
    def test_api_error_raises_ocr_page_failure(self, tmp_path):
        """Non-429 ClientError must raise OCRPageFailure, not return a string."""
        img_path = tmp_path / "page_001.png"
        img_path.write_bytes(b"fake-png")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        args = ("page_001.png", 1, 0, str(tmp_path), str(out_dir), "job-1")

        with patch("app.services.ocr_factory.get_provider") as mock_factory, \
             patch("PIL.Image.open"):
            mock_provider = MagicMock()
            mock_provider.generate_content.side_effect = _client_error(500, "Server error")
            mock_factory.return_value = mock_provider

            with pytest.raises(OCRPageFailure):
                process_single_image(args)

    def test_generic_exception_raises_ocr_page_failure(self, tmp_path):
        """Any unexpected exception must raise OCRPageFailure."""
        img_path = tmp_path / "page_001.png"
        img_path.write_bytes(b"fake-png")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        args = ("page_001.png", 1, 0, str(tmp_path), str(out_dir), "job-2")

        with patch("app.services.ocr_factory.get_provider") as mock_factory, \
             patch("PIL.Image.open"):
            mock_provider = MagicMock()
            mock_provider.generate_content.side_effect = RuntimeError("unexpected")
            mock_factory.return_value = mock_provider

            with pytest.raises(OCRPageFailure):
                process_single_image(args)

    def test_max_retries_raises_ocr_page_failure(self, tmp_path):
        """Exhausting all 429 retries must raise OCRPageFailure."""
        img_path = tmp_path / "page_001.png"
        img_path.write_bytes(b"fake-png")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        args = ("page_001.png", 1, 0, str(tmp_path), str(out_dir), "job-3")

        rate_limit_error = _client_error(429, "RESOURCE_EXHAUSTED")

        with patch("app.services.ocr_factory.get_provider") as mock_factory, \
             patch("PIL.Image.open"), \
             patch("time.sleep"):  # don't actually sleep in tests
            mock_provider = MagicMock()
            mock_provider.generate_content.side_effect = rate_limit_error
            mock_factory.return_value = mock_provider

            with pytest.raises(OCRPageFailure, match="Max retries exceeded"):
                process_single_image(args)

    def test_success_returns_string(self, tmp_path):
        """Successful processing must still return a success string (not raise)."""
        img_path = tmp_path / "page_001.png"
        img_path.write_bytes(b"fake-png")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        args = ("page_001.png", 1, 0, str(tmp_path), str(out_dir), "job-4")

        with patch("app.services.ocr_factory.get_provider") as mock_factory, \
             patch("PIL.Image.open"):
            mock_provider = MagicMock()
            mock_provider.generate_content.return_value = '{"markdown_content": "text"}'
            mock_factory.return_value = mock_provider

            result = process_single_image(args)
            assert "✅ Success" in result

    def test_skip_if_json_exists(self, tmp_path):
        """Already-processed pages are skipped without calling the API."""
        img_path = tmp_path / "page_001.png"
        img_path.write_bytes(b"fake-png")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "page_001.json").write_text("{}", encoding="utf-8")

        args = ("page_001.png", 1, 0, str(tmp_path), str(out_dir), "job-5")

        with patch("app.services.ocr_factory.get_provider") as mock_factory:
            result = process_single_image(args)
            mock_factory.assert_not_called()
            assert "Skipped" in result


# ---------------------------------------------------------------------------
# Gap 2 — completed_pages NOT incremented on failure
# ---------------------------------------------------------------------------

class TestCeleryCompletedPagesAccuracy:
    def test_completed_pages_not_incremented_on_failure(self):
        """When process_single_image raises, ocr_page_task must NOT increment completed_pages."""
        mock_redis = MagicMock()

        with patch("app.workers.celery_worker.batch_ocr.process_single_image",
                   side_effect=OCRPageFailure("forced failure")), \
             patch("app.workers.celery_worker.redis.Redis.from_url", return_value=mock_redis):

            from app.workers.celery_worker import ocr_page_task
            # Direct call — Celery runs eagerly without a broker in test context.
            # The retry raises MaxRetriesExceededError when retries are exhausted.
            from celery.exceptions import MaxRetriesExceededError, Retry
            with pytest.raises((MaxRetriesExceededError, Retry, OCRPageFailure, Exception)):
                ocr_page_task("job-99", "page_001.png", "/img", "/out")

            # Key assertion: completed_pages was never incremented
            mock_redis.incr.assert_not_called()

    def test_completed_pages_incremented_on_success(self):
        """completed_pages must be incremented exactly once on success."""
        mock_redis = MagicMock()

        with patch("app.workers.celery_worker.batch_ocr.process_single_image",
                   return_value="✅ Success: page_001.png"), \
             patch("app.workers.celery_worker.redis.Redis.from_url", return_value=mock_redis):

            from app.workers.celery_worker import ocr_page_task
            result = ocr_page_task("job-88", "page_001.png", "/img", "/out")

            mock_redis.incr.assert_called_once_with("cache:job-88:completed_pages")
            assert result == "page_001.png"


# ---------------------------------------------------------------------------
# Gap 3 — failed_pages.log format
# ---------------------------------------------------------------------------

class TestLogFailureFormat:
    def test_log_entry_has_four_fields(self, tmp_path):
        """Each log entry must have exactly 4 pipe-separated fields."""
        log_path = str(tmp_path / "failed.log")
        original = config.LOG_FILE
        config.LOG_FILE = log_path
        try:
            log_failure("page_007.png", "Max Retries Exceeded", job_id="abc-123")
        finally:
            config.LOG_FILE = original

        with open(log_path) as f:
            line = f.readline().strip()

        parts = line.split("|")
        assert len(parts) == 4, f"Expected 4 fields, got {len(parts)}: {line}"

    def test_log_entry_fields_order(self, tmp_path):
        """Format must be job_id|ISO-timestamp|filename|reason."""
        log_path = str(tmp_path / "failed.log")
        original = config.LOG_FILE
        config.LOG_FILE = log_path
        try:
            log_failure("page_007.png", "SSL Error", job_id="job-xyz")
        finally:
            config.LOG_FILE = original

        with open(log_path) as f:
            line = f.readline().strip()

        job_id_field, ts_field, filename_field, reason_field = line.split("|")
        assert job_id_field == "job-xyz"
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts_field), (
            f"Timestamp not in ISO format: {ts_field}"
        )
        assert filename_field == "page_007.png"
        assert reason_field == "SSL Error"

    def test_log_entry_unknown_job_id_when_none(self, tmp_path):
        """When job_id is None, the field must read 'unknown'."""
        log_path = str(tmp_path / "failed.log")
        original = config.LOG_FILE
        config.LOG_FILE = log_path
        try:
            log_failure("page_001.png", "some reason", job_id=None)
        finally:
            config.LOG_FILE = original

        with open(log_path) as f:
            line = f.readline().strip()

        assert line.startswith("unknown|")

    def test_log_is_thread_safe(self, tmp_path):
        """Concurrent log_failure calls must not interleave partial lines."""
        log_path = str(tmp_path / "failed.log")
        original = config.LOG_FILE
        config.LOG_FILE = log_path

        try:
            def write(i):
                log_failure(f"page_{i:03d}.png", "error", job_id=f"job-{i}")

            threads = [threading.Thread(target=write, args=(i,)) for i in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            config.LOG_FILE = original

        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 50
        for line in lines:
            assert len(line.split("|")) == 4, f"Malformed line: {line}"
