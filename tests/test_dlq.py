"""
tests/test_dlq.py

Validates the Dead Letter Queue (DLQ) implementation for CleanOCR Celery workers.

Coverage:
  Queue configuration
    - 'default' and 'dlq' queues are defined
    - task_default_queue is 'default'
    - task_acks_late is True  (at-least-once delivery)
    - task_reject_on_worker_lost is True  (re-queue on worker crash)

  Task retry configuration
    - ocr_page_task:        bind=True, max_retries >= 3
    - stitch_markdown_task: bind=True, max_retries >= 3

  DLQ signal handler (on_task_failure)
    - Pushes a JSON entry to the 'dlq:tasks' Redis list
    - Increments the 'dlq:total_failures' counter
    - Sets 'cache:{job_id}:status' = 'failed' in Redis
    - DLQ entry contains: task_id, task_name, exception_type,
                          exception_message, args, failed_at

  Regression — success path preserved
    - ocr_page_task still increments 'cache:{job_id}:completed_pages' on success
    - stitch_markdown_task still sets 'cache:{job_id}:end_time' on success
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_redis():
    mock_redis = MagicMock()
    mock_redis.incr.return_value = 1
    return mock_redis


# ===========================================================================
# 1. Queue & reliability configuration
# ===========================================================================

class TestCeleryQueueConfiguration:
    """Celery app must declare both 'default' and 'dlq' queues."""

    def test_default_and_dlq_queues_declared(self):
        from app.workers.celery_worker import celery_app
        queue_names = {q.name for q in celery_app.conf.task_queues}
        assert "default" in queue_names, "'default' queue not found in task_queues"
        assert "dlq" in queue_names, "'dlq' queue not found in task_queues"

    def test_task_default_queue_is_default(self):
        from app.workers.celery_worker import celery_app
        assert celery_app.conf.task_default_queue == "default"

    def test_acks_late_is_true(self):
        """At-least-once delivery: tasks are ACK'd only after successful completion."""
        from app.workers.celery_worker import celery_app
        assert celery_app.conf.task_acks_late is True

    def test_reject_on_worker_lost_is_true(self):
        """Tasks are re-queued if the worker process crashes mid-execution."""
        from app.workers.celery_worker import celery_app
        assert celery_app.conf.task_reject_on_worker_lost is True


# ===========================================================================
# 2. Task retry configuration
# ===========================================================================

class TestTaskRetryConfiguration:
    """All leaf tasks must be bound and have a max_retries ceiling."""

    def test_ocr_page_task_is_bound(self):
        from app.workers.celery_worker import ocr_page_task
        assert ocr_page_task.__bound__ is True, "ocr_page_task must use bind=True to call self.retry()"

    def test_ocr_page_task_has_max_retries_gte_3(self):
        from app.workers.celery_worker import ocr_page_task
        assert ocr_page_task.max_retries is not None
        assert ocr_page_task.max_retries >= 3

    def test_stitch_markdown_task_is_bound(self):
        from app.workers.celery_worker import stitch_markdown_task
        assert stitch_markdown_task.__bound__ is True, (
            "stitch_markdown_task must use bind=True to call self.retry()"
        )

    def test_stitch_markdown_task_has_max_retries_gte_3(self):
        from app.workers.celery_worker import stitch_markdown_task
        assert stitch_markdown_task.max_retries is not None
        assert stitch_markdown_task.max_retries >= 3


# ===========================================================================
# 3. DLQ signal handler — on_task_failure
# ===========================================================================

