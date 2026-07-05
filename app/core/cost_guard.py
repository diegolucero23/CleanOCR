"""
Gemini API call budget guard.

Every real Gemini request (GoogleVisionProvider._call) registers here before
hitting the network, so a bug in the batching/retry logic cannot run up an
unbounded bill. Two independent caps, each disabled by setting it to 0:

  GEMINI_RUN_CALL_CAP   — in-process counter. Bounds a single worker process
                          or CLI batch run even when Redis is unreachable.
  GEMINI_DAILY_CALL_CAP — Redis counter shared across all workers, keyed by
                          UTC date. The authoritative daily spend ceiling.

If Redis is unavailable the daily cap fails open (the run cap still applies)
so the legacy CLI batch mode keeps working outside docker.

Mock mode (GOOGLE_API_KEY=MOCK_KEY...) never reaches this module because the
factory returns RedTeamMockProvider instead of GoogleVisionProvider.
"""
import datetime
import logging
import threading

import redis

from app.core import config

logger = logging.getLogger(__name__)

DAILY_KEY_PREFIX = "budget:gemini:"
# Keep the counter a day past its window so operators can inspect yesterday's usage.
_DAILY_KEY_TTL_SECONDS = 48 * 3600


class BudgetExceededError(RuntimeError):
    """A Gemini call would exceed GEMINI_RUN_CALL_CAP or GEMINI_DAILY_CALL_CAP."""


_lock = threading.Lock()
_run_count = 0
_redis_client = None
_redis_disabled = False


def _get_redis():
    global _redis_client, _redis_disabled
    if _redis_disabled:
        return None
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
    return _redis_client


def _daily_key(today: datetime.date = None) -> str:
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    return DAILY_KEY_PREFIX + today.strftime("%Y%m%d")


def register_call():
    """Count one prospective Gemini API call against both caps.

    Raises BudgetExceededError *before* the call is made if either cap is hit.
    """
    global _run_count, _redis_disabled

    run_cap = config.GEMINI_RUN_CALL_CAP
    if run_cap > 0:
        with _lock:
            if _run_count >= run_cap:
                raise BudgetExceededError(
                    f"Per-run Gemini call cap reached ({run_cap}). "
                    "Raise GEMINI_RUN_CALL_CAP (0 disables) or restart after "
                    "investigating why so many calls were made."
                )
            _run_count += 1

    day_cap = config.GEMINI_DAILY_CALL_CAP
    if day_cap > 0:
        client = _get_redis()
        if client is None:
            return
        try:
            key = _daily_key()
            count = client.incr(key)
            if count == 1:
                client.expire(key, _DAILY_KEY_TTL_SECONDS)
        except redis.RedisError:
            # Fail open: never let a Redis outage take down OCR, the
            # in-process run cap still bounds spend. Disable further
            # attempts so each call doesn't stall on a dead connection.
            _redis_disabled = True
            logger.warning(
                "Cost guard: Redis unreachable at %s — daily Gemini call cap "
                "disabled for this process (per-run cap still active).",
                config.REDIS_URL,
            )
            return
        if count > day_cap:
            raise BudgetExceededError(
                f"Daily Gemini call cap reached ({day_cap} calls on "
                f"{key.removeprefix(DAILY_KEY_PREFIX)}). Raise "
                "GEMINI_DAILY_CALL_CAP (0 disables) or wait until tomorrow. "
                "If you did not expect this volume, check for a retry loop "
                "before raising the cap."
            )


def reset_run_counter():
    """Reset the in-process counter (start of a new CLI batch run / tests)."""
    global _run_count
    with _lock:
        _run_count = 0
