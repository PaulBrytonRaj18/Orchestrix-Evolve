"""Database-level uniqueness, race-safe persistence and migration 003's data merge."""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from database import SessionLocal, get_db_context
from models import Citation, Paper, Summary, Work
from models import Session as SessionModel
from services import persistence


@pytest.fixture
def session_id():
    sid = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=sid, name="s", query="q", user_id="u"))
    return sid


def _work(key, title="T"):
    return Work(work_key=key, title=title, source="x", external_id=key)


def test_same_work_twice_in_a_session_is_rejected(session_id):
    with pytest.raises(IntegrityError), get_db_context() as db:
        w = _work("10.1/dup")
        db.add(w)
        db.flush()
        db.add(Paper(session_id=session_id, work_id=w.id))
        db.add(Paper(session_id=session_id, work_id=w.id))
        db.flush()


def test_work_keys_are_unique():
    with pytest.raises(IntegrityError), get_db_context() as db:
        db.add(_work("10.1/same"))
        db.add(_work("10.1/same", title="other"))
        db.flush()


def test_one_summary_per_work():
    with get_db_context() as db:
        w = _work("10.1/s")
        db.add(w)
        db.flush()
        db.add(Summary(work_id=w.id))
        db.flush()
        db.add(Summary(work_id=w.id))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_two_sessions_share_one_work(session_id):
    other = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=other, name="s2", query="q", user_id="u2"))
    paper = {
        "title": "Shared paper",
        "external_id": "10.1/shared",
        "source": "x",
        "citation_count": 3,
        "citation": {"apa": "A"},
    }
    with get_db_context() as db:
        persistence.save_papers(db, session_id, [dict(paper, id="a")])
        persistence.save_papers(db, other, [dict(paper, id="b", citation_count=9)])
    with get_db_context() as db:
        works = db.scalars(sa.select(Work).where(Work.external_id == "10.1/shared")).all()
        assert len(works) == 1 and works[0].citation_count == 9  # refreshed, not duplicated
        links = db.scalars(sa.select(Paper).where(Paper.work_id == works[0].id)).all()
        assert {p.session_id for p in links} == {session_id, other}
        assert (
            db.scalar(
                sa.select(sa.func.count())
                .select_from(Citation)
                .where(Citation.work_id == works[0].id)
            )
            == 1
        )


def test_save_papers_survives_a_concurrent_insert(session_id, monkeypatch):
    """Another writer creates the same work between our lookup and our INSERT."""
    with get_db_context() as other:
        other.add(_work("10.1/race", title="Winner"))

    db = SessionLocal()
    real_scalar = db.scalar
    state = {"missed": False}

    def miss_work_once(stmt, *a, **kw):  # our lookup predates the winner's commit
        if not state["missed"] and "works" in str(stmt) and "work_key" in str(stmt):
            state["missed"] = True
            return None
        return real_scalar(stmt, *a, **kw)

    monkeypatch.setattr(db, "scalar", miss_work_once)
    try:
        id_map = persistence.save_papers(
            db,
            session_id,
            [{"id": "prov-1", "title": "Loser", "external_id": "10.1/race", "source": "x"}],
        )
        db.commit()
    finally:
        db.close()
    assert state["missed"]
    with get_db_context() as check:
        winner = check.scalar(sa.select(Work).where(Work.work_key == "10.1/race"))
        link = check.get(Paper, id_map["prov-1"])
        assert link.work_id == winner.id and winner.title == "Winner"


def test_get_or_create_falls_back_to_the_winner(session_id, monkeypatch):
    with get_db_context() as db:
        w = _work("10.1/goc")
        db.add(w)
        db.flush()
        pid = w.id
    with get_db_context() as other:
        other.add(Summary(work_id=pid, methodology="winner"))

    db = SessionLocal()
    real_scalar = db.scalar
    calls = {"n": 0}

    def miss_once(stmt, *a, **kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_scalar(stmt, *a, **kw)

    monkeypatch.setattr(db, "scalar", miss_once)
    try:
        row = persistence._get_or_create(db, Summary, {"work_id": pid})
        assert row.methodology == "winner"
        db.commit()
    finally:
        db.close()


def test_migrations_merge_duplicates_and_build_shared_works():
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
            c.execute(sa.text("INSERT INTO sessions (id, name, query) VALUES ('s2','n','q')"))
            # The same work in a second session → both sessions must share one works row.
            c.execute(
                sa.text(
                    "INSERT INTO papers (id, session_id, title, authors, source, external_id,"
                    " citation_count, created_at, updated_at)"
                    " VALUES ('p-s2','s2','T','[]','x','10.1/a',42,'2024-03-01','2024-03-01')"
                )
            )
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
            papers = c.execute(sa.text("SELECT id, work_id FROM papers ORDER BY id")).all()
            assert [p[0] for p in papers] == ["p-old", "p-s2"]
            works = c.execute(sa.text("SELECT id, work_key, citation_count FROM works")).all()
            assert len(works) == 1 and works[0][1] == "10.1/a" and works[0][2] == 42
            assert {p[1] for p in papers} == {works[0][0]}
            assert c.execute(sa.text("SELECT paper_id FROM notes")).scalar() == "p-old"
            assert c.execute(sa.text("SELECT work_id FROM summaries")).scalar() == works[0][0]
            assert c.execute(sa.text("SELECT id FROM analyses")).scalars().all() == ["a2"]
        names = {i["name"] for i in sa.inspect(eng).get_indexes("papers")}
        assert {"uq_papers_session_work", "idx_papers_session_created"} <= names
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
        command.downgrade(cfg, "004_orchestration_jobs")
        with eng.begin() as c:  # content is copied back onto the papers rows
            rows = c.execute(sa.text("SELECT id, title, external_id FROM papers ORDER BY id")).all()
            assert rows == [("p-old", "T", "10.1/a"), ("p-s2", "T", "10.1/a")]
            assert c.execute(sa.text("SELECT paper_id FROM summaries")).scalar() == "p-old"
        command.downgrade(cfg, "002_decouple_user_fk")
        eng.dispose()
    finally:
        database.DATABASE_URL = original
