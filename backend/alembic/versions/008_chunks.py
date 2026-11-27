"""Question answering: text passages (with embeddings) per work.

Revision ID: 008_chunks
Revises: 007_citation_graph
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_chunks"
down_revision: str | None = "007_citation_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _embedding_type(conn):
    if conn.dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector

        return Vector()
    return sa.JSON()


def upgrade() -> None:
    conn = op.get_bind()
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("work_id", sa.String(), sa.ForeignKey("works.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("embedding", _embedding_type(conn), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_chunks_work_position", "chunks", ["work_id", "position"], unique=True)
    with op.batch_alter_table("works") as b:
        b.add_column(sa.Column("passages_source", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("works") as b:
        b.drop_column("passages_source")
    op.drop_table("chunks")
