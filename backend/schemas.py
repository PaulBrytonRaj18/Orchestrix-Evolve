from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class SessionCreate(BaseModel):
    name: str
    query: str


class SessionResponse(BaseModel):
    id: str
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    paper_count: Optional[int] = 0

    class Config:
        from_attributes = True


class PaperBase(BaseModel):
    title: str
    authors: List[str]
    year: Optional[int] = None
    abstract: Optional[str] = None
    source_url: Optional[str] = None
    citation_count: Optional[int] = None
    relevance_score: Optional[float] = None
    external_id: Optional[str] = None
    source: str


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
    paper_ids: List[str]
    content: Optional[str] = None
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
    content: str


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
    resolution_notes: str


class ScheduledDigestCreate(BaseModel):
    name: str
    query: str
    frequency: str = Field(
        default="weekly", pattern="^(daily|weekly|biweekly|monthly)$"
    )
    notify_email: Optional[str] = None


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
