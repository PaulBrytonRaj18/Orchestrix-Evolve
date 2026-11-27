"""Store each paper once: shared ``works`` with sessions linking to them.

* New ``works`` table (one row per paper across all sessions/users) with an
  ``embedding`` column — pgvector ``vector`` on PostgreSQL, JSON elsewhere.
* ``papers`` becomes the session link (session_id, work_id, relevance_score);
  its content columns move to ``works``.
* ``summaries`` and ``citations`` belong to the work (one each), so they are
  computed once and reused by every session that finds the paper.

Existing data is migrated: works are keyed by external id (DOI / arXiv) or a title
hash; papers in one session that turn out to be the same work are merged, moving
notes onto the kept row.

On PostgreSQL this needs the ``vector`` extension (enabled by default on Supabase;
``CREATE EXTENSION vector`` elsewhere).

Revision ID: 005_shared_works
Revises: 004_orchestration_jobs
"""

import hashlib
import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_shared_works"
down_revision: str | None = "004_orchestration_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTENT = ("title", "authors", "year", "abstract", "source_url", "citation_count", "external_id", "source")


def _work_key(external_id, title) -> str:  # frozen copy of models.work_key_for
    if external_id:
        return external_id[:500]
    normalised = " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))
    return "title:" + hashlib.sha1(normalised.encode()).hexdigest()


def _embedding_type(conn):
    if conn.dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector

        return Vector()
    return sa.JSON()


