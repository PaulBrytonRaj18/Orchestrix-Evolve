"""Database-level uniqueness, race-safe persistence and migration 003's data merge."""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from database import SessionLocal, get_db_context
from models import Citation, Paper, Summary
from models import Session as SessionModel
from services import persistence


@pytest.fixture
def session_id():
    sid = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=sid, name="s", query="q", user_id="u"))
    return sid


def _paper(session_id, ext, **kw):
    return Paper(session_id=session_id, title=kw.get("title", "T"), source="x", external_id=ext)


def test_unique_index_rejects_duplicate_paper(session_id):
    with pytest.raises(IntegrityError), get_db_context() as db:
        db.add(_paper(session_id, "10.1/dup"))
        db.add(_paper(session_id, "10.1/dup", title="T2"))
        db.flush()


def test_null_external_ids_are_not_constrained(session_id):
    with get_db_context() as db:
        db.add(_paper(session_id, None))
        db.add(_paper(session_id, None, title="other"))
    with get_db_context() as db:
        assert db.scalar(sa.select(sa.func.count()).where(Paper.session_id == session_id)) == 2


def test_one_summary_per_paper(session_id):
    with get_db_context() as db:
        p = _paper(session_id, "10.1/s")
        db.add(p)
        db.flush()
        db.add(Summary(paper_id=p.id))
        db.flush()
        db.add(Summary(paper_id=p.id))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_save_papers_survives_a_concurrent_insert(session_id, monkeypatch):
    """Another writer inserts the same work between our snapshot and our INSERT."""
    with get_db_context() as other:
        other.add(_paper(session_id, "10.1/race", title="Winner"))

    db = SessionLocal()
    real_execute = db.execute
    state = {"first": True}

    def stale_snapshot(stmt, *a, **kw):  # our "existing papers" read predates the winner
        if state["first"]:
            state["first"] = False
            return real_execute(
                sa.select(Paper.id, Paper.external_id, Paper.title).where(sa.false())
            )
        return real_execute(stmt, *a, **kw)

    monkeypatch.setattr(db, "execute", stale_snapshot)
    try:
        id_map = persistence.save_papers(
            db,
            session_id,
            [
                {"id": "prov-1", "title": "Loser", "external_id": "10.1/race", "source": "x"},
                {
                    "id": "prov-2",
                    "title": "Fresh",
                    "external_id": "10.1/new",
                    "source": "x",
                    "citation": {"apa": "A"},
                },
            ],
        )
        db.commit()
    finally:
        db.close()
    with get_db_context() as check:
        winner = check.scalar(sa.select(Paper).where(Paper.external_id == "10.1/race"))
        assert id_map["prov-1"] == winner.id and winner.title == "Winner"
        assert id_map["prov-2"] == "prov-2"
        assert check.scalar(sa.select(Citation.apa).where(Citation.paper_id == "prov-2")) == "A"


def test_get_or_create_falls_back_to_the_winner(session_id, monkeypatch):
    with get_db_context() as db:
        p = _paper(session_id, "10.1/goc")
        db.add(p)
        db.flush()
        pid = p.id
    with get_db_context() as other:
        other.add(Summary(paper_id=pid, methodology="winner"))

    db = SessionLocal()
    real_scalar = db.scalar
    calls = {"n": 0}

    def miss_once(stmt, *a, **kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_scalar(stmt, *a, **kw)

    monkeypatch.setattr(db, "scalar", miss_once)
    try:
        row = persistence._get_or_create(db, Summary, {"paper_id": pid})
        assert row.methodology == "winner"
        db.commit()
    finally:
        db.close()


def test_migration_003_merges_existing_duplicates():
    from alembic.config import Config

    from alembic import command

    backend = Path(__file__).resolve().parent.parent
    url = os.environ.get("TEST_DATABASE_URL", "")
    if url.startswith("postgresql"):
        pytest.skip("migration data test runs on its own SQLite file")
    db_file = Path(tempfile.mkdtemp()) / "mig.db"
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")

    import database  # alembic/env.py reads database.DATABASE_URL; point it at the temp file

    original = database.DATABASE_URL
    database.DATABASE_URL = f"sqlite:///{db_file}"
    try:
        command.upgrade(cfg, "002_decouple_user_fk")
        eng = sa.create_engine(f"sqlite:///{db_file}")
        with eng.begin() as c:
            c.execute(sa.text("INSERT INTO sessions (id, name, query) VALUES ('s','n','q')"))
            for pid, ts in (("p-old", "2024-01-01"), ("p-new", "2024-02-01")):
                c.execute(
                    sa.text(
                        "INSERT INTO papers (id, session_id, title, authors, source, external_id,"
                        " created_at, updated_at) VALUES (:id,'s','T','[]','x','10.1/a',:ts,:ts)"
                    ),
                    {"id": pid, "ts": ts},
                )
            c.execute(
                sa.text("INSERT INTO notes (id, paper_id, content) VALUES ('n1','p-new','keep me')")
            )
            c.execute(
                sa.text(
                    "INSERT INTO summaries (id, paper_id, methodology) VALUES ('s1','p-new','m')"
                )
            )
            for aid, ts in (("a1", "2024-01-01"), ("a2", "2024-03-01")):
                c.execute(
                    sa.text(
                        "INSERT INTO analyses (id, session_id, analysis_type, data_json, created_at,"
                        " updated_at) VALUES (:id,'s','full','{}',:ts,:ts)"
                    ),
                    {"id": aid, "ts": ts},
                )
        command.upgrade(cfg, "head")
        with eng.begin() as c:
            assert c.execute(sa.text("SELECT id FROM papers")).scalars().all() == ["p-old"]
            assert c.execute(sa.text("SELECT paper_id FROM notes")).scalar() == "p-old"
            assert c.execute(sa.text("SELECT paper_id FROM summaries")).scalar() == "p-old"
            assert c.execute(sa.text("SELECT id FROM analyses")).scalars().all() == ["a2"]
        names = {i["name"] for i in sa.inspect(eng).get_indexes("papers")}
        assert {"uq_papers_session_external", "idx_papers_session_created"} <= names
        assert "source_cache" in sa.inspect(eng).get_table_names()
        # The migrated schema carries exactly the indexes the models declare.
        from database import Base

        insp = sa.inspect(eng)
        for table in Base.metadata.sorted_tables:
            if table.name == "users":
                continue
            declared = {(i.name, bool(i.unique)) for i in table.indexes}
            actual = {(i["name"], bool(i["unique"])) for i in insp.get_indexes(table.name)}
            assert actual == declared, table.name
        command.downgrade(cfg, "002_decouple_user_fk")
        eng.dispose()
    finally:
        database.DATABASE_URL = original
