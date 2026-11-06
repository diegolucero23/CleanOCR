import os
import json
import uuid
import pytest
import PIL.Image
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.server import app, compute_stream_timeout_seconds, compute_expected_duration_seconds
from app.db.database import get_db_context
from app.db.models import JobModel
from app.core import config
from app.core.image_utils import normalize_broadsheet_image, MAX_IMAGE_DIMENSION, MAX_SAFE_PIXELS
from app.services.ocr_processor import write_atomic_json, process_single_image
from app.workers.celery_worker import stitch_markdown_task


@pytest.fixture
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Job Cancellation Tests (API Contract)
# ---------------------------------------------------------------------------

def test_cancel_active_job_success(test_client):
    """POST /jobs/{job_id}/cancel on an active/processing job sets status to cancelled."""
    job_id = str(uuid.uuid4())
    
    with get_db_context() as db:
        job = JobModel(
            id=job_id,
            status="processing",
            original_filename="active_job.pdf",
            file_size=1024,
            total_pages=4,
            processed_pages=1,
            model_name="gemini-3.1-flash-lite",
        )
        db.add(job)
        db.commit()

    with patch("app.workers.celery_worker.celery_app.control.revoke") as mock_revoke:
        headers = {"X-API-Key": config.CLEANOCR_API_KEY} if config.CLEANOCR_API_KEY else {}
        resp = test_client.post(
            f"/jobs/{job_id}/cancel",
            json={"reason": "User requested cancellation"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] == "cancelled"
        assert "cancelled" in data["message"].lower()
        mock_revoke.assert_called_once()

    # Verify DB persistence
    with get_db_context() as db:
        db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
        assert db_job is not None
        assert db_job.status == "cancelled"
        assert "User requested cancellation" in (db_job.error_message or "")


def test_cancel_terminal_job_fails(test_client):
    """POST /jobs/{job_id}/cancel on completed or failed job returns HTTP 400."""
    job_id = str(uuid.uuid4())
    
    with get_db_context() as db:
        job = JobModel(
            id=job_id,
            status="completed",
            original_filename="completed_job.pdf",
            file_size=1024,
            total_pages=2,
            processed_pages=2,
        )
        db.add(job)
        db.commit()

    headers = {"X-API-Key": config.CLEANOCR_API_KEY} if config.CLEANOCR_API_KEY else {}
    resp = test_client.post(
        f"/jobs/{job_id}/cancel",
        json={"reason": "Cannot cancel completed job"},
        headers=headers,
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "JOB_ALREADY_TERMINAL" in str(data) or "already" in str(data).lower()


def test_cancel_nonexistent_job_fails(test_client):
    """POST /jobs/{job_id}/cancel for non-existent job returns HTTP 404."""
    headers = {"X-API-Key": config.CLEANOCR_API_KEY} if config.CLEANOCR_API_KEY else {}
    resp = test_client.post(
        "/jobs/00000000-0000-0000-0000-000000000000/cancel",
        json={"reason": "Ghost job"},
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Atomic JSON Writing & 0-Byte Poisoning Guard
# ---------------------------------------------------------------------------

def test_write_atomic_json_success(tmp_path):
    """Atomic write creates valid JSON file with non-empty content."""
    target_file = tmp_path / "valid_page.json"
    valid_payload = json.dumps({"markdown_content": "Extracted text", "metadata": {}})
    
    write_atomic_json(str(target_file), valid_payload)
    
    assert target_file.exists()
    assert target_file.stat().st_size > 0
    with open(target_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["markdown_content"] == "Extracted text"
    # Ensure no leftover .tmp file
    assert not (tmp_path / "valid_page.json.tmp").exists()


def test_write_atomic_json_rejects_empty_or_invalid(tmp_path):
    """Empty string, None, or invalid JSON raises ValueError and touches no target file."""
    target_file = tmp_path / "corrupt_page.json"
    
    with pytest.raises(ValueError):
        write_atomic_json(str(target_file), None)
    assert not target_file.exists()

    with pytest.raises(ValueError):
        write_atomic_json(str(target_file), "")
    assert not target_file.exists()

    with pytest.raises(Exception):
        write_atomic_json(str(target_file), "this is not json {")
    assert not target_file.exists()


def test_ocr_skip_ignores_zero_byte_file(tmp_path):
    """A 0-byte JSON file must NOT be skipped; it must trigger reprocessing."""
    input_folder = tmp_path / "images"
    output_folder = tmp_path / "ocr_json"
    input_folder.mkdir()
    output_folder.mkdir()
    
    img_name = "page_001.png"
    img_path = input_folder / img_name
    img = PIL.Image.new("RGB", (100, 100), color="white")
    img.save(img_path)
    
    # Create poison 0-byte json file
    poison_json = output_folder / "page_001.json"
    poison_json.write_text("", encoding="utf-8")
    assert poison_json.stat().st_size == 0
    
    # Mock get_provider to return valid response
    mock_provider = MagicMock()
    mock_provider.generate_content.return_value = json.dumps({
        "markdown_content": "Recovered text from 0-byte poison",
        "metadata": {}
    })
    
    with patch("app.services.ocr_factory.get_provider", return_value=mock_provider):
        res = process_single_image((img_name, 1, 0, str(input_folder), str(output_folder), "job-test-poison"))
        assert "Success" in res
        assert poison_json.stat().st_size > 0
        with open(poison_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["markdown_content"] == "Recovered text from 0-byte poison"


# ---------------------------------------------------------------------------
# 3. Broadsheet Image Downscaling & Normalization
# ---------------------------------------------------------------------------

def test_normalize_broadsheet_image_oversized():
    """An image exceeding 36 Megapixels or 4096px is downscaled to max 4096px preserving aspect ratio."""
    # Create 5000 x 8000 image (40 Megapixels)
    huge_img = PIL.Image.new("RGB", (5000, 8000), color="white")
    normalized = normalize_broadsheet_image(huge_img)
    
    w, h = normalized.size
    assert max(w, h) <= MAX_IMAGE_DIMENSION
    assert w * h <= MAX_SAFE_PIXELS
    # Aspect ratio preserved (5000 / 8000 = 0.625)
    assert abs((w / h) - (5000 / 8000)) < 0.01


def test_normalize_broadsheet_image_standard():
    """An image within normal dimensions (e.g. 1800 x 2400) is returned unmodified."""
    normal_img = PIL.Image.new("RGB", (1800, 2400), color="white")
    normalized = normalize_broadsheet_image(normal_img)
    assert normalized.size == (1800, 2400)


# ---------------------------------------------------------------------------
# 4. Partial Failure Reporting in Celery Chords
# ---------------------------------------------------------------------------

def test_stitch_markdown_task_partial_failure(tmp_path):
    """When some pages succeed and some fail, job status is set to partial_failure, not completed."""
    job_id = "test-job-partial-failure-1234"
    ocr_json_dir = tmp_path / "ocr_json"
    final_md_dir = tmp_path / "output"
    ocr_json_dir.mkdir()
    final_md_dir.mkdir()
    
    # Page 1 succeeded, Page 2 was dropped/failed (None)
    page_1 = ocr_json_dir / "page_001.json"
    page_1.write_text(json.dumps({"markdown_content": "Page 1 text", "metadata": {}}), encoding="utf-8")
    
    with get_db_context() as db:
        existing = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.commit()
        job = JobModel(
            id=job_id,
            status="processing",
            original_filename="partial_doc.pdf",
            file_size=2048,
            total_pages=2,
            processed_pages=1,
        )
        db.add(job)
        db.commit()

    results = ["page_001.png", None]
    
    with patch("app.services.stitcher.stitch_markdown") as mock_stitch, \
         patch("redis.Redis.from_url") as mock_redis_factory:
        mock_redis = MagicMock()
        mock_redis_factory.return_value = mock_redis
        
        status = stitch_markdown_task(results, job_id, str(ocr_json_dir), str(final_md_dir), None, None)
        assert status == "partial_failure"

    with get_db_context() as db:
        db_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
        assert db_job.status == "partial_failure"
        assert db_job.processed_pages == 1
        assert "1 of 2 pages failed" in (db_job.error_message or "").lower() or "missing" in (db_job.error_message or "").lower()


# ---------------------------------------------------------------------------
# 5. Recalibrated Time Estimations
# ---------------------------------------------------------------------------

def test_recalibrated_time_budgets():
    """Verify expected turnaround and stream timeouts match Gemini 3.1 Flash Lite throughput."""
    # 52 pages: expected ~176s (2.9 min)
    expected_52 = compute_expected_duration_seconds(52)
    timeout_52 = compute_stream_timeout_seconds(52)
    assert 150 <= expected_52 <= 200
    assert 150 <= timeout_52 <= 200

    # 4 pages: expected ~32s
    expected_4 = compute_expected_duration_seconds(4)
    timeout_4 = compute_stream_timeout_seconds(4)
    assert 25 <= expected_4 <= 40
    assert 25 <= timeout_4 <= 40
