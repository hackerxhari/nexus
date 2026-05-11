"""
Database connection and session management for Nexus.
SQLAlchemy async engine with connection pooling.
Never import session directly — always use get_db() dependency.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker
)
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.exceptions import DatabaseError
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    All models must inherit from this.
    """
    pass


def _create_engine():
    """
    Create SQLAlchemy engine based on environment.
    SQLite for dev, easily swappable to Postgres for production.
    """
    db_url = settings.DATABASE_URL
    is_sqlite = db_url.startswith("sqlite")

    if is_sqlite:
        engine = create_engine(
            db_url,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            },
            poolclass=StaticPool,
            echo=settings.DEBUG
        )

        # Enable WAL mode for better SQLite concurrency
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    else:
        # PostgreSQL for production
        engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.DEBUG
        )

    logger.info(
        "database_engine_created",
        url=db_url.split("@")[-1] if "@" in db_url else db_url,
        dialect="sqlite" if is_sqlite else "postgresql"
    )

    return engine


# Module level engine and session factory
engine = _create_engine()

SessionFactory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Handles commit, rollback, and cleanup automatically.

    Usage:
        with get_db_session() as db:
            user = db.query(User).first()
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except DatabaseError:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error("database_session_error", error=str(e))
        raise DatabaseError(f"Database operation failed: {str(e)}")
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage in routes:
        @router.get("/")
        def route(db: Session = Depends(get_db)):
            ...
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Create all tables on startup.
    Safe to call multiple times — only creates missing tables.
    """
    try:
        import db.models
        Base.metadata.create_all(bind=engine)
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise DatabaseError(f"Failed to initialize database: {str(e)}")


def check_db_health() -> bool:
    """Check database connectivity. Never raises."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False