class TestOnTaskFailureSignalHandler:
    """
    on_task_failure is the @task_failure.connect handler.
    It must push a DLQ entry to Redis and update job status.
    """

    def _call_handler(self, mock_redis, task_name, task_id, exception, args, kwargs=None):
        """Helper: call on_task_failure with a patched Redis client."""
        from app.workers.celery_worker import on_task_failure

        mock_sender = MagicMock()
        mock_sender.name = task_name

        on_task_failure(
            sender=mock_sender,
            task_id=task_id,
            exception=exception,
            args=args,
            kwargs=kwargs or {},
            traceback=None,
            einfo=None,
        )

    def test_pushes_entry_to_dlq_tasks_list(self):
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="ocr_page_task",
                task_id="tid-001",
                exception=Exception("Gemini API unavailable"),
                args=["job-aaa", "page_001.png", "/in", "/out"],
            )

            assert mock_redis.rpush.called, "rpush must be called to add entry to DLQ list"
            list_name, raw_entry = mock_redis.rpush.call_args[0]
            assert list_name == "dlq:tasks"
            # Must be valid JSON
            entry = json.loads(raw_entry)
            assert entry is not None

    def test_dlq_entry_schema(self):
        """Entry must contain task_id, task_name, exception_type, exception_message, args, failed_at."""
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="ocr_page_task",
                task_id="tid-schema",
                exception=ValueError("bad OCR JSON"),
                args=["job-schema", "page_002.png", "/in", "/out"],
            )

            _, raw_entry = mock_redis.rpush.call_args[0]
            entry = json.loads(raw_entry)

            assert entry["task_id"] == "tid-schema"
            assert entry["task_name"] == "ocr_page_task"
            assert entry["exception_type"] == "ValueError"
            assert "bad OCR JSON" in entry["exception_message"]
            assert isinstance(entry["args"], list)
            assert "failed_at" in entry
            assert isinstance(entry["failed_at"], float)

    def test_increments_dlq_total_failures_counter(self):
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="stitch_markdown_task",
                task_id="tid-counter",
                exception=RuntimeError("stitch boom"),
                args=["job-counter"],
            )

            mock_redis.incr.assert_any_call("dlq:total_failures")

    def test_sets_job_status_to_failed_in_redis(self):
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="ocr_page_task",
                task_id="tid-status",
                exception=Exception("permanent failure"),
                args=["job-status-test", "page.png", "/in", "/out"],
            )

            mock_redis.set.assert_any_call("cache:job-status-test:status", "failed")

    def test_stitch_task_failure_also_updates_job_status(self):
        """stitch_markdown_task failures must also mark the job as failed."""
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="stitch_markdown_task",
                task_id="tid-stitch-fail",
                exception=IOError("disk full"),
                args=["job-stitch-fail"],
            )

            mock_redis.set.assert_any_call("cache:job-stitch-fail:status", "failed")

    def test_dlq_entry_args_are_serialised_as_list(self):
        """args tuple must be stored as a JSON list (tuples are not JSON-serialisable)."""
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            self._call_handler(
                mock_redis,
                task_name="ocr_page_task",
                task_id="tid-args",
                exception=Exception("err"),
                args=("job-args-test", "page.png", "/in", "/out"),  # tuple
            )

            _, raw_entry = mock_redis.rpush.call_args[0]
            entry = json.loads(raw_entry)
            assert isinstance(entry["args"], list)
            assert entry["args"][0] == "job-args-test"

    def test_handler_works_when_args_is_empty(self):
        """Handler must not raise if args is empty (e.g. run_ocr_pipeline kwargs-only call)."""
        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls:
            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            # Should not raise
            self._call_handler(
                mock_redis,
                task_name="run_ocr_pipeline",
                task_id="tid-noargs",
                exception=Exception("pipeline crash"),
                args=[],
            )

            assert mock_redis.rpush.called


# ===========================================================================
# 4. Regression — success paths must be unchanged
# ===========================================================================

class TestSuccessPathRegression:
    """
    Adding DLQ / retry logic must not break the happy path.
    These mirror the assertions from the original test_concurrency.py and
    test_stats.py to guard against regressions.
    """

    def test_ocr_page_task_increments_completed_pages_on_success(self):
        """On success, ocr_page_task must still call redis.incr('cache:{job_id}:completed_pages')."""
        with patch("app.workers.celery_worker.batch_ocr") as mock_batch, \
             patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls, \
             patch("app.workers.celery_worker.celery_app") as mock_celery_app:

            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis
            mock_celery_app.conf.broker_url = "redis://dummy:6379/0"
            mock_batch.process_single_image.return_value = None  # success

            from app.workers.celery_worker import ocr_page_task
            result = ocr_page_task("job-regr-ocr", "page_001.png", "/in", "/out")

            mock_redis.incr.assert_called_with("cache:job-regr-ocr:completed_pages")
            assert result == "page_001.png"

    def test_stitch_task_sets_end_time_and_status_on_success(self):
        """On success, stitch_markdown_task must still set end_time and 'completed' status."""
        import time as time_module
        FAKE_TIME = 1620000100.0

        with patch("app.workers.celery_worker.redis.Redis.from_url") as mock_redis_cls, \
             patch("app.workers.celery_worker.stitch_to_markdown.stitch_markdown"), \
             patch("app.workers.celery_worker.time.time", return_value=FAKE_TIME):

            mock_redis = _make_mock_redis()
            mock_redis_cls.return_value = mock_redis

            from app.workers.celery_worker import stitch_markdown_task
            result = stitch_markdown_task([], "job-regr-stitch", "/in", "/out", None, None)

            mock_redis.set.assert_any_call("cache:job-regr-stitch:end_time", FAKE_TIME)
            mock_redis.set.assert_any_call("cache:job-regr-stitch:status", "completed")
            assert result == "done"
