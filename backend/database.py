import os
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")
USE_ASYNC = os.getenv("USE_ASYNC", "false").lower() == "true"

if SUPABASE_DB_URL:
    DATABASE_URL = SUPABASE_DB_URL


def is_postgres():
    return DATABASE_URL and (
        "postgres" in DATABASE_URL.lower() or "postgresql" in DATABASE_URL.lower()
    )


if is_postgres():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session, declarative_base
    from sqlalchemy.pool import QueuePool

    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    def get_db() -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def get_db_context() -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def init_db_async():
        from models import Base as ModelsBase

        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)

    def init_db():
        from models import Base as ModelsBase

        ModelsBase.metadata.create_all(bind=engine)

    def close_engine():
        engine.dispose()

    __all__ = [
        "get_db",
        "get_db_context",
        "init_db",
        "init_db_async",
        "close_engine",
        "Base",
        "engine",
        "is_postgres",
    ]

else:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session, declarative_base

    if not DATABASE_URL:
        DATABASE_URL = "sqlite:///./orchestrix.db"

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
        pool_pre_ping=True,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    def get_db() -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def get_db_context() -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def init_db_async():
        init_db()

    def init_db():
        from models import Base as ModelsBase

        ModelsBase.metadata.create_all(bind=engine)

    def close_engine():
        engine.dispose()

    __all__ = [
        "get_db",
        "get_db_context",
        "init_db",
        "init_db_async",
        "close_engine",
        "Base",
        "engine",
        "is_postgres",
    ]
