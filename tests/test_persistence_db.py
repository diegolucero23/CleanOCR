import os
import time
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, init_db, get_db
from app.db.models import JobModel, JobMetadataModel, JobResultModel
from app.api.server import app
from app.core import config
from app.workers.celery_worker import cleanup_old_workspaces


@pytest.fixture
def test_db(tmp_path):
    """Fixture providing an isolated SQLite database in a temporary directory."""
    db_file = tmp_path / "test_cleanocr.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal, engine, override_get_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_redis():
    """Mock Redis client to avoid network socket errors during unit tests."""
    m = MagicMock()
    m.get.return_value = None
    m.exists.return_value = False
    m.pipeline.return_value = m
    m.execute.return_value = [None, None, 0, None]
    with patch("app.api.server.redis_client", m), \
         patch("app.core.security.redis_client", m):
        yield m


@pytest.fixture
def client(test_db, mock_redis, tmp_path):
    with patch("app.api.server.config.UPLOAD_DIR", str(tmp_path / "uploads")):
        return TestClient(app)


def test_models_and_schema_initialization(test_db):
    """Verify that models and database tables initialize cleanly."""
    TestingSessionLocal, engine, _ = test_db
    table_names = Base.metadata.tables.keys()
    assert "jobs" in table_names
    assert "job_metadata" in table_names
    assert "job_results" in table_names


def test_job_crud_lifecycle_and_cascade(test_db):
    """Test full CRUD lifecycle and cascade deletion for Job, Metadata, and Results."""
    TestingSessionLocal, _, _ = test_db
    db = TestingSessionLocal()
    job_id = str(uuid.uuid4())

    # 1. Create Job with Metadata
    job = JobModel(
        id=job_id,
        status="queued",
        file_hash="test_sha256_hash",
        original_filename="advocate_oct_1834.pdf",
        file_size=1048576,
        total_pages=16,
        model_name="gemini-3.1-flash-lite",
        upload_time=time.time(),
    )
    metadata = JobMetadataModel(
        job_id=job_id,
        title="Latter Day Saints' Messenger and Advocate",
        volume="1",
        issue="1",
        publication_date="1834-10",
    )
    db.add(job)
    db.add(metadata)
    db.commit()

    # 2. Query Job
    saved_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one()
    assert saved_job.status == "queued"
    assert saved_job.citation_metadata.title == "Latter Day Saints' Messenger and Advocate"
    assert saved_job.citation_metadata.volume == "1"

    # 3. Attach Result
    result = JobResultModel(
        job_id=job_id,
        markdown_text="# Latter Day Saints' Messenger and Advocate\n\nFull transcript...",
        total_words=450,
        confidence_score=0.98,
        statistics_json='{"processing_time": 42.5}',
    )
    saved_job.status = "completed"
    saved_job.end_time = time.time()
    saved_job.duration_seconds = 42.5
    saved_job.complexity = 3.2
    db.add(result)
    db.commit()

    reloaded_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one()
    assert reloaded_job.status == "completed"
    assert reloaded_job.result.total_words == 450
    assert "Messenger and Advocate" in reloaded_job.result.markdown_text

    # 4. Cascade Deletion
    db.delete(reloaded_job)
    db.commit()

    assert db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none() is None
    assert db.execute(select(JobMetadataModel).where(JobMetadataModel.job_id == job_id)).scalar_one_or_none() is None
    assert db.execute(select(JobResultModel).where(JobResultModel.job_id == job_id)).scalar_one_or_none() is None
    db.close()


