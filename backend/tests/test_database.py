import pytest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseModule:
    def test_database_imports(self):
        from database import get_db, init_db, Base, engine

        assert get_db is not None
        assert init_db is not None
        assert Base is not None
        assert engine is not None

    def test_get_db_returns_generator(self):
        from database import get_db

        gen = get_db()
        assert hasattr(gen, "__next__")

    def test_is_postgres_function_exists(self):
        from database import is_postgres

        assert callable(is_postgres)


class TestDatabaseInit:
    def test_init_db_creates_tables(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

            from database import init_db, engine

            init_db()

            from sqlalchemy import inspect

            inspector = inspect(engine)
            tables = inspector.get_table_names()

            expected_tables = [
                "users",
                "sessions",
                "papers",
                "analyses",
                "summaries",
                "citations",
                "notes",
                "conflicts",
                "scheduled_digests",
                "digest_runs",
                "roadmaps",
                "syntheses",
            ]

            for table in expected_tables:
                assert table in tables, f"Table {table} not found"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestDatabaseContext:
    def test_get_db_context(self):
        from database import get_db_context

        with get_db_context() as db:
            assert db is not None
            from sqlalchemy import text

            result = db.execute(text("SELECT 1"))
            assert result.scalar() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
