"""Background orchestration jobs.

Revision ID: 004_orchestration_jobs
Revises: 003_constraints_cache
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_orchestration_jobs"
down_revision: str | None = "003_constraints_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orchestration_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("conflict_summary", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_jobs_session_created", "orchestration_jobs", ["session_id", "created_at"]
    )
    op.create_index("idx_jobs_user_status", "orchestration_jobs", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("orchestration_jobs")
