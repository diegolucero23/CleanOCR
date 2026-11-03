"""
scripts/import_legacy_jobs.py

Record OCR jobs that were processed before the job database existed (Set B).

Their results live only in workspaces/{job_id}/ and Redis, so they never show
in Job History. Because the database is the source of truth for upload cache
hits, re-uploading one of those PDFs would otherwise pay for OCR again.

Usage (from the repo root, with the same DATABASE_URL/REDIS_URL as the app):
    python -m scripts.import_legacy_jobs --dry-run          # list candidates
    python -m scripts.import_legacy_jobs JOB_ID [JOB_ID...]  # import specific jobs
    python -m scripts.import_legacy_jobs --all              # import every candidate

Candidates are Redis cache:{file_hash} entries whose job has no DB record and
whose workspace holds output/full_extracted_content.md. Importing is
idempotent: existing records are never modified.
"""

import argparse
import json
import logging
import os
import sys
import time

logger = logging.getLogger("import_legacy_jobs")


def _decode(value):
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _int(value):
    try:
        return int(float(_decode(value)))
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(_decode(value))
    except (TypeError, ValueError):
        return None


def find_file_hash(redis_client, job_id: str):
    """Return the file hash whose cache:{hash} entry points at job_id, if any."""
    for key in redis_client.scan_iter(match="cache:*"):
        key = _decode(key)
        if key.count(":") != 1:
            continue
        if _decode(redis_client.get(key)) == job_id:
            return key.split(":", 1)[1]
    return None


def find_candidates(db, redis_client, workspaces_dir: str):
    """Job IDs referenced by Redis file-hash entries that have no DB record but have extracted markdown."""
    from app.db.models import JobModel

    found = []
    for key in redis_client.scan_iter(match="cache:*"):
        key = _decode(key)
        if key.count(":") != 1:
            continue
        job_id = _decode(redis_client.get(key))
        if not job_id or job_id in found or db.get(JobModel, job_id) is not None:
            continue
        if os.path.isfile(os.path.join(workspaces_dir, job_id, "output", "full_extracted_content.md")):
            found.append(job_id)
    return found


def import_legacy_job(db, job_id: str, workspaces_dir: str, redis_client, dry_run: bool = False) -> bool:
    """Create JobModel, JobMetadataModel and JobResultModel rows for one legacy job.

    Returns True if the job was (or, with dry_run, would be) imported; False if it
    already has a record or its workspace has no extracted markdown.
    """
    from app.core import config
    from app.db.models import JobMetadataModel, JobModel, JobResultModel

    if db.get(JobModel, job_id) is not None:
        logger.info("Skip %s: already recorded", job_id)
        return False

    workspace = os.path.join(workspaces_dir, job_id)
    markdown_path = os.path.join(workspace, "output", "full_extracted_content.md")
    if not os.path.isfile(markdown_path):
        logger.warning("Skip %s: no output/full_extracted_content.md in %s", job_id, workspace)
        return False

    ws_meta = {}
    meta_path = os.path.join(workspace, "metadata.json")
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            ws_meta = json.load(fh) or {}
    with open(markdown_path, encoding="utf-8") as fh:
        markdown = fh.read()

    status = _decode(redis_client.get(f"cache:{job_id}:status")) or "completed"
    total_pages = _int(redis_client.get(f"cache:{job_id}:total_pages"))
    processed = _int(redis_client.get(f"cache:{job_id}:completed_pages"))
    end_time = _float(redis_client.get(f"cache:{job_id}:end_time"))
    upload_time = _float(redis_client.get(f"cache:{job_id}:upload_time")) or end_time or time.time()
    pdf_path = os.path.join(config.UPLOAD_DIR, f"{job_id}.pdf")
    file_size = _int(redis_client.get(f"cache:{job_id}:file_size")) or (
        os.path.getsize(pdf_path) if os.path.isfile(pdf_path) else 0
    )
    filename = ws_meta.get("original_filename") or f"{job_id}.pdf"

    if dry_run:
        logger.info("Would import %s: %s (%s, %s pages, %d chars of markdown)",
                    job_id, filename, status, total_pages, len(markdown))
        return True

    db.add(JobModel(
        id=job_id,
        status=status,
        file_hash=find_file_hash(redis_client, job_id) or f"legacy-{job_id}",
        original_filename=filename,
        file_size=file_size,
        total_pages=total_pages,
        processed_pages=processed if processed is not None else (total_pages or 0),
        model_name=config.MODEL_NAME,
        upload_time=upload_time,
        end_time=end_time,
        duration_seconds=round(end_time - upload_time, 2) if end_time and upload_time <= end_time else None,
    ))
    db.add(JobMetadataModel(
        job_id=job_id,
        title=ws_meta.get("title"),
        volume=ws_meta.get("volume"),
        issue=ws_meta.get("issue"),
        publication_date=ws_meta.get("date"),
        skip_metadata=bool(ws_meta.get("skip_metadata", False)),
    ))
    db.add(JobResultModel(job_id=job_id, markdown_text=markdown, total_words=len(markdown.split())))
    db.flush()
    logger.info("Imported %s: %s (%s, %s pages)", job_id, filename, status, total_pages)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job_ids", nargs="*", help="Job IDs to import (default: list candidates only)")
    parser.add_argument("--all", action="store_true", help="Import every candidate found in Redis")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported; write nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    import redis

    from app.core import config
    from app.db.database import get_db_context, init_db
    import app.db.models  # noqa: F401  (register tables)

    init_db()
    redis_client = redis.Redis.from_url(config.REDIS_URL)
    with get_db_context() as db:
        job_ids = args.job_ids or find_candidates(db, redis_client, config.WORKSPACES_DIR)
        if not job_ids:
            logger.info("No legacy jobs to import.")
            return 0
        if not args.job_ids and not args.all and not args.dry_run:
            logger.info("Candidates (pass IDs or --all to import): %s", ", ".join(job_ids))
            return 0
        imported = sum(import_legacy_job(db, j, config.WORKSPACES_DIR, redis_client, dry_run=args.dry_run)
                       for j in job_ids)
    logger.info("%s %d of %d job(s).", "Would import" if args.dry_run else "Imported", imported, len(job_ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
