"""
tests/test_job_serialization.py

SQLite drops tzinfo, so created_at comes back naive even though the column is
timezone-aware and holds UTC. Serialized without an offset, browsers parse it
as LOCAL time and Job History shows UTC clock times (e.g. 08:18 PM for a
1:18 PM upload in UTC-7). created_at must always carry an explicit offset.
"""

from datetime import datetime, timedelta, timezone

from app.db.models import JobModel


def _job(created_at):
    return JobModel(id="ser-1", status="completed", file_hash="h", original_filename="a.pdf",
                    file_size=1, total_pages=1, processed_pages=1, model_name="m",
                    upload_time=1.0, created_at=created_at)


def test_naive_created_at_is_serialized_as_utc():
    out = _job(datetime(2026, 11, 3, 20, 18, 27)).to_summary_dict()["created_at"]
    assert out == "2026-11-03T20:18:27+00:00"
    assert datetime.fromisoformat(out).utcoffset() == timedelta(0)


def test_aware_created_at_keeps_its_offset():
    pdt = timezone(timedelta(hours=-7))
    out = _job(datetime(2026, 11, 3, 13, 18, 27, tzinfo=pdt)).to_summary_dict()["created_at"]
    assert datetime.fromisoformat(out) == datetime(2026, 11, 3, 20, 18, 27, tzinfo=timezone.utc)
