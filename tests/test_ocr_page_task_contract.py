"""
tests/test_ocr_page_task_contract.py

Contract between the Celery page task and the OCR service.

Regression (2026-11-03): commit 4bebf0b changed ocr_page_task to call
process_single_image(img, in_dir, out_dir), but the service takes ONE args
tuple. Every page raised TypeError, was retried for ~3.5 minutes, and the job
was still reported "completed" with empty markdown. Existing tests mocked
process_single_image without a spec, so any call signature passed.

Coverage:
  - ocr_page_task calls the real process_single_image signature
    (autospec enforces it), passing (filename, total, index, in, out, job_id)
"""

import uuid
from unittest.mock import MagicMock, call, patch

from app.db import database
from app.db.models import JobModel
from app.workers.celery_worker import ocr_page_task, stitch_markdown_task


def test_ocr_page_task_calls_process_single_image_with_args_tuple(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    for n in (1, 2, 3):
        (images / f"page_{n:03d}.png").write_bytes(b"png")
    out_dir = tmp_path / "ocr_json"

    with patch("app.workers.celery_worker.batch_ocr.process_single_image", autospec=True) as mock_proc, \
         patch("app.workers.celery_worker.redis.Redis.from_url", return_value=MagicMock()):
        result = ocr_page_task("job-123", "page_002.png", str(images), str(out_dir))

    assert result == "page_002.png"
    mock_proc.assert_called_once_with(("page_002.png", 3, 1, str(images), str(out_dir), "job-123"))


def _seed_job(job_id: str, total_pages: int) -> None:
    with database.get_db_context() as db:
        db.add(JobModel(id=job_id, status="queued", file_hash=f"hash-{job_id}", original_filename="scan.pdf",
                        file_size=1000, total_pages=total_pages, processed_pages=0, model_name="m",
                        upload_time=1.0))


def _run_stitch(job_id: str, results, tmp_path):
    redis_mock = MagicMock()
    with patch("app.workers.celery_worker.stitch_to_markdown.stitch_markdown"), \
         patch("app.workers.celery_worker.redis.Redis.from_url", return_value=redis_mock):
        stitch_markdown_task(results, job_id, str(tmp_path / "ocr_json"), str(tmp_path / "out"),
                             str(tmp_path / "metadata.json"), f"hash-{job_id}")
    with database.get_db_context() as db:
        job = db.get(JobModel, job_id)
        return job.status, job.processed_pages, job.error_message, redis_mock


def test_job_with_zero_successful_pages_is_failed_not_completed(tmp_path):
    job_id = str(uuid.uuid4())
    _seed_job(job_id, total_pages=9)

    status, processed, error, redis_mock = _run_stitch(job_id, [None] * 9, tmp_path)

    assert status == "failed"
    assert processed == 0
    assert error and "9" in error
    assert call(f"cache:{job_id}:status", "failed") in redis_mock.set.call_args_list
    # An empty result must not be cached against the file hash, or re-uploads return it.
    assert not any(c.args[0] == f"cache:hash-{job_id}" for c in redis_mock.set.call_args_list)


def test_partial_success_completes_with_accurate_page_count(tmp_path):
    job_id = str(uuid.uuid4())
    _seed_job(job_id, total_pages=3)

    status, processed, _, redis_mock = _run_stitch(job_id, ["page_001.png", None, "page_003.png"], tmp_path)

    assert status == "completed"
    assert processed == 2
    assert call(f"cache:{job_id}:status", "completed") in redis_mock.set.call_args_list
