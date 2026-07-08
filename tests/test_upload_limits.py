"""
Tests for the upload abuse limits on POST /upload:
  - size cap (MAX_UPLOAD_MB) enforced while streaming to disk
  - page-count cap (MAX_PDF_PAGES) checked before any OCR work is dispatched
  - unreadable/corrupt PDFs rejected instead of queued
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.server import app
from app.core import config

client = TestClient(app)


def _post_dummy_pdf():
    files = {'file': ('dummy.pdf', b'fake pdf content', 'application/pdf')}
    return client.post("/upload", files=files)


def test_upload_rejects_oversize_file():
    with patch.object(config, 'MAX_UPLOAD_MB', 0), \
         patch('app.api.server.redis_client', autospec=True), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task:
        response = _post_dummy_pdf()

        assert response.status_code == 413
        assert "upload limit" in response.json()["detail"]
        mock_task.assert_not_called()


def test_upload_rejects_too_many_pages():
    with patch('app.api.server.redis_client', autospec=True), \
         patch('app.api.server.magic', object()), \
         patch('app.api.server.validate_file_type', return_value=True), \
         patch('app.api.server.get_pdf_page_count', return_value=config.MAX_PDF_PAGES + 1), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task:
        response = _post_dummy_pdf()

        assert response.status_code == 413
        assert "pages" in response.json()["detail"]
        mock_task.assert_not_called()


def test_upload_rejects_unreadable_page_count():
    with patch('app.api.server.redis_client', autospec=True), \
         patch('app.api.server.magic', object()), \
         patch('app.api.server.validate_file_type', return_value=True), \
         patch('app.api.server.get_pdf_page_count', return_value=None), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task:
        response = _post_dummy_pdf()

        assert response.status_code == 400
        mock_task.assert_not_called()


def test_upload_within_limits_is_queued():
    with patch('app.api.server.redis_client', autospec=True) as mock_redis, \
         patch('app.api.server.magic', object()), \
         patch('app.api.server.validate_file_type', return_value=True), \
         patch('app.api.server.get_pdf_page_count', return_value=3), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task:
        mock_redis.get.return_value = None  # no cache hit
        response = _post_dummy_pdf()

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        mock_task.assert_called_once()


def test_upload_fails_closed_without_libmagic():
    """Without libmagic there is no content check; the endpoint must reject
    uploads with a 503 instead of falling back to extension matching."""
    with patch('app.api.server.magic', None), \
         patch('app.api.server.redis_client', autospec=True), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task:
        response = _post_dummy_pdf()

        assert response.status_code == 503
        assert "libmagic" in response.json()["detail"]
        mock_task.assert_not_called()
