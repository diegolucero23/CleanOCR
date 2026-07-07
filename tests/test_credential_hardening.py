"""
Tests for credential hardening: secret redaction (app/core/secrets.py) and
the Gemini call budget guard (app/core/cost_guard.py).
"""
import logging

import pytest
import redis as redis_lib

from app.core import config, cost_guard
from app.core.secrets import REDACTED, SecretRedactingFilter, redact

FAKE_KEY = "fake-secret-key-value-1234567890"
KEY_SHAPED = "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r"  # AIza + 35 chars


# ---------------------------------------------------------------------------
# redact()
# ---------------------------------------------------------------------------

def test_redact_removes_configured_key(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", FAKE_KEY)
    out = redact(f"ClientError: 400 invalid key {FAKE_KEY} rejected")
    assert FAKE_KEY not in out
    assert REDACTED in out


def test_redact_removes_key_shaped_strings_even_if_not_configured(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", FAKE_KEY)
    out = redact(f"url was ?key={KEY_SHAPED}&alt=json")
    assert KEY_SHAPED not in out
    assert REDACTED in out


def test_redact_accepts_exceptions_and_leaves_mock_values(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "MOCK_KEY_DO_NOT_CHARGE")
    out = redact(ValueError("mock mode MOCK_KEY_DO_NOT_CHARGE active"))
    assert "MOCK_KEY_DO_NOT_CHARGE" in out


def test_status_endpoint_redacts_celery_failure_message(monkeypatch):
    """The FAILURE branch of /status reflects the exception Celery stored in
    its result backend; that string must pass through redact() first."""
    import uuid
    from unittest.mock import patch

    from fastapi.testclient import TestClient
    from app.api.server import app

    monkeypatch.setattr(config, "GOOGLE_API_KEY", FAKE_KEY)
    client = TestClient(app)
    job_id = str(uuid.uuid4())

    with patch("app.api.server.redis_client") as mock_redis, \
         patch("app.api.server.AsyncResult") as mock_result:
        mock_redis.get.return_value = None  # no status key in Redis
        mock_result.return_value.state = "FAILURE"
        mock_result.return_value.info = RuntimeError(
            f"auth rejected for key {KEY_SHAPED}"
        )
        response = client.get(f"/status/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert KEY_SHAPED not in body["message"]
    assert REDACTED in body["message"]


# ---------------------------------------------------------------------------
# SecretRedactingFilter
# ---------------------------------------------------------------------------

def test_logging_filter_scrubs_message_args_and_extra(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", FAKE_KEY)
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1,
        "call failed: %s", (f"key {FAKE_KEY} invalid",), None,
    )
    record.error = f"extra field holding {FAKE_KEY}"

    assert SecretRedactingFilter().filter(record) is True
    assert FAKE_KEY not in record.getMessage()
    assert FAKE_KEY not in record.error
    assert REDACTED in record.getMessage()


def test_logging_filter_scrubs_exception_traceback(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", FAKE_KEY)
    try:
        raise RuntimeError(f"auth rejected for {FAKE_KEY}")
    except RuntimeError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "boom", None, exc_info,
    )
    SecretRedactingFilter().filter(record)
    assert record.exc_text and FAKE_KEY not in record.exc_text
    assert logging.Formatter().format(record).count(FAKE_KEY) == 0


# ---------------------------------------------------------------------------
# cost_guard
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_cost_guard(monkeypatch):
    cost_guard.reset_run_counter()
    monkeypatch.setattr(cost_guard, "_redis_client", None)
    monkeypatch.setattr(cost_guard, "_redis_disabled", False)
    yield
    cost_guard.reset_run_counter()


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.ttls = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, ttl):
        self.ttls[key] = ttl


class DeadRedis:
    def incr(self, key):
        raise redis_lib.ConnectionError("connection refused")


def test_run_cap_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_RUN_CALL_CAP", 3)
    monkeypatch.setattr(config, "GEMINI_DAILY_CALL_CAP", 0)
    for _ in range(3):
        cost_guard.register_call()
    with pytest.raises(cost_guard.BudgetExceededError, match="Per-run"):
        cost_guard.register_call()


def test_daily_cap_blocks_after_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(config, "GEMINI_RUN_CALL_CAP", 0)
    monkeypatch.setattr(config, "GEMINI_DAILY_CALL_CAP", 2)
    monkeypatch.setattr(cost_guard, "_get_redis", lambda: fake)
    cost_guard.register_call()
    cost_guard.register_call()
    with pytest.raises(cost_guard.BudgetExceededError, match="Daily"):
        cost_guard.register_call()
    # Counter got a TTL so it expires instead of accumulating forever.
    assert list(fake.ttls.values()) == [cost_guard._DAILY_KEY_TTL_SECONDS]


def test_caps_of_zero_disable_the_guard(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_RUN_CALL_CAP", 0)
    monkeypatch.setattr(config, "GEMINI_DAILY_CALL_CAP", 0)
    for _ in range(50):
        cost_guard.register_call()  # must not raise, must not touch Redis


def test_daily_cap_fails_open_when_redis_down(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_RUN_CALL_CAP", 0)
    monkeypatch.setattr(config, "GEMINI_DAILY_CALL_CAP", 1)
    monkeypatch.setattr(cost_guard, "_get_redis", lambda: DeadRedis())
    cost_guard.register_call()
    cost_guard.register_call()  # would exceed cap, but Redis is down → allowed
    assert cost_guard._redis_disabled is True


def test_provider_checks_budget_before_touching_the_api(monkeypatch):
    from app.services.google_vision import GoogleVisionProvider

    api_calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            api_calls.append(kwargs)

    class FakeClient:
        models = FakeModels()

    provider = GoogleVisionProvider.__new__(GoogleVisionProvider)
    provider.client = FakeClient()

    def deny():
        raise cost_guard.BudgetExceededError("cap reached")

    monkeypatch.setattr(
        "app.services.google_vision.cost_guard.register_call", deny
    )
    with pytest.raises(cost_guard.BudgetExceededError):
        provider.generate_content(contents=["prompt"], config=None)
    assert api_calls == []


def test_provider_registers_each_call(monkeypatch):
    from app.services.google_vision import GoogleVisionProvider

    class FakeResponse:
        text = "ok"

    class FakeModels:
        def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    provider = GoogleVisionProvider.__new__(GoogleVisionProvider)
    provider.client = FakeClient()

    registered = []
    monkeypatch.setattr(
        "app.services.google_vision.cost_guard.register_call",
        lambda: registered.append(1),
    )
    assert provider.generate_content(contents=["prompt"], config=None) == "ok"
    assert len(registered) == 1
