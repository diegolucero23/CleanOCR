import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core import config

Base = declarative_base()

def get_engine(database_url: str = None):
    url = database_url or config.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30.0
    eng = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    return eng

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(target_engine=None):
    """
    Initializes the database schema by creating all registered tables.
    If using SQLite, ensures the target directory exists on disk.
    """
    eng = target_engine or engine
    url_str = str(eng.url)
    if "sqlite" in url_str:
        # Extract directory from sqlite path if file-based
        db_path = eng.url.database
        if db_path and db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(bind=eng)

def get_db():
    """
    FastAPI dependency that yields a database session and guarantees closure.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """
    Context manager for background workers and scripts outside FastAPI request context.
    Commits on normal exit, rolls back on exception, and ensures closure.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
