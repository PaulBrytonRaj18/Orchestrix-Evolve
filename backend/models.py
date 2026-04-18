from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from database import Base


def generate_uuid():
    return str(uuid.uuid4())


class DigestFrequency(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    digests = relationship(
        "ScheduledDigest", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="sessions")
    papers = relationship(
        "Paper", back_populates="session", cascade="all, delete-orphan"
    )
    analyses = relationship(
        "Analysis", back_populates="session", cascade="all, delete-orphan"
    )
    syntheses = relationship(
        "Synthesis", back_populates="session", cascade="all, delete-orphan"
    )
    conflicts = relationship(
        "Conflict", back_populates="session", cascade="all, delete-orphan"
    )
    roadmaps = relationship(
        "Roadmap", back_populates="session", cascade="all, delete-orphan"
    )
    digest_runs = relationship(
        "DigestRun", back_populates="session", cascade="all, delete-orphan"
    )


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    authors = Column(JSON, nullable=False, default=list)
    year = Column(Integer, nullable=True)
    abstract = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    citation_count = Column(Integer, nullable=True)
    relevance_score = Column(Float, nullable=True)
    external_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session = relationship("Session", back_populates="papers")
    summary = relationship(
        "Summary", back_populates="paper", uselist=False, cascade="all, delete-orphan"
    )
    citation = relationship(
        "Citation", back_populates="paper", uselist=False, cascade="all, delete-orphan"
    )
    notes = relationship("Note", back_populates="paper", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    analysis_type = Column(String, nullable=False)
    data_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session = relationship("Session", back_populates="analyses")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False, index=True)
    abstract_compression = Column(Text, nullable=True)
    key_contributions = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paper = relationship("Paper", back_populates="summary")


class Synthesis(Base):
    __tablename__ = "syntheses"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    paper_ids = Column(JSON, nullable=False, default=list)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session = relationship("Session", back_populates="syntheses")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(String, primary_key=True, default=generate_uuid)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False, index=True)
    apa = Column(Text, nullable=True)
    mla = Column(Text, nullable=True)
    ieee = Column(Text, nullable=True)
    chicago = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paper = relationship("Paper", back_populates="citation")


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=generate_uuid)
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False, index=True)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

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
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session = relationship("Session", back_populates="conflicts")


class ScheduledDigest(Base):
    __tablename__ = "scheduled_digests"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    frequency = Column(String, nullable=False, default="weekly")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    notify_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="digests")
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
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scheduled_digest = relationship("ScheduledDigest", back_populates="runs")
    session = relationship("Session", back_populates="digest_runs")


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    foundational_papers_json = Column(JSON, nullable=False)
    gap_areas_json = Column(JSON, nullable=False)
    next_queries_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session = relationship("Session", back_populates="roadmaps")
