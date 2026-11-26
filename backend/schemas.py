"""Pydantic request/response models (Pydantic v2 idioms)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_SPECIAL_CHARS = re.compile(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]")
_DANGEROUS_PATTERNS = ("<script", "javascript:", "onerror=", "onclick=")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Auth ────────────────────────────────────────────────────────────────────


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not _SPECIAL_CHARS.search(v):
            raise ValueError("Password must contain at least one special character")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> UserCreate:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(ORMModel):
    id: str
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse
    # True when Supabase requires e-mail confirmation before a session is issued.
    email_confirmation_required: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


# ─── Sessions & papers ───────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query: str = Field(..., min_length=1, max_length=1000)

    @field_validator("query", "name")
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        lowered = v.lower()
        if any(p in lowered for p in _DANGEROUS_PATTERNS):
            raise ValueError("Invalid input detected")
        v = v.strip()
        if not v:
            raise ValueError("Value must not be blank")
        return v


class SessionResponse(ORMModel):
    id: str
    user_id: str | None = None
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    paper_count: int | None = 0


class PaperBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    authors: list[str] = Field(default_factory=list, max_length=500)
    year: int | None = Field(None, ge=1900, le=2100)
    abstract: str | None = Field(None, max_length=10000)
    source_url: str | None = Field(None, max_length=2000)
    citation_count: int | None = Field(None, ge=0)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    external_id: str | None = Field(None, max_length=500)
    source: str = Field(..., max_length=100)


class PaperResponse(PaperBase, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class SummaryResponse(ORMModel):
    id: str
    paper_id: str
    abstract_compression: str | None = None
    key_contributions: str | None = None
    methodology: str | None = None
    limitations: str | None = None
    created_at: datetime
    updated_at: datetime


class CitationResponse(ORMModel):
    id: str
    paper_id: str
    apa: str | None = Field(None, max_length=4000)
    mla: str | None = Field(None, max_length=4000)
    ieee: str | None = Field(None, max_length=4000)
    chicago: str | None = Field(None, max_length=4000)
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    content: str = Field(..., max_length=10000)


class NoteResponse(ORMModel):
    id: str
    paper_id: str
    content: str = Field(..., max_length=10000)
    created_at: datetime
    updated_at: datetime


class PaperWithDetails(PaperBase, ORMModel):
    id: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    summary: SummaryResponse | None = None
    citation: CitationResponse | None = None
    notes: list[NoteResponse] = Field(default_factory=list)


class AnalysisResponse(ORMModel):
    id: str
    session_id: str
    analysis_type: str
    data_json: Any
    created_at: datetime
    updated_at: datetime


class SynthesizeRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=1, max_length=50)


class SynthesisResponse(ORMModel):
    id: str
    session_id: str
    paper_ids: list[str] = Field(default_factory=list, max_length=100)
    content: str | None = Field(None, max_length=50000)
    created_at: datetime
    updated_at: datetime

    @field_validator("paper_ids", mode="before")
    @classmethod
    def sanitize_paper_ids(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


# ─── Conflicts ───────────────────────────────────────────────────────────────


class ConflictResponse(ORMModel):
    id: str
    session_id: str
    conflict_type: str
    severity: str
    title: str
    description: str | None = None
    analysis_insight: str | None = None
    summarization_insight: str | None = None
    resolved: bool
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ConflictResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=1, max_length=5000)


class ConflictDetectionResult(BaseModel):
    conflicts: list[ConflictResponse]
    summary: str
    stats: dict[str, int] = Field(default_factory=dict)


# ─── Digests ─────────────────────────────────────────────────────────────────


class ScheduledDigestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query: str = Field(..., min_length=1, max_length=1000)
    frequency: Literal["daily", "weekly", "biweekly", "monthly"] = "weekly"
    notify_email: EmailStr | None = None


class ScheduledDigestResponse(ORMModel):
    id: str
    name: str
    query: str
    frequency: str
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    is_active: bool
    notify_email: str | None = None
    created_at: datetime
    updated_at: datetime


class DigestRunResponse(ORMModel):
    id: str
    scheduled_digest_id: str
    session_id: str | None = None
    query: str
    new_papers_count: int
    new_paper_ids: list[str]
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ScheduledDigestWithRuns(ScheduledDigestResponse):
    runs: list[DigestRunResponse] = Field(default_factory=list)


# ─── Roadmap ─────────────────────────────────────────────────────────────────


class FoundationalPaper(BaseModel):
    paper_id: str
    title: str
    reason: str
    citation_count: int
    year: int | None = None
    priority: int


class GapArea(BaseModel):
    question: str
    evidence: str
    related_papers: list[str] = Field(default_factory=list)
    severity: str


class NextQuery(BaseModel):
    query: str
    rationale: str
    trigger_action: str = "discovery"
    expected_insight: str


class RoadmapResponse(BaseModel):
    foundational_papers: list[FoundationalPaper]
    gap_areas: list[GapArea]
    next_query_suggestions: list[NextQuery]


class RoadmapQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


# ─── Orchestration / session views ───────────────────────────────────────────


class SessionFullResponse(BaseModel):
    id: str
    user_id: str | None = None
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    papers: list[PaperWithDetails]
    analyses: list[AnalysisResponse]
    syntheses: list[SynthesisResponse]
    conflicts: list[ConflictResponse] = Field(default_factory=list)


class TraceEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent: str
    status: Literal["running", "done", "skipped", "error"]
    timestamp: str
    duration_ms: int | None = None
    result: str | None = None
    reason: str | None = None
    error: str | None = None


class OrchestrateResponse(BaseModel):
    """Everything the UI needs after a run, read back from the database so every
    paper / summary / citation carries its real, persisted id."""

    papers: list[PaperWithDetails]
    analysis: dict[str, Any] | None
    citations: list[dict[str, Any]]
    summaries: list[SummaryResponse]
    trace: list[TraceEntry]
    conflicts: list[ConflictResponse] = Field(default_factory=list)
    conflict_summary: str | None = None
    roadmap: RoadmapResponse | None = None


class RoadmapQueryResponse(BaseModel):
    triggered_query: str
    orchestration_result: OrchestrateResponse


class HealthResponse(BaseModel):
    status: str
    version: str | None = None
    database: str | None = None
    uptime_seconds: float | None = None
    llm_enabled: bool | None = None
