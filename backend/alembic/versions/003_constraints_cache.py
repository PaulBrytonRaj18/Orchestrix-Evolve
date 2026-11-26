"""Uniqueness at the database level, missing indexes, source response cache.

* Migration 001 created no indexes on the app tables, so databases built with
  Alembic had none; every index the models declare is now created (idempotently).
* Duplicate rows that the application could create under concurrency are merged,
  then unique indexes make them impossible:
  papers (session_id, external_id) · summaries/citations (paper_id) ·
  roadmaps (session_id) · analyses (session_id, analysis_type).
* New ``source_cache`` table shared by all processes.

Revision ID: 003_constraints_cache
Revises: 002_decouple_user_fk
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_constraints_cache"
down_revision: str | None = "002_decouple_user_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, table, columns, unique) — frozen here so later model edits never rewrite history.
INDEXES = [
    ("ix_sessions_user_id", "sessions", ["user_id"], False),
    ("idx_sessions_user_updated", "sessions", ["user_id", "updated_at"], False),
    ("ix_scheduled_digests_user_id", "scheduled_digests", ["user_id"], False),
    ("idx_digests_user_created", "scheduled_digests", ["user_id", "created_at"], False),
    ("ix_papers_session_id", "papers", ["session_id"], False),
    ("ix_papers_external_id", "papers", ["external_id"], False),
    ("idx_papers_session_created", "papers", ["session_id", "created_at"], False),
    ("uq_papers_session_external", "papers", ["session_id", "external_id"], True),
    ("ix_analyses_session_id", "analyses", ["session_id"], False),
    ("uq_analyses_session_type", "analyses", ["session_id", "analysis_type"], True),
    ("uq_summaries_paper_id", "summaries", ["paper_id"], True),
    ("uq_citations_paper_id", "citations", ["paper_id"], True),
    ("ix_notes_paper_id", "notes", ["paper_id"], False),
    ("ix_syntheses_session_id", "syntheses", ["session_id"], False),
    ("ix_conflicts_session_id", "conflicts", ["session_id"], False),
    ("idx_conflicts_session_severity", "conflicts", ["session_id", "severity"], False),
    ("idx_conflicts_session_resolved", "conflicts", ["session_id", "resolved"], False),
    ("ix_digest_runs_scheduled_digest_id", "digest_runs", ["scheduled_digest_id"], False),
    ("ix_digest_runs_session_id", "digest_runs", ["session_id"], False),
    ("idx_digest_runs_sched_status", "digest_runs", ["scheduled_digest_id", "status"], False),
    ("idx_digest_runs_sched_created", "digest_runs", ["scheduled_digest_id", "created_at"], False),
    ("uq_roadmaps_session_id", "roadmaps", ["session_id"], True),
]
# Non-unique indexes superseded by a unique one on the same columns.
REPLACED = [
    ("idx_papers_session_external", "papers"),
    ("idx_analyses_session_type", "analyses"),
    ("ix_summaries_paper_id", "summaries"),
    ("ix_citations_paper_id", "citations"),
    ("ix_roadmaps_session_id", "roadmaps"),
]


def _existing_indexes(conn, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(conn).get_indexes(table)}


def _duplicate_groups(conn, table: str, cols: list[str]) -> list[tuple]:
    col_sql = ", ".join(cols)
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in cols)
    return conn.execute(
        sa.text(
            f"SELECT {col_sql} FROM {table} WHERE {not_null} "
            f"GROUP BY {col_sql} HAVING COUNT(*) > 1"
        )
    ).fetchall()


def _ids_in_group(conn, table: str, cols: list[str], values: tuple, newest_first: bool) -> list:
    where = " AND ".join(f"{c} = :v{i}" for i, c in enumerate(cols))
    order = "DESC" if newest_first else "ASC"
    rows = conn.execute(
        sa.text(f"SELECT id FROM {table} WHERE {where} ORDER BY updated_at {order}, id {order}"),
        {f"v{i}": v for i, v in enumerate(values)},
    ).fetchall()
    return [r[0] for r in rows]


def _keep_newest(conn, table: str, cols: list[str]) -> int:
    removed = 0
    for values in _duplicate_groups(conn, table, cols):
        ids = _ids_in_group(conn, table, cols, tuple(values), newest_first=True)
        for dupe in ids[1:]:
            conn.execute(sa.text(f"DELETE FROM {table} WHERE id = :id"), {"id": dupe})
            removed += 1
    return removed


def _merge_duplicate_papers(conn) -> int:
    """Keep the oldest paper per (session, external_id); move its duplicates' children."""
    removed = 0
    for values in _duplicate_groups(conn, "papers", ["session_id", "external_id"]):
        keeper, *dupes = _ids_in_group(
            conn, "papers", ["session_id", "external_id"], tuple(values), newest_first=False
        )
        for dupe in dupes:
            params = {"keeper": keeper, "dupe": dupe}
            conn.execute(sa.text("UPDATE notes SET paper_id = :keeper WHERE paper_id = :dupe"), params)
            for child in ("summaries", "citations"):
                has_own = conn.execute(
                    sa.text(f"SELECT 1 FROM {child} WHERE paper_id = :keeper"), params
                ).first()
                if has_own:
                    conn.execute(sa.text(f"DELETE FROM {child} WHERE paper_id = :dupe"), params)
                else:
                    conn.execute(
                        sa.text(f"UPDATE {child} SET paper_id = :keeper WHERE paper_id = :dupe"),
                        params,
                    )
            conn.execute(sa.text("DELETE FROM papers WHERE id = :dupe"), params)
            removed += 1
    return removed


def upgrade() -> None:
    conn = op.get_bind()

    if "source_cache" not in sa.inspect(conn).get_table_names():
        op.create_table(
            "source_cache",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_source_cache_expires_at", "source_cache", ["expires_at"])

    merged = _merge_duplicate_papers(conn)
    merged += _keep_newest(conn, "summaries", ["paper_id"])
    merged += _keep_newest(conn, "citations", ["paper_id"])
    merged += _keep_newest(conn, "roadmaps", ["session_id"])
    merged += _keep_newest(conn, "analyses", ["session_id", "analysis_type"])
    if merged:
        print(f"003_constraints_cache: removed {merged} duplicate rows")

    for name, table in REPLACED:
        if name in _existing_indexes(conn, table):
            op.drop_index(name, table_name=table)
    for name, table, cols, unique in INDEXES:
        if name not in _existing_indexes(conn, table):
            op.create_index(name, table, cols, unique=unique)


def downgrade() -> None:
    conn = op.get_bind()
    for name, table, _cols, unique in INDEXES:
        if unique and name in _existing_indexes(conn, table):
            op.drop_index(name, table_name=table)
    for name, table, cols in (
        ("idx_papers_session_external", "papers", ["session_id", "external_id"]),
        ("idx_analyses_session_type", "analyses", ["session_id", "analysis_type"]),
        ("ix_summaries_paper_id", "summaries", ["paper_id"]),
        ("ix_citations_paper_id", "citations", ["paper_id"]),
        ("ix_roadmaps_session_id", "roadmaps", ["session_id"]),
    ):
        if name not in _existing_indexes(conn, table):
            op.create_index(name, table, cols)
    op.drop_table("source_cache")
