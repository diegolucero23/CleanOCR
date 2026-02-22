import pytest
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.api.server import app
import time

client = TestClient(app)

def test_upload_sets_stats_in_redis():
    """TDD Test: Verifies POST /upload sets upload_time and file_size in Redis."""
    with patch('app.api.server.redis_client', autospec=True) as mock_redis, \
         patch('app.api.server.validate_file_type', return_value=True), \
         patch('app.api.server.run_ocr_pipeline.apply_async') as mock_task, \
         patch('app.api.server.os.remove'), \
         patch('app.api.server.os.path.getsize', return_value=1048576), \
         patch('app.api.server.time.time', return_value=1620000000.0):

        mock_redis.get.return_value = None  # No cache hit
        
        # We need a dummy pdf
        files = {'file': ('dummy.pdf', b'fake pdf content', 'application/pdf')}
        response = client.post("/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        job_id = data['job_id']
        
        # Verify redis_client.set was called for upload_time and file_size
        mock_redis.set.assert_any_call(f"cache:{job_id}:upload_time", 1620000000.0, ex=86400)
        mock_redis.set.assert_any_call(f"cache:{job_id}:file_size", 1048576, ex=86400)

def test_stitch_task_sets_end_time():
    """TDD Test: Verifies stitch_markdown_task sets end_time in Redis."""
    with patch('app.workers.celery_worker.redis.Redis.from_url') as mock_redis_cls, \
         patch('app.workers.celery_worker.stitch_to_markdown.stitch_markdown'), \
         patch('app.workers.celery_worker.time.time', return_value=1620000100.0):
        
        mock_redis = MagicMock()
        mock_redis_cls.return_value = mock_redis
        
        from app.workers.celery_worker import stitch_markdown_task
        dummy_job_id = "job-123"
        stitch_markdown_task([], dummy_job_id, "dummy_in", "dummy_out", None, None)
        
        mock_redis.set.assert_any_call(f"cache:{dummy_job_id}:end_time", 1620000100.0)

def test_get_status_calculates_stats():
    """TDD Test: Verifies GET /status returns calculated stats when job is completed."""
    with patch('app.api.server.redis_client', autospec=True) as mock_redis, \
         patch('app.api.server.os.path.exists', return_value=True), \
         patch('builtins.open', unittest.mock.mock_open(read_data="dummy markdown")):
        
        def redis_get_side_effect(key):
            if key.endswith(":status"):
                return b"completed"
            elif key.endswith(":upload_time"):
                return b"1620000000.0"
            elif key.endswith(":end_time"):
                return b"1620000100.0"  # 100 seconds processing
            elif key.endswith(":file_size"):
                return b"1048576"  # 1 MB
            elif key.endswith(":total_pages"):
                return b"10"
            return None
        
        mock_redis.get.side_effect = redis_get_side_effect
        
        response = client.get("/status/job-123")
        assert response.status_code == 200
        data = response.json()
        
        assert "upload_time" in data
        assert data["upload_time"] == 1620000000.0
        assert "file_size" in data
        assert data["file_size"] == 1048576
        assert "processing_time" in data
        assert data["processing_time"] == 100.0
        
        # Complexity heuristic check: min(10.0, (1 MB * 0.2) + (10 pages * 0.1) + (100 sec * 0.05))
        # 0.2 + 1.0 + 5.0 = 6.2
        assert "complexity" in data
        assert data["complexity"] == 6.2
