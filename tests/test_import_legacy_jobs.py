"""
tests/test_import_legacy_jobs.py

scripts/import_legacy_jobs.py records jobs that were OCR'd before the job
database existed (Set B). Their results live only in workspaces/{job_id} and
Redis, so they never appear in Job History, and since the database became the
source of truth for cache hits, re-uploading them would pay for OCR again.

Coverage:
  - Imports job, citation metadata, and markdown result from the workspace
  - Takes file hash and page counts from Redis
  - Is idempotent (never duplicates or overwrites an existing record)
  - Dry run writes nothing
  - Skips workspaces without extracted markdown
"""

import json
from unittest.mock import MagicMock

from app.db import database
from app.db.models import JobModel
from scripts.import_legacy_jobs import import_legacy_job

JOB_ID = "f65376df-6217-4914-8d28-02911b88dbd4"


def _workspace(root, job_id=JOB_ID, markdown="# Obituary\n\nBert Lucero was born"):
    ws = root / job_id
    (ws / "output").mkdir(parents=True)
    (ws / "metadata.json").write_text(json.dumps({
        "title": "Bert Lucero - Full Obituary-1", "volume": None, "issue": None,
        "date": "February 27, 2025", "skip_metadata": False, "original_filename": "Bert Lucero - Full Obituary-1.pdf",
    }))
    if markdown is not None:
        (ws / "output" / "full_extracted_content.md").write_text(markdown)
    return ws


def _redis(job_id=JOB_ID, file_hash="abc123"):
    values = {
        f"cache:{job_id}:status": b"completed",
        f"cache:{job_id}:total_pages": b"2",
        f"cache:{job_id}:completed_pages": b"2",
        f"cache:{job_id}:end_time": b"1792028400.5",
    }
    r = MagicMock()
    r.get.side_effect = values.get
    r.scan_iter.return_value = [f"cache:{file_hash}".encode()]

    def get(key):
        if key == f"cache:{file_hash}":
            return job_id.encode()
        return values.get(key)

    r.get.side_effect = get
    return r


def _delete(job_id):
    with database.get_db_context() as db:
        job = db.get(JobModel, job_id)
        if job:
            db.delete(job)


def test_imports_job_metadata_and_result(tmp_path):
    _delete(JOB_ID)
    _workspace(tmp_path)

    with database.get_db_context() as db:
        assert import_legacy_job(db, JOB_ID, str(tmp_path), _redis()) is True

    with database.get_db_context() as db:
        job = db.get(JobModel, JOB_ID)
        assert job.status == "completed"
        assert job.original_filename == "Bert Lucero - Full Obituary-1.pdf"
        assert job.file_hash == "abc123"
        assert job.total_pages == 2 and job.processed_pages == 2
        assert job.citation_metadata.title == "Bert Lucero - Full Obituary-1"
        assert job.citation_metadata.publication_date == "February 27, 2025"
        assert "Bert Lucero was born" in job.result.markdown_text
    _delete(JOB_ID)


def test_is_idempotent(tmp_path):
    _delete(JOB_ID)
    _workspace(tmp_path)
    with database.get_db_context() as db:
        assert import_legacy_job(db, JOB_ID, str(tmp_path), _redis()) is True
    with database.get_db_context() as db:
        assert import_legacy_job(db, JOB_ID, str(tmp_path), _redis()) is False
    with database.get_db_context() as db:
        assert db.query(JobModel).filter(JobModel.id == JOB_ID).count() == 1
    _delete(JOB_ID)


def test_dry_run_writes_nothing(tmp_path):
    _delete(JOB_ID)
    _workspace(tmp_path)
    with database.get_db_context() as db:
        assert import_legacy_job(db, JOB_ID, str(tmp_path), _redis(), dry_run=True) is True
    with database.get_db_context() as db:
        assert db.get(JobModel, JOB_ID) is None


def test_skips_workspace_without_markdown(tmp_path):
    _delete(JOB_ID)
    _workspace(tmp_path, markdown=None)
    with database.get_db_context() as db:
        assert import_legacy_job(db, JOB_ID, str(tmp_path), _redis()) is False
    with database.get_db_context() as db:
        assert db.get(JobModel, JOB_ID) is None


def test_created_at_uses_original_processing_time(tmp_path):
    """Imported jobs must sort by when they were processed, not import day."""
    from datetime import datetime, timezone

    _delete(JOB_ID)
    _workspace(tmp_path)
    with database.get_db_context() as db:
        import_legacy_job(db, JOB_ID, str(tmp_path), _redis())
    with database.get_db_context() as db:
        created = db.get(JobModel, JOB_ID).created_at
        if created.tzinfo is None:  # SQLite drops tzinfo
            created = created.replace(tzinfo=timezone.utc)
        assert created == datetime.fromtimestamp(1792028400.5, tz=timezone.utc)
    _delete(JOB_ID)