@patch("app.api.server.run_ocr_pipeline")
@patch("app.api.server.validate_file_type", return_value=True)
@patch("app.api.server.get_pdf_page_count", return_value=5)
def test_upload_persists_to_database(mock_pages, mock_val, mock_celery, client, test_db, tmp_path):
    """Test that POST /upload creates persistent JobModel and JobMetadataModel rows."""
    TestingSessionLocal, _, _ = test_db
    mock_task = MagicMock()
    mock_task.id = "mock-task-id"
    mock_celery.apply_async.return_value = mock_task

    pdf_content = b"%PDF-1.4 test document content"
    files = {"file": ("test_doc.pdf", pdf_content, "application/pdf")}
    data = {
        "title": "Evening and Morning Star",
        "volume": "Vol_001",
        "issue": "Issue_001",
        "date": "1832-06",
        "skip_metadata": False,
    }

    response = client.post("/upload", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    job_id = res_data["job_id"]

    db = TestingSessionLocal()
    persisted_job = db.execute(select(JobModel).where(JobModel.id == job_id)).scalar_one_or_none()
    assert persisted_job is not None
    assert persisted_job.status == "queued"
    assert persisted_job.original_filename == "test_doc.pdf"
    assert persisted_job.total_pages == 5
    assert persisted_job.citation_metadata.title == "Evening and Morning Star"
    assert persisted_job.citation_metadata.volume == "Vol_001"
    db.close()


def test_get_jobs_pagination_and_filtering(client, test_db):
    """Test GET /jobs pagination, status filtering, and search functionality."""
    TestingSessionLocal, _, _ = test_db
    db = TestingSessionLocal()

    # Seed 5 test jobs
    for i in range(1, 6):
        status = "completed" if i <= 3 else "failed"
        job = JobModel(
            id=f"00000000-0000-0000-0000-00000000000{i}",
            status=status,
            file_hash=f"hash_{i}",
            original_filename=f"document_volume_{i:03d}.pdf",
            file_size=1000 * i,
            total_pages=10 * i,
            processed_pages=10 * i if status == "completed" else 2,
            model_name="gemini-3.1-flash-lite",
            upload_time=1700000000.0 + (i * 100),
        )
        meta = JobMetadataModel(
            job_id=job.id,
            title="Messenger and Advocate" if i % 2 == 1 else "Times and Seasons",
            volume=f"Vol_{i:03d}",
            issue="Issue_001",
            publication_date="1835-01",
        )
        db.add(job)
        db.add(meta)
    db.commit()
    db.close()

    # 1. Test pagination: Page 1 with limit 2
    res = client.get("/jobs?page=1&limit=2")
    assert res.status_code == 200
    p1_data = res.json()
    assert p1_data["total"] == 5
    assert p1_data["page"] == 1
    assert p1_data["limit"] == 2
    assert p1_data["total_pages"] == 3
    assert len(p1_data["items"]) == 2

    # 2. Test status filtering: status=completed
    res_completed = client.get("/jobs?status=completed")
    assert res_completed.status_code == 200
    comp_data = res_completed.json()
    assert comp_data["total"] == 3
    assert all(item["status"] == "completed" for item in comp_data["items"])

    # 3. Test status filtering: status=failed
    res_failed = client.get("/jobs?status=failed")
    assert res_failed.status_code == 200
    fail_data = res_failed.json()
    assert fail_data["total"] == 2
    assert all(item["status"] == "failed" for item in fail_data["items"])

    # 4. Test text search on title
    res_search = client.get("/jobs?search=Messenger")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] == 3
    assert all("Messenger" in item["metadata"]["title"] for item in search_data["items"])


