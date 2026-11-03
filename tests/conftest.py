"""
tests/conftest.py

Sets up a dummy GOOGLE_API_KEY before any app module is collected by pytest.
This prevents config.py from calling sys.exit() in environments where a real
.env file is not present (CI, fresh clones, etc.).

In local development, if a .env file exists with a real key,
load_dotenv(override=True) in config.py will replace this dummy value after
module load — so real credentials are never displaced when present.

Also disables API rate limiting for every test by default (see
_disable_rate_limiting below).
"""
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-ci")


@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """Let every request through the API rate limiter unless a test opts in.

    The limiter in app.core.security talks to its own Redis client, which test
    fixtures that mock app.api.server.redis_client do not replace. With a live
    Redis (CI), the suite's uploads share one client IP and hit the
    3-uploads-per-minute limit, so later tests got HTTP 429. Without Redis
    (most local runs), the limiter fails open and hid the problem.

    Tests that exercise throttling patch app.core.security.check_rate_limit
    themselves (the inner patch wins) or test RateLimiter directly.
    """
    with patch("app.core.security.check_rate_limit", return_value=(True, 0)):
        yield
