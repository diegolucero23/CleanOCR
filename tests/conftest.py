"""
tests/conftest.py

Sets up a dummy GOOGLE_API_KEY before any app module is collected by pytest.
This prevents config.py from calling sys.exit() in environments where a real
.env file is not present (CI, fresh clones, etc.).

In local development, if a .env file exists with a real key,
load_dotenv(override=True) in config.py will replace this dummy value after
module load — so real credentials are never displaced when present.

Also disables API rate limiting for every test by default (see
_disable_rate_limiting below), and points the app at a throwaway SQLite
database for the whole session (see pytest_sessionstart below).
"""
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-ci")

# Throwaway database for the whole test session. Set before any app module is
# imported so app.db.database never builds an engine on the developer's
# workspaces/cleanocr.db (the default DATABASE_URL). Before this, every upload
# test left a doc.pdf / dummy.pdf / test.pdf job in the dev UI's history.
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="cleanocr-tests-"))
_TEST_DB_URL = f"sqlite:///{(_TEST_DB_DIR / 'cleanocr_test.db').as_posix()}"
os.environ["DATABASE_URL"] = _TEST_DB_URL


def pytest_sessionstart(session):
    """Bind the app to the throwaway database and create its schema.

    config.py calls load_dotenv(override=True), so a DATABASE_URL in .env would
    win over the environment variable above. Rebinding the engine here keeps
    tests off the real database either way; get_db() and get_db_context() look
    up SessionLocal at call time, so they pick up the rebind.
    """
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    from app.db import database
    import app.db.models  # noqa: F401  (registers tables on Base.metadata before init_db)

    if database.engine.url.database != make_url(_TEST_DB_URL).database:
        database.engine.dispose()
        database.engine = database.get_engine(_TEST_DB_URL)
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
    database.init_db()


def pytest_sessionfinish(session, exitstatus):
    """Release SQLite handles (required on Windows) and delete the throwaway database."""
    from app.db import database

    database.engine.dispose()
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


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