def test_get_job_by_id_and_not_found(client, test_db):
    """Test GET /jobs/{job_id} returns full record with markdown result, and 404 for unknown."""
    TestingSessionLocal, _, _ = test_db
    db = TestingSessionLocal()
    job_id = str(uuid.uuid4())

    job = JobModel(
        id=job_id,
        status="completed",
        file_hash="hash_single",
        original_filename="single_test.pdf",
        file_size=2048,
        total_pages=2,
        processed_pages=2,
        model_name="gemini-3.1-flash-lite",
        upload_time=time.time(),
        end_time=time.time() + 10,
        duration_seconds=10.0,
        complexity=1.5,
    )
    meta = JobMetadataModel(job_id=job_id, title="Single Volume Test", volume="Vol_001", issue="Issue_001")
    result = JobResultModel(
        job_id=job_id,
        markdown_text="# Header\n\nExtracted content.",
        total_words=25,
        confidence_score=0.99,
        statistics_json='{"pages": 2}',
    )
    db.add(job)
    db.add(meta)
    db.add(result)
    db.commit()
    db.close()

    # Success
    res = client.get(f"/jobs/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert data["result"]["markdown_text"] == "# Header\n\nExtracted content."
    assert data["result"]["total_words"] == 25

    # 404 Not Found with structured error
    res_404 = client.get(f"/jobs/{uuid.uuid4()}")
    assert res_404.status_code == 404
    err_data = res_404.json()
    assert "error" in err_data
    assert err_data["error"]["code"] == "JOB_NOT_FOUND"


def test_status_endpoint_database_fallback(client, test_db):
    """Test that GET /status/{job_id} gracefully falls back to DB when Redis cache is absent."""
    TestingSessionLocal, _, _ = test_db
    db = TestingSessionLocal()
    job_id = str(uuid.uuid4())

    job = JobModel(
        id=job_id,
        status="completed",
        file_hash="hash_fallback",
        original_filename="fallback_doc.pdf",
        file_size=5000,
        total_pages=4,
        processed_pages=4,
        model_name="gemini-3.1-flash-lite",
        upload_time=1700000000.0,
        end_time=1700000050.0,
        duration_seconds=50.0,
        complexity=2.5,
    )
    result = JobResultModel(
        job_id=job_id,
        markdown_text="Markdown recovered directly from the database fallback.",
        total_words=50,
        confidence_score=0.95,
    )
    db.add(job)
    db.add(result)
    db.commit()
    db.close()

    # Mock Redis client to simulate an evicted or restarted Redis instance (returning None for everything)
    with patch("app.api.server.redis_client.get", return_value=None):
        res = client.get(f"/status/{job_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert "Markdown recovered directly from the database fallback." in data.get("markdown", "")


def test_workspace_cleanup_preserves_database(test_db, tmp_path):
    """Verify that cleanup_old_workspaces purges files on disk but preserves database rows."""
    TestingSessionLocal, _, _ = test_db
    db = TestingSessionLocal()
    old_job_id = str(uuid.uuid4())

    # Create DB entry for an old job
    old_time = time.time() - (30 * 3600)  # 30 hours old (TTL is 24h)
    job = JobModel(
        id=old_job_id,
        status="completed",
        file_hash="hash_old",
        original_filename="ancient_publication.pdf",
        file_size=1024,
        upload_time=old_time,
        end_time=old_time + 60,
    )
    result = JobResultModel(
        job_id=old_job_id,
        markdown_text="Permanent archival text stored in SQL.",
        total_words=100,
    )
    db.add(job)
    db.add(result)
    db.commit()
    db.close()

    # Create dummy workspace and upload files
    ws_dir = tmp_path / "workspaces" / old_job_id
    ws_dir.mkdir(parents=True)
    (ws_dir / "full_extracted_content.md").write_text("Temp disk content")
    upload_file = tmp_path / "uploads" / f"{old_job_id}.pdf"
    upload_file.parent.mkdir(parents=True, exist_ok=True)
    upload_file.write_bytes(b"%PDF-1.4 dummy")

    with patch.object(config, "WORKSPACES_DIR", str(tmp_path / "workspaces")), \
         patch.object(config, "UPLOAD_DIR", str(tmp_path / "uploads")), \
         patch.object(config, "WORKSPACE_TTL_HOURS", 24), \
         patch("app.workers.celery_worker.redis.Redis.from_url") as mock_r:
        
        mock_r.return_value.get.return_value = str(old_time).encode("utf-8")
        mock_r.return_value.keys.return_value = []

        cleanup_old_workspaces()

        # Workspace on disk should be removed
        assert not ws_dir.exists()
        assert not upload_file.exists()

        # Database rows MUST still exist
        check_db = TestingSessionLocal()
        persisted = check_db.execute(select(JobModel).where(JobModel.id == old_job_id)).scalar_one_or_none()
        assert persisted is not None
        assert persisted.result.markdown_text == "Permanent archival text stored in SQL."
        check_db.close()


def test_adversarial_query_parameters(client, test_db):
    """Test adversarial query parameters: invalid pagination bounds, bad sort orders, and SQL injection strings."""
    # 1. Negative or zero page
    res_page_zero = client.get("/jobs?page=0")
    assert res_page_zero.status_code == 422

    # 2. Limit exceeding max allowed ceiling (100)
    res_huge_limit = client.get("/jobs?limit=500")
    assert res_huge_limit.status_code == 422

    # 3. Invalid sort order enum
    res_bad_sort = client.get("/jobs?sort_order=random")
    assert res_bad_sort.status_code == 422

    # 4. SQL Injection payload in search string
    injection_payload = "'; DROP TABLE jobs; --"
    res_injection = client.get(f"/jobs?search={injection_payload}")
    assert res_injection.status_code == 200
    data = res_injection.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0
