"""Claim-based conflict detection: ``claims`` per work; evidence on conflicts.

Revision ID: 006_claims
Revises: 005_shared_works
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_claims"
down_revision: str | None = "005_shared_works"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("work_id", sa.String(), sa.ForeignKey("works.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("direction", sa.String(20), nullable=True),
        sa.Column("dataset", sa.String(), nullable=True),
        sa.Column("metric", sa.String(100), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_claims_work_position", "claims", ["work_id", "position"], unique=True)
    with op.batch_alter_table("conflicts") as b:
        b.add_column(sa.Column("paper_a_id", sa.String(), nullable=True))
        b.add_column(sa.Column("paper_b_id", sa.String(), nullable=True))
        b.add_column(sa.Column("evidence_a", sa.Text(), nullable=True))
        b.add_column(sa.Column("evidence_b", sa.Text(), nullable=True))
        b.add_column(sa.Column("confidence", sa.Float(), nullable=True))
        b.add_column(sa.Column("detected_by", sa.String(20), nullable=True))
        b.create_foreign_key(
            "fk_conflicts_paper_a", "papers", ["paper_a_id"], ["id"], ondelete="SET NULL"
        )
        b.create_foreign_key(
            "fk_conflicts_paper_b", "papers", ["paper_b_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("conflicts") as b:
        b.drop_constraint("fk_conflicts_paper_a", type_="foreignkey")
        b.drop_constraint("fk_conflicts_paper_b", type_="foreignkey")
        for col in ("paper_a_id", "paper_b_id", "evidence_a", "evidence_b", "confidence", "detected_by"):
            b.drop_column(col)
    op.drop_table("claims")
