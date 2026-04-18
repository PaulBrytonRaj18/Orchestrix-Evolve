from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    confirm_password: str


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
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8)


class TokenResponse(BaseModel):
    access_token: str
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
                    raise ValueError(f"Invalid input detected")
        return v.strip()


class SessionResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    paper_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PaperBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    authors: List[str] = Field(default_factory=list, max_length=500)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    abstract: Optional[str] = Field(None, max_length=10000)
    source_url: Optional[str] = Field(None, max_length=2000)
    citation_count: Optional[int] = Field(None, ge=0)
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    external_id: Optional[str] = Field(None, max_length=500)
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
    notes: List["NoteResponse"] = []

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
    abstract_compression: Optional[str] = None
    key_contributions: Optional[str] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SynthesisResponse(BaseModel):
    id: str
    session_id: str
    paper_ids: List[str] = Field(default_factory=list, max_length=100)
    content: Optional[str] = Field(None, max_length=50000)
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
    apa: Optional[str] = Field(None, max_length=2000)
    mla: Optional[str] = Field(None, max_length=2000)
    ieee: Optional[str] = Field(None, max_length=2000)
    chicago: Optional[str] = Field(None, max_length=2000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteResponse(BaseModel):
    id: str
    paper_id: str
    content: str = Field(..., max_length=10000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CitationResponse(BaseModel):
    id: str
    paper_id: str
    apa: Optional[str] = None
    mla: Optional[str] = None
    ieee: Optional[str] = None
    chicago: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=0, max_length=10000)


class NoteResponse(BaseModel):
    id: str
    paper_id: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConflictResponse(BaseModel):
    id: str
    session_id: str
    conflict_type: str
    severity: str
    title: str
    description: Optional[str] = None
    analysis_insight: Optional[str] = None
    summarization_insight: Optional[str] = None
    resolved: bool
    resolution_notes: Optional[str] = None
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
    notify_email: Optional[EmailStr] = None


class ScheduledDigestResponse(BaseModel):
    id: str
    name: str
    query: str
    frequency: str
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    is_active: bool
    notify_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DigestRunResponse(BaseModel):
    id: str
    scheduled_digest_id: str
    session_id: Optional[str] = None
    query: str
    new_papers_count: int
    new_paper_ids: List[str]
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduledDigestWithRuns(ScheduledDigestResponse):
    runs: List[DigestRunResponse] = []


class SessionFullResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    papers: List[PaperWithDetails]
    analyses: List[AnalysisResponse]
    syntheses: List[SynthesisResponse]
    conflicts: List[ConflictResponse] = []


class OrchestrateResponse(BaseModel):
    papers: List[PaperWithDetails]
    analysis: Optional[dict]
    citations: List[dict]
    summaries: List[dict]
    trace: List[dict]
    conflicts: List[dict] = []


class HealthResponse(BaseModel):
    status: str


class ConflictDetectionResult(BaseModel):
    conflicts: List[dict]
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
    related_papers: List[str] = []
    severity: str


class NextQuery(BaseModel):
    query: str
    rationale: str
    trigger_action: str = "discovery"
    expected_insight: str


class RoadmapResponse(BaseModel):
    foundational_papers: List[FoundationalPaper]
    gap_areas: List[GapArea]
    next_query_suggestions: List[NextQuery]


PaperWithDetails.model_rebuild()
