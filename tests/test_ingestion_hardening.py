"""
Tests for ingestion hardening against hostile/degraded inputs:
  - decompression-bomb guard: PDF pages with huge MediaBoxes are rejected
    before poppler rasterizes them (MAX_PAGE_PIXELS)
  - corrupt/truncated PDFs fail gracefully (empty result, no exception)
  - job ids from the URL are validated as UUIDs before being joined into
    workspace paths (/status, /stream path-traversal guard)
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.server import app
from app.core import config
from app.services import pdf_converter

client = TestClient(app)


def _write_pdf(path, page_boxes):
    """Write a minimal valid PDF with one page per (width, height) pts box."""
    objs = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids ["
        + " ".join(f"{3 + i} 0 R" for i in range(len(page_boxes)))
        + f"] /Count {len(page_boxes)} >>\nendobj\n",
    ]
    for i, (w, h) in enumerate(page_boxes):
        objs.append(
            f"{3 + i} 0 obj\n<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {w} {h}] >>\nendobj\n"
        )
    pdf = "%PDF-1.4\n"
    offsets = []
    for obj in objs:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n"
    pdf += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    )
    path.write_bytes(pdf.encode())
    return str(path)


# ---------------------------------------------------------------------------
# Decompression-bomb guard
# ---------------------------------------------------------------------------

def test_oversized_page_detected(tmp_path):
    # Page 2 declares a 14000x14000 pts MediaBox: ~58000x58000 px at 300 DPI.
    pdf_path = _write_pdf(tmp_path / "bomb.pdf", [(612, 792), (14000, 14000)])
    from pdf2image import pdfinfo_from_path

    info = pdfinfo_from_path(pdf_path, first_page=1, last_page=config.MAX_PDF_PAGES)
    assert pdf_converter.find_oversized_pages(info, config.PDF_RENDER_DPI) == [2]


def test_normal_pages_pass_size_check(tmp_path):
    pdf_path = _write_pdf(tmp_path / "ok.pdf", [(612, 792), (1224, 1584)])
    from pdf2image import pdfinfo_from_path

    info = pdfinfo_from_path(pdf_path, first_page=1, last_page=config.MAX_PDF_PAGES)
    assert pdf_converter.find_oversized_pages(info, config.PDF_RENDER_DPI) == []


def test_size_check_fails_closed_without_page_sizes():
    # A pdfinfo dict with no per-page entries (unexpected poppler output)
    # must raise rather than silently approving the file.
    with pytest.raises(ValueError):
        pdf_converter.find_oversized_pages({"Pages": 3}, config.PDF_RENDER_DPI)


def test_convert_refuses_bomb_pdf(tmp_path):
    pdf_path = _write_pdf(tmp_path / "bomb.pdf", [(612, 792), (14000, 14000)])
    generated = pdf_converter.convert_pdf_in_chunks(pdf_path, str(tmp_path / "out"))
    assert generated == []


# ---------------------------------------------------------------------------
# Malformed inputs fail gracefully
# ---------------------------------------------------------------------------

def test_convert_handles_corrupt_pdf(tmp_path):
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"%PDF-1.4\nthis is not really a pdf")
    generated = pdf_converter.convert_pdf_in_chunks(str(bad), str(tmp_path / "out"))
    assert generated == []


def test_convert_handles_truncated_pdf(tmp_path):
    real = _write_pdf(tmp_path / "real.pdf", [(612, 792)])
    truncated = tmp_path / "truncated.pdf"
    truncated.write_bytes(open(real, "rb").read()[:80])
    generated = pdf_converter.convert_pdf_in_chunks(str(truncated), str(tmp_path / "out"))
    assert generated == []


# ---------------------------------------------------------------------------
# job_id validation (/status and /stream path-traversal guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "not-a-uuid",
    "page_001.json",
    "..output",
])
def test_status_rejects_non_uuid_job_id(bad_id):
    response = client.get(f"/status/{bad_id}")
    assert response.status_code == 400
    assert "Invalid job id" in response.json()["detail"]


@pytest.mark.parametrize("path", [
    "/status/..%2F..%2Fetc",
    "/status/%2e%2e%2fuploads",
    "/stream/..%2F..%2Fworkspaces",
])
def test_encoded_traversal_never_reaches_workspace(path):
    # The current Starlette router 404s multi-segment decoded paths before
    # they reach the handler; the UUID validator returns 400 if routing
    # behavior ever changes. Either way the request must not succeed.
    response = client.get(path)
    assert response.status_code in (400, 404)


def test_stream_rejects_non_uuid_job_id():
    response = client.get("/stream/not-a-uuid")
    assert response.status_code == 400


def test_status_accepts_valid_uuid():
    job_id = str(uuid.uuid4())
    with patch("app.api.server.redis_client") as mock_redis, \
         patch("app.api.server.AsyncResult") as mock_result:
        mock_redis.get.return_value = None
        mock_result.return_value.state = "PENDING"
        response = client.get(f"/status/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
