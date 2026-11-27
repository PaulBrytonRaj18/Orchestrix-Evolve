"""Citation graph: OpenAlex id and reference list on works.

Revision ID: 007_citation_graph
Revises: 006_claims
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_citation_graph"
down_revision: str | None = "006_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("works") as b:
        b.add_column(sa.Column("openalex_id", sa.String(40), nullable=True))
        b.add_column(sa.Column("references", sa.JSON(), nullable=True))
        b.add_column(sa.Column("references_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_works_openalex_id", "works", ["openalex_id"])


def downgrade() -> None:
    op.drop_index("ix_works_openalex_id", table_name="works")
    with op.batch_alter_table("works") as b:
        for col in ("references_fetched_at", "references", "openalex_id"):
            b.drop_column(col)
