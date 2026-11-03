"""
tests/test_structured_logging.py

Validates the JSON log formatters for the API and the Celery worker.

Coverage:
  - Every log line carries a non-null, ISO-8601 "timestamp" field
  - Every log line carries the level name in a non-null "level" field
  - Message, module, and funcName fields are still emitted

Regression for RedTeam Campaign 2 (tests/redteam_artifacts/campaign_2_flooding.md),
which observed {"timestamp": null, "level": null} in worker logs.
"""

import json
import logging
from datetime import datetime

import pytest

import app.api.server  # noqa: F401  (configures the "cleanocr_api" logger)
import app.workers.celery_worker  # noqa: F401  (configures "cleanocr_worker")


def _format_with(logger_name: str, level: int, message: str) -> dict:
    logger = logging.getLogger(logger_name)
    assert logger.handlers, f"{logger_name} has no handlers configured"
    formatter = logger.handlers[0].formatter
    record = logger.makeRecord(logger_name, level, __file__, 1, message, None, None, func="probe")
    return json.loads(formatter.format(record))


@pytest.mark.parametrize("logger_name", ["cleanocr_api", "cleanocr_worker"])
def test_log_line_has_iso_timestamp(logger_name):
    payload = _format_with(logger_name, logging.INFO, "probe message")
    assert payload.get("timestamp"), f"{logger_name} emitted null timestamp: {payload}"
    datetime.fromisoformat(payload["timestamp"])


@pytest.mark.parametrize(
    "logger_name,level,expected",
    [
        ("cleanocr_api", logging.INFO, "INFO"),
        ("cleanocr_api", logging.ERROR, "ERROR"),
        ("cleanocr_worker", logging.WARNING, "WARNING"),
    ],
)
def test_log_line_has_level_name(logger_name, level, expected):
    payload = _format_with(logger_name, level, "probe message")
    assert payload.get("level") == expected, f"{logger_name} emitted bad level: {payload}"


@pytest.mark.parametrize("logger_name", ["cleanocr_api", "cleanocr_worker"])
def test_log_line_keeps_context_fields(logger_name):
    payload = _format_with(logger_name, logging.INFO, "probe message")
    assert payload["message"] == "probe message"
    assert payload["funcName"] == "probe"
    assert "module" in payload