def _indexes(conn, table):
    return {i["name"] for i in sa.inspect(conn).get_indexes(table)}


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        try:
            with conn.begin_nested():
                conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:  # pragma: no cover - depends on the server
            raise RuntimeError(
                "Migration 005 needs the pgvector extension. On Supabase enable 'vector' under "
                "Database → Extensions; elsewhere install pgvector and run CREATE EXTENSION vector."
            ) from exc

    op.create_table(
        "works",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("work_key", sa.String(600), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=True),
        sa.Column("embedding", _embedding_type(conn), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_works_work_key", "works", ["work_key"], unique=True)
    op.create_index("ix_works_external_id", "works", ["external_id"])

    with op.batch_alter_table("papers") as b:
        b.add_column(sa.Column("work_id", sa.String(), nullable=True))
    with op.batch_alter_table("summaries") as b:
        b.add_column(sa.Column("work_id", sa.String(), nullable=True))
        b.add_column(sa.Column("generated_by", sa.String(20), nullable=True))
    with op.batch_alter_table("citations") as b:
        b.add_column(sa.Column("work_id", sa.String(), nullable=True))

    # ── backfill works from existing papers ────────────────────────────────
    papers = conn.execute(
        sa.text(
            "SELECT id, session_id, title, authors, year, abstract, source_url, citation_count,"
            " external_id, source FROM papers ORDER BY created_at, id"
        )
    ).mappings().all()
    work_by_key: dict[str, str] = {}
    keeper: dict[tuple[str, str], str] = {}  # (session, work) → kept paper id
    for p in papers:
        key = _work_key(p["external_id"], p["title"])
        wid = work_by_key.get(key)
        if wid is None:
            wid = str(uuid.uuid4())
            work_by_key[key] = wid
            conn.execute(
                sa.table(
                    "works",
                    *(sa.column(c) for c in ("id", "work_key", "venue", *_CONTENT) if c != "authors"),
                    sa.column("authors", sa.JSON()),  # typed, so Postgres gets JSON, not an array
                ).insert(),
                {"id": wid, "work_key": key, "venue": None, **{c: p[c] for c in _CONTENT},
                 "authors": p["authors"] if p["authors"] is not None else []},
            )
        else:
            conn.execute(
                sa.text(
                    "UPDATE works SET citation_count = :c WHERE id = :w"
                    " AND (citation_count IS NULL OR citation_count < :c)"
                ),
                {"c": p["citation_count"], "w": wid},
            )
        kept = keeper.get((p["session_id"], wid))
        if kept is None:
            keeper[(p["session_id"], wid)] = p["id"]
            conn.execute(sa.text("UPDATE papers SET work_id = :w WHERE id = :p"), {"w": wid, "p": p["id"]})
        else:  # same work twice in one session → merge into the older row
            params = {"keep": kept, "dupe": p["id"]}
            conn.execute(sa.text("UPDATE notes SET paper_id = :keep WHERE paper_id = :dupe"), params)
            for child in ("summaries", "citations"):
                if conn.execute(sa.text(f"SELECT 1 FROM {child} WHERE paper_id = :keep"), params).first():
                    conn.execute(sa.text(f"DELETE FROM {child} WHERE paper_id = :dupe"), params)
                else:
                    conn.execute(sa.text(f"UPDATE {child} SET paper_id = :keep WHERE paper_id = :dupe"), params)
            conn.execute(sa.text("DELETE FROM papers WHERE id = :dupe"), params)

    # summaries / citations follow their paper to the work; keep the newest per work
    for child in ("summaries", "citations"):
        conn.execute(
            sa.text(
                f"UPDATE {child} SET work_id = (SELECT work_id FROM papers WHERE papers.id = {child}.paper_id)"
            )
        )
        conn.execute(sa.text(f"DELETE FROM {child} WHERE work_id IS NULL"))
        rows = conn.execute(
            sa.text(f"SELECT id, work_id FROM {child} ORDER BY work_id, updated_at DESC, id DESC")
        ).all()
        seen: set[str] = set()
        for row_id, wid in rows:
            if wid in seen:
                conn.execute(sa.text(f"DELETE FROM {child} WHERE id = :i"), {"i": row_id})
            seen.add(wid)

    # ── reshape tables ─────────────────────────────────────────────────────
    for name in ("uq_papers_session_external", "ix_papers_external_id"):
        if name in _indexes(conn, "papers"):
            op.drop_index(name, table_name="papers")
    with op.batch_alter_table("papers") as b:
        b.alter_column("work_id", existing_type=sa.String(), nullable=False)
        b.create_foreign_key("fk_papers_work_id_works", "works", ["work_id"], ["id"])
        for col in _CONTENT:
            b.drop_column(col)
    op.create_index("ix_papers_work_id", "papers", ["work_id"])
    op.create_index("uq_papers_session_work", "papers", ["session_id", "work_id"], unique=True)

    for child, old_index in (("summaries", "uq_summaries_paper_id"), ("citations", "uq_citations_paper_id")):
        if old_index in _indexes(conn, child):
            op.drop_index(old_index, table_name=child)
        with op.batch_alter_table(child) as b:
            b.alter_column("work_id", existing_type=sa.String(), nullable=False)
            b.create_foreign_key(f"fk_{child}_work_id_works", "works", ["work_id"], ["id"])
            b.drop_column("paper_id")
        op.create_index(f"uq_{child}_work_id", child, ["work_id"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("papers") as b:
        b.add_column(sa.Column("title", sa.String(), nullable=True))
        b.add_column(sa.Column("authors", sa.JSON(), nullable=True))
        b.add_column(sa.Column("year", sa.Integer(), nullable=True))
        b.add_column(sa.Column("abstract", sa.Text(), nullable=True))
        b.add_column(sa.Column("source_url", sa.String(), nullable=True))
        b.add_column(sa.Column("citation_count", sa.Integer(), nullable=True))
        b.add_column(sa.Column("external_id", sa.String(), nullable=True))
        b.add_column(sa.Column("source", sa.String(), nullable=True))
    for col in _CONTENT:
        conn.execute(sa.text(f"UPDATE papers SET {col} = (SELECT {col} FROM works WHERE works.id = papers.work_id)"))
    for child in ("summaries", "citations"):
        with op.batch_alter_table(child) as b:
            b.add_column(sa.Column("paper_id", sa.String(), nullable=True))
        # a work-level summary goes back to one paper that shows that work
        conn.execute(
            sa.text(
                f"UPDATE {child} SET paper_id = (SELECT MIN(id) FROM papers WHERE papers.work_id = {child}.work_id)"
            )
        )
        conn.execute(sa.text(f"DELETE FROM {child} WHERE paper_id IS NULL"))
        op.drop_index(f"uq_{child}_work_id", table_name=child)
        with op.batch_alter_table(child) as b:
            b.drop_constraint(f"fk_{child}_work_id_works", type_="foreignkey")
            b.drop_column("work_id")
            if child == "summaries":
                b.drop_column("generated_by")
            b.alter_column("paper_id", existing_type=sa.String(), nullable=False)
            b.create_foreign_key(f"{child}_paper_id_fkey", "papers", ["paper_id"], ["id"])
        op.create_index(f"uq_{child}_paper_id", child, ["paper_id"], unique=True)
    op.drop_index("uq_papers_session_work", table_name="papers")
    op.drop_index("ix_papers_work_id", table_name="papers")
    with op.batch_alter_table("papers") as b:
        b.drop_constraint("fk_papers_work_id_works", type_="foreignkey")
        b.drop_column("work_id")
        b.alter_column("title", existing_type=sa.String(), nullable=False)
        b.alter_column("source", existing_type=sa.String(), nullable=False)
    op.create_index("ix_papers_external_id", "papers", ["external_id"])
    op.create_index("uq_papers_session_external", "papers", ["session_id", "external_id"], unique=True)
    op.drop_table("works")
