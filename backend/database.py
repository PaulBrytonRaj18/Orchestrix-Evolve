"""Database engine and session management (one code path for SQLite and Postgres)."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

settings = get_settings()
DATABASE_URL = settings.resolved_database_url


class Base(DeclarativeBase):
    pass


def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")


def _build_engine():
    if is_postgres():
        return create_engine(
            DATABASE_URL,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",
                # Supabase's transaction pooler (port 6543) does not support
                # server-side prepared statements.
                "prepare_threshold": None,
            },
        )
    eng = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _sqlite_fk_on(dbapi_conn, _):  # make SQLite enforce FKs like Postgres does
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return eng


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Endpoints commit explicitly; anything uncommitted is rolled back."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Transactional scope for background work: commits on success, rolls back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create any missing tables. Schema *changes* go through Alembic migrations."""
    import models  # noqa: F401  (registers mappers on Base.metadata)

    Base.metadata.create_all(bind=engine)


def close_engine() -> None:
    engine.dispose()


__all__ = [
    "Base",
    "DATABASE_URL",
    "SessionLocal",
    "close_engine",
    "engine",
    "get_db",
    "get_db_context",
    "init_db",
    "is_postgres",
]
