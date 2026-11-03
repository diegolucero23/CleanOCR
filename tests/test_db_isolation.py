"""
tests/test_db_isolation.py

Guards the developer's real database from test traffic.

Before 2026-11-03 the suite wrote every upload into workspaces/cleanocr.db
(the default DATABASE_URL), leaving 263 doc.pdf / dummy.pdf / test.pdf jobs in
the dev UI's job history.

Coverage:
  - The app engine and session factory point at a throwaway SQLite file
    outside the repository, never workspaces/cleanocr.db
  - The throwaway database has the schema, so API writes succeed
"""

from pathlib import Path

from sqlalchemy import inspect

from app.db import database

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_DB = (REPO_ROOT / "workspaces" / "cleanocr.db").resolve()


def _engine_db_path() -> Path:
    return Path(database.engine.url.database).resolve()


def test_engine_does_not_use_dev_database():
    assert _engine_db_path() != DEV_DB, "tests are writing into the developer's workspaces/cleanocr.db"


def test_engine_database_lives_outside_repository():
    assert REPO_ROOT not in _engine_db_path().parents


def test_session_factory_bound_to_test_engine():
    assert database.SessionLocal.kw["bind"] is database.engine


def test_test_database_has_schema():
    assert "jobs" in inspect(database.engine).get_table_names()
