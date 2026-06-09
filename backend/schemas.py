import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
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
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse


class SessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query: str = Field(..., min_length=1, max_length=1000)

    @field_validator("query", "name")
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        if v and len(v) > 0:
            dangerous_patterns = ["<script", "javascript:", "onerror=", "onclick="]
            v_lower = v.lower()
            for pattern in dangerous_patterns:
                if pattern in v_lower:
                    raise ValueError("Invalid input detected")
        return v.strip()


class SessionResponse(BaseModel):
    id: str
    user_id: str | None = None
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    paper_count: int | None = 0

    class Config:
        from_attributes = True


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


class PaperResponse(PaperBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperWithDetails(PaperBase):
    id: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    summary: Optional["SummaryResponse"] = None
    citation: Optional["CitationResponse"] = None
    notes: list["NoteResponse"] = []

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    id: str
    session_id: str
    analysis_type: str
    data_json: Any
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    id: str
    paper_id: str
    abstract_compression: str | None = None
    key_contributions: str | None = None
    methodology: str | None = None
    limitations: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SynthesisResponse(BaseModel):
    id: str
    session_id: str
    paper_ids: list[str] = Field(default_factory=list, max_length=100)
    content: str | None = Field(None, max_length=50000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("paper_ids", mode="before")
    @classmethod
    def sanitize_paper_ids(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


class CitationResponse(BaseModel):
    id: str
    paper_id: str
    apa: str | None = Field(None, max_length=2000)
    mla: str | None = Field(None, max_length=2000)
    ieee: str | None = Field(None, max_length=2000)
    chicago: str | None = Field(None, max_length=2000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=0, max_length=10000)


class NoteResponse(BaseModel):
    id: str
    paper_id: str
    content: str = Field(..., max_length=10000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class ConflictResponse(BaseModel):
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

    class Config:
        from_attributes = True


class ConflictResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=1, max_length=5000)


class ScheduledDigestCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    query: str = Field(..., min_length=1, max_length=1000)
    frequency: str = Field(
        default="weekly", pattern="^(daily|weekly|biweekly|monthly)$"
    )
    notify_email: EmailStr | None = None


class ScheduledDigestResponse(BaseModel):
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

    class Config:
        from_attributes = True


class DigestRunResponse(BaseModel):
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

    class Config:
        from_attributes = True


class ScheduledDigestWithRuns(ScheduledDigestResponse):
    runs: list[DigestRunResponse] = []


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
    conflicts: list[ConflictResponse] = []


class OrchestrateResponse(BaseModel):
    papers: list[PaperWithDetails]
    analysis: dict | None
    citations: list[dict]
    summaries: list[dict]
    trace: list[dict]
    conflicts: list[dict] = []


class HealthResponse(BaseModel):
    status: str
    version: str | None = None
    database: str | None = None
    uptime_seconds: float | None = None


class ConflictDetectionResult(BaseModel):
    conflicts: list[dict]
    summary: str


class FoundationalPaper(BaseModel):
    paper_id: str
    title: str
    reason: str
    citation_count: int
    year: int
    priority: int


class GapArea(BaseModel):
    question: str
    evidence: str
    related_papers: list[str] = []
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


PaperWithDetails.model_rebuild()
