"""
Tests for ingestion-limit disclosure and bounded SSE streams:
  - GET /limits exposes the upload caps and streaming budgets pre-upload
  - /upload returns an 'expectations' block using the same budgets that
    /stream enforces
  - /stream closes with a final 'stream_timeout' event for job ids Redis
    has never seen, instead of streaming heartbeats forever
  - YAML frontmatter in the stitcher escapes user-supplied metadata
"""
import json
import os
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.api.server import app, compute_stream_timeout_seconds
from app.core import config

client = TestClient(app)


# ---------------------------------------------------------------------------
# Limits disclosure
# ---------------------------------------------------------------------------

def test_limits_endpoint_discloses_caps():
    response = client.get("/limits")
    assert response.status_code == 200
    data = response.json()
    assert data["max_upload_mb"] == config.MAX_UPLOAD_MB
    assert data["max_pdf_pages"] == config.MAX_PDF_PAGES
    assert data["max_page_pixels"] == config.MAX_PAGE_PIXELS
    assert data["render_dpi"] == config.PDF_RENDER_DPI
    assert data["accepted_types"] == ["application/pdf"]
    assert data["stream_page_budget_seconds"] == config.STREAM_PAGE_BUDGET_SECONDS


def test_upload_response_includes_expectations():
    with patch('app.api.server.redis_client') as mock_redis, \
         patch('app.api.server.validate_file_type', return_value=True), \
         patch('app.api.server.get_pdf_page_count', return_value=3), \
         patch('app.api.server.run_ocr_pipeline.apply_async'):
        mock_redis.get.return_value = None  # no cache hit
        files = {'file': ('dummy.pdf', b'fake pdf content', 'application/pdf')}
        response = client.post("/upload", files=files)

    assert response.status_code == 200
    expectations = response.json()["expectations"]
    expected_timeout = (
        config.STREAM_BASE_BUDGET_SECONDS + 3 * config.STREAM_PAGE_BUDGET_SECONDS
    )
    assert expectations["page_count"] == 3
    assert expectations["stream_timeout_seconds"] == expected_timeout
    assert expectations["estimated_max_processing_seconds"] == expected_timeout
    assert expectations["limits"]["max_pdf_pages"] == config.MAX_PDF_PAGES


def test_compute_stream_timeout_handles_missing_page_count():
    assert compute_stream_timeout_seconds(None) == config.STREAM_BASE_BUDGET_SECONDS
    assert compute_stream_timeout_seconds(0) == config.STREAM_BASE_BUDGET_SECONDS


# ---------------------------------------------------------------------------
# Bounded SSE stream
# ---------------------------------------------------------------------------

def test_stream_times_out_for_unknown_job():
    job_id = "11111111-2222-4333-8444-555555555555"
    with patch('app.api.server.redis_client') as mock_redis, \
         patch('app.api.server.AsyncResult') as mock_result, \
         patch.object(config, 'STREAM_UNKNOWN_JOB_TIMEOUT', 0):
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = 0  # Redis has never seen this job
        mock_result.return_value.state = "PENDING"

        response = client.get(f"/stream/{job_id}")

    assert response.status_code == 200
    events = [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["status"] == "stream_timeout"
    assert "may not exist" in events[-1]["message"]


def test_stream_timeout_leaves_job_untouched():
    """Hitting the stream bound must not write a failed status to Redis."""
    job_id = "11111111-2222-4333-8444-555555555555"
    with patch('app.api.server.redis_client') as mock_redis, \
         patch('app.api.server.AsyncResult') as mock_result, \
         patch.object(config, 'STREAM_UNKNOWN_JOB_TIMEOUT', 0):
        mock_redis.get.return_value = None
        mock_redis.exists.return_value = 0
        mock_result.return_value.state = "PENDING"

        client.get(f"/stream/{job_id}")

        mock_redis.set.assert_not_called()


# ---------------------------------------------------------------------------
# YAML frontmatter escaping
# ---------------------------------------------------------------------------

def test_frontmatter_escapes_hostile_metadata(tmp_path):
    from app.services import stitcher

    input_dir = tmp_path / "ocr_json"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "page_001.json").write_text(json.dumps({
        "markdown_content": "Some text.",
        "metadata": {"volume": "1", "issue": "1", "page_number": "1"},
    }), encoding="utf-8")

    hostile_title = 'Breaking: "quotes" and \\backslashes\nand a newline'
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text(json.dumps({
        "title": hostile_title,
        "date": '2026-07-05" injected: true',
        "volume": "1",
        "issue": "1",
        "skip_metadata": False,
    }), encoding="utf-8")

    stitcher.stitch_markdown(str(input_dir), str(output_dir), str(metadata_file))

    content = (output_dir / "full_extracted_content.md").read_text(encoding="utf-8")
    assert content.startswith("---\n")
    frontmatter_block = content.split("---\n")[1]
    parsed = yaml.safe_load(frontmatter_block)
    assert parsed["title"] == hostile_title
    assert parsed["date"] == '2026-07-05" injected: true'
    assert "injected" not in parsed  # the quote didn't create a new key
