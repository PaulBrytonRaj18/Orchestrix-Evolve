from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    papers = relationship(
        "Paper", back_populates="session", cascade="all, delete-orphan"
    )
    analyses = relationship(
        "Analysis", back_populates="session", cascade="all, delete-orphan"
    )
    syntheses = relationship(
        "Synthesis", back_populates="session", cascade="all, delete-orphan"
    )


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    title = Column(String, nullable=False)
    authors = Column(JSON, nullable=False, default=list)
    year = Column(Integer, nullable=True)
    abstract = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    citation_count = Column(Integer, nullable=True)
    relevance_score = Column(Float, nullable=True)
    external_id = Column(String, nullable=True)
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
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
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
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
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
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
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
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
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
    paper_id = Column(String, ForeignKey("papers.id"), nullable=False)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    paper = relationship("Paper", back_populates="notes")
