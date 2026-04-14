"""Initial migration - Create all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-04-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_admin", sa.Boolean(), default=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "scheduled_digests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("frequency", sa.String(), nullable=False, default="weekly"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("notify_email", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "papers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False, default=[]),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False
        ),
        sa.Column("analysis_type", sa.String(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "summaries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paper_id", sa.String(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("abstract_compression", sa.Text(), nullable=True),
        sa.Column("key_contributions", sa.Text(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paper_id", sa.String(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("apa", sa.Text(), nullable=True),
        sa.Column("mla", sa.Text(), nullable=True),
        sa.Column("ieee", sa.Text(), nullable=True),
        sa.Column("chicago", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paper_id", sa.String(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "conflicts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False
        ),
        sa.Column("conflict_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("analysis_insight", sa.Text(), nullable=True),
        sa.Column("summarization_insight", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), default=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "digest_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "scheduled_digest_id",
            sa.String(),
            sa.ForeignKey("scheduled_digests.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=True
        ),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("new_papers_count", sa.Integer(), default=0),
        sa.Column("new_paper_ids", sa.JSON(), nullable=False, default=[]),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "roadmaps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False
        ),
        sa.Column("foundational_papers_json", sa.JSON(), nullable=False),
        sa.Column("gap_areas_json", sa.JSON(), nullable=False),
        sa.Column("next_queries_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "syntheses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "session_id", sa.String(), sa.ForeignKey("sessions.id"), nullable=False
        ),
        sa.Column("paper_ids", sa.JSON(), nullable=False, default=[]),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("syntheses")
    op.drop_table("roadmaps")
    op.drop_table("digest_runs")
    op.drop_table("conflicts")
    op.drop_table("notes")
    op.drop_table("citations")
    op.drop_table("summaries")
    op.drop_table("analyses")
    op.drop_table("papers")
    op.drop_table("scheduled_digests")
    op.drop_table("sessions")
    op.drop_index("ix_users_username", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
