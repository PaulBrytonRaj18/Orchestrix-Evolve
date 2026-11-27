import hashlib
import re
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Legacy local user table from the pre-Supabase JWT auth.

    Identity now lives in Supabase (``auth.users``); ``user_id`` columns store the
    Supabase ``sub`` claim and deliberately have no FK to this table. The model is
    kept only so ``migrate_to_supabase.py`` can read old SQLite databases.
    """

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (Index("idx_sessions_user_updated", "user_id", "updated_at"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    papers = relationship("Paper", back_populates="session", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")
    syntheses = relationship("Synthesis", back_populates="session", cascade="all, delete-orphan")
    conflicts = relationship("Conflict", back_populates="session", cascade="all, delete-orphan")
    roadmaps = relationship("Roadmap", back_populates="session", cascade="all, delete-orphan")
    digest_runs = relationship("DigestRun", back_populates="session", cascade="all, delete-orphan")
    jobs = relationship("OrchestrationJob", back_populates="session", cascade="all, delete-orphan")


class EmbeddingVector(TypeDecorator):
    """A float vector: pgvector ``vector`` on PostgreSQL, a JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in value]


def work_key_for(external_id: str | None, title: str | None) -> str:
    """Identity of a work across sessions: its DOI / arXiv id, else a title hash."""
    if external_id:
        return external_id[:500]
    normalised = " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))
    return "title:" + hashlib.sha1(normalised.encode()).hexdigest()


class Work(Base):
    """A paper, stored once for every session and user that finds it. Summaries,
    citations and the embedding hang off the work, so they are computed once."""

    __tablename__ = "works"
    __table_args__ = (Index("uq_works_work_key", "work_key", unique=True),)

    id = Column(String, primary_key=True, default=generate_uuid)
    work_key = Column(String(600), nullable=False)
    title = Column(String, nullable=False)
    authors = Column(JSON, nullable=False, default=list)
    year = Column(Integer, nullable=True)
    abstract = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    citation_count = Column(Integer, nullable=True)
    external_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False)
    venue = Column(String, nullable=True)
    embedding = Column(EmbeddingVector, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    summary = relationship(
        "Summary", back_populates="work", uselist=False, cascade="all, delete-orphan"
    )
    citation = relationship(
        "Citation", back_populates="work", uselist=False, cascade="all, delete-orphan"
    )


class Paper(Base):
    """A work as it appears in one session (with that session's score and notes)."""

    __tablename__ = "papers"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    work_id = Column(String, ForeignKey("works.id"), nullable=False, index=True)
    relevance_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_papers_session_created", "session_id", "created_at"),
        Index("uq_papers_session_work", "session_id", "work_id", unique=True),
    )

    session = relationship("Session", back_populates="papers")
    work = relationship("Work", lazy="joined", innerjoin=True)
    notes = relationship("Note", back_populates="paper", cascade="all, delete-orphan")

    # Read-through to the shared work, so API schemas and agents see a flat paper.
    title = property(lambda self: self.work.title)
    authors = property(lambda self: self.work.authors or [])
    year = property(lambda self: self.work.year)
    abstract = property(lambda self: self.work.abstract)
    source_url = property(lambda self: self.work.source_url)
    citation_count = property(lambda self: self.work.citation_count)
    external_id = property(lambda self: self.work.external_id)
    source = property(lambda self: self.work.source)
    venue = property(lambda self: self.work.venue)
    summary = property(lambda self: self.work.summary)
    citation = property(lambda self: self.work.citation)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    analysis_type = Column(String, nullable=False)
    data_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("uq_analyses_session_type", "session_id", "analysis_type", unique=True),
    )

    session = relationship("Session", back_populates="analyses")


class Summary(Base):
    __tablename__ = "summaries"

    __table_args__ = (Index("uq_summaries_work_id", "work_id", unique=True),)

    id = Column(String, primary_key=True, default=generate_uuid)
    work_id = Column(String, ForeignKey("works.id"), nullable=False)
    abstract_compression = Column(Text, nullable=True)
    key_contributions = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    generated_by = Column(String(20), nullable=True)  # "llm" | "extractive"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    work = relationship("Work", back_populates="summary")


class Synthesis(Base):
    __tablename__ = "syntheses"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    paper_ids = Column(JSON, nullable=False, default=list)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="syntheses")


class Citation(Base):
    __tablename__ = "citations"

    __table_args__ = (Index("uq_citations_work_id", "work_id", unique=True),)

    id = Column(String, primary_key=True, default=generate_uuid)
    work_id = Column(String, ForeignKey("works.id"), nullable=False)
    apa = Column(Text, nullable=True)
    mla = Column(Text, nullable=True)
    ieee = Column(Text, nullable=True)
    chicago = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    work = relationship("Work", back_populates="citation")


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=generate_uuid)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False, index=True)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    paper = relationship("Paper", back_populates="notes")


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    conflict_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    analysis_insight = Column(Text, nullable=True)
    summarization_insight = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_conflicts_session_severity", "session_id", "severity"),
        Index("idx_conflicts_session_resolved", "session_id", "resolved"),
    )

    session = relationship("Session", back_populates="conflicts")


class ScheduledDigest(Base):
    __tablename__ = "scheduled_digests"

    __table_args__ = (Index("idx_digests_user_created", "user_id", "created_at"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    frequency = Column(String, nullable=False, default="weekly")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    notify_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    runs = relationship(
        "DigestRun", back_populates="scheduled_digest", cascade="all, delete-orphan"
    )


class DigestRun(Base):
    __tablename__ = "digest_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    scheduled_digest_id = Column(
        String, ForeignKey("scheduled_digests.id"), nullable=False, index=True
    )
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True, index=True)
    query = Column(String, nullable=False)
    new_papers_count = Column(Integer, default=0)
    new_paper_ids = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_digest_runs_sched_status", "scheduled_digest_id", "status"),
        Index("idx_digest_runs_sched_created", "scheduled_digest_id", "created_at"),
    )

    scheduled_digest = relationship("ScheduledDigest", back_populates="runs")
    session = relationship("Session", back_populates="digest_runs")


class Roadmap(Base):
    __tablename__ = "roadmaps"

    __table_args__ = (Index("uq_roadmaps_session_id", "session_id", unique=True),)

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    foundational_papers_json = Column(JSON, nullable=False)
    gap_areas_json = Column(JSON, nullable=False)
    next_queries_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="roadmaps")


class SourceCacheEntry(Base):
    """Cached result of one discovery-source request, shared by every process."""

    __tablename__ = "source_cache"

    key = Column(String(64), primary_key=True)  # sha256 of source + normalised request
    source = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OrchestrationJob(Base):
    """One background agent run. Its trace is updated live; the result lives in the
    session's tables once the job completes."""

    __tablename__ = "orchestration_jobs"
    __table_args__ = (
        Index("idx_jobs_session_created", "session_id", "created_at"),
        Index("idx_jobs_user_status", "user_id", "status"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(String, nullable=False)
    kind = Column(String(20), nullable=False, default="search")  # search | followup
    query = Column(String, nullable=False)
    page = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="queued")  # queued|running|completed|failed
    trace = Column(JSON, nullable=False, default=list)
    error = Column(Text, nullable=True)
    conflict_summary = Column(Text, nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="jobs")
