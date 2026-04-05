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


class SessionFullResponse(BaseModel):
    id: str
    name: str
    query: str
    created_at: datetime
    updated_at: datetime
    papers: List[PaperWithDetails]
    analyses: List[AnalysisResponse]
    syntheses: List[SynthesisResponse]


class OrchestrateResponse(BaseModel):
    papers: List[PaperWithDetails]
    analysis: Optional[dict]
    citations: List[dict]
    summaries: List[dict]
    trace: List[dict]


class HealthResponse(BaseModel):
    status: str


PaperWithDetails.model_rebuild()
