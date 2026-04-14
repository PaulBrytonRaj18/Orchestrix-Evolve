from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from database import get_db, init_db
from models import (
    Session as SessionModel,
    Paper,
    Analysis,
    Summary,
    Synthesis,
    Citation,
    Note,
    Conflict,
    ScheduledDigest,
    DigestRun,
    Roadmap,
)
from schemas import (
    SessionCreate,
    SessionResponse,
    SessionFullResponse,
    PaperResponse,
    PaperWithDetails,
    AnalysisResponse,
    SummaryResponse,
    SynthesisResponse,
    CitationResponse,
    NoteCreate,
    NoteResponse,
    OrchestrateResponse,
    HealthResponse,
    ConflictResponse,
    ConflictResolve,
    ScheduledDigestCreate,
    ScheduledDigestResponse,
    DigestRunResponse,
    ScheduledDigestWithRuns,
    ConflictDetectionResult,
    RoadmapResponse,
)
from orchestrator import orchestrate
from agents import summarizer, conflict_detector, digest_scheduler, roadmap
from scheduler import scheduler

load_dotenv()

app = FastAPI(title="Orchestrix API", version="2.0.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.stop()


@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionResponse)
def create_session(session: SessionCreate, db: Session = Depends(get_db)):
    db_session = SessionModel(name=session.name, query=session.query)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return SessionResponse(
        id=db_session.id,
        name=db_session.name,
        query=db_session.query,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        paper_count=0,
    )


@app.get("/sessions", response_model=List[SessionResponse])
def get_sessions(db: Session = Depends(get_db)):
    sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
    result = []
    for s in sessions:
        paper_count = db.query(Paper).filter(Paper.session_id == s.id).count()
        result.append(
            SessionResponse(
                id=s.id,
                name=s.name,
                query=s.query,
                created_at=s.created_at,
                updated_at=s.updated_at,
                paper_count=paper_count,
            )
        )
    return result


@app.get("/sessions/{session_id}", response_model=SessionFullResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    analyses = db.query(Analysis).filter(Analysis.session_id == session_id).all()
    syntheses = db.query(Synthesis).filter(Synthesis.session_id == session_id).all()
    conflicts = db.query(Conflict).filter(Conflict.session_id == session_id).all()

    papers_with_details = []
    for paper in papers:
        summary = db.query(Summary).filter(Summary.paper_id == paper.id).first()
        citation = db.query(Citation).filter(Citation.paper_id == paper.id).first()
        notes = db.query(Note).filter(Note.paper_id == paper.id).all()

        papers_with_details.append(
            PaperWithDetails(
                id=paper.id,
                session_id=paper.session_id,
                title=paper.title,
                authors=paper.authors,
                year=paper.year,
                abstract=paper.abstract,
                source_url=paper.source_url,
                citation_count=paper.citation_count,
                relevance_score=paper.relevance_score,
                external_id=paper.external_id,
                source=paper.source,
                created_at=paper.created_at,
                updated_at=paper.updated_at,
                summary=SummaryResponse(
                    id=summary.id,
                    paper_id=summary.paper_id,
                    abstract_compression=summary.abstract_compression,
                    key_contributions=summary.key_contributions,
                    methodology=summary.methodology,
                    limitations=summary.limitations,
                    created_at=summary.created_at,
                    updated_at=summary.updated_at,
                )
                if summary
                else None,
                citation=CitationResponse(
                    id=citation.id,
                    paper_id=citation.paper_id,
                    apa=citation.apa,
                    mla=citation.mla,
                    ieee=citation.ieee,
                    chicago=citation.chicago,
                    created_at=citation.created_at,
                    updated_at=citation.updated_at,
                )
                if citation
                else None,
                notes=[
                    NoteResponse(
                        id=n.id,
                        paper_id=n.paper_id,
                        content=n.content,
                        created_at=n.created_at,
                        updated_at=n.updated_at,
                    )
                    for n in notes
                ],
            )
        )

    return SessionFullResponse(
        id=db_session.id,
        name=db_session.name,
        query=db_session.query,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        papers=papers_with_details,
        analyses=[
            AnalysisResponse(
                id=a.id,
                session_id=a.session_id,
                analysis_type=a.analysis_type,
                data_json=a.data_json,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in analyses
        ],
        syntheses=[
            SynthesisResponse(
                id=s.id,
                session_id=s.session_id,
                paper_ids=s.paper_ids,
                content=s.content,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in syntheses
        ],
        conflicts=[
            ConflictResponse(
                id=c.id,
                session_id=c.session_id,
                conflict_type=c.conflict_type,
                severity=c.severity,
                title=c.title,
                description=c.description,
                analysis_insight=c.analysis_insight,
                summarization_insight=c.summarization_insight,
                resolved=c.resolved,
                resolution_notes=c.resolution_notes,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in conflicts
        ],
    )


@app.post("/sessions/{session_id}/orchestrate", response_model=OrchestrateResponse)
async def run_orchestration(
    session_id: str,
    page: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await orchestrate(db_session.query, session_id, page)

    papers_data = result["papers"]
    papers_with_details = []

    logger.info(f"Processing {len(papers_data)} papers for session {session_id}")
    for i, paper_data in enumerate(papers_data[:3]):
        logger.info(f"Paper {i}: '{paper_data.get('title', 'Unknown')[:50]}...' - citation_count={paper_data.get('citation_count')}, source={paper_data.get('source')}")

    for paper_data in papers_data:
        existing_paper = (
            db.query(Paper)
            .filter(
                Paper.session_id == session_id,
                Paper.external_id == paper_data.get("external_id"),
            )
            .first()
        )

        if existing_paper:
            existing_paper.title = paper_data.get("title", existing_paper.title)
            existing_paper.authors = paper_data.get("authors", existing_paper.authors)
            existing_paper.year = paper_data.get("year", existing_paper.year)
            existing_paper.abstract = paper_data.get(
                "abstract", existing_paper.abstract
            )
            existing_paper.source_url = paper_data.get(
                "source_url", existing_paper.source_url
            )
            existing_paper.citation_count = paper_data.get(
                "citation_count", existing_paper.citation_count
            )
            existing_paper.relevance_score = paper_data.get(
                "relevance_score", existing_paper.relevance_score
            )
            db.commit()
            db.refresh(existing_paper)
            paper = existing_paper
            logger.info(f"Updated paper {paper.id}: citation_count={paper.citation_count}")
        else:
            paper = Paper(
                session_id=session_id,
                title=paper_data.get("title", ""),
                authors=paper_data.get("authors", []),
                year=paper_data.get("year"),
                abstract=paper_data.get("abstract"),
                source_url=paper_data.get("source_url"),
                citation_count=paper_data.get("citation_count"),
                relevance_score=paper_data.get("relevance_score"),
                external_id=paper_data.get("external_id"),
                source=paper_data.get("source", "unknown"),
            )
            db.add(paper)
            db.commit()
            db.refresh(paper)
            logger.info(f"Created paper {paper.id}: citation_count={paper.citation_count}")

        citations_data = paper_data.get("citation", {})
        existing_citation = (
            db.query(Citation).filter(Citation.paper_id == paper.id).first()
        )
        if existing_citation:
            existing_citation.apa = citations_data.get("apa", "")
            existing_citation.mla = citations_data.get("mla", "")
            existing_citation.ieee = citations_data.get("ieee", "")
            existing_citation.chicago = citations_data.get("chicago", "")
        else:
            citation = Citation(
                paper_id=paper.id,
                apa=citations_data.get("apa", ""),
                mla=citations_data.get("mla", ""),
                ieee=citations_data.get("ieee", ""),
                chicago=citations_data.get("chicago", ""),
            )
            db.add(citation)

        # summaries returned by the summarizer are nested structures.
        # map derived_content/inferred_content into our Summary model fields.
        summaries_data = result.get("summaries", [])
        # Each summary corresponds to a paper in the same order as `papers_data`.
        # Use index of the current paper to pick the matching summary if possible.
        try:
            idx = papers_data.index(paper_data)
        except ValueError:
            idx = None

        # pick the matching summary if available, otherwise fall back to iterating
        matching_summary = None
        if idx is not None and idx < len(summaries_data):
            matching_summary = summaries_data[idx]
        else:
            # try to pick a summary that looks like a dict
            for s in summaries_data:
                if isinstance(s, dict):
                    matching_summary = s
                    break

        if isinstance(matching_summary, dict):
            derived = matching_summary.get("derived_content", {}) or {}
            inferred = matching_summary.get("inferred_content", {}) or {}

            abstract_compression = derived.get("abstract_compression", "")
            # key_points may be a list or a string
            kp = derived.get("key_points", "")
            if isinstance(kp, list):
                key_contributions = "\n".join(str(x) for x in kp)
            else:
                key_contributions = str(kp or "")

            methodology = inferred.get("explanation_approach", "") or derived.get("methodology", "")
            limitations = inferred.get("limitations", "")

            existing_summary = (
                db.query(Summary).filter(Summary.paper_id == paper.id).first()
            )
            if existing_summary:
                existing_summary.abstract_compression = abstract_compression
                existing_summary.key_contributions = key_contributions
                existing_summary.methodology = methodology
                existing_summary.limitations = limitations
            else:
                summary = Summary(
                    paper_id=paper.id,
                    abstract_compression=abstract_compression,
                    key_contributions=key_contributions,
                    methodology=methodology,
                    limitations=limitations,
                )
                db.add(summary)

        db.commit()

        paper_obj = db.query(Paper).filter(Paper.id == paper.id).first()
        summary_obj = db.query(Summary).filter(Summary.paper_id == paper.id).first()
        citation_obj = db.query(Citation).filter(Citation.paper_id == paper.id).first()
        logger.info(f"Returning paper {paper_obj.id}: citation_count={paper_obj.citation_count}")

        papers_with_details.append(
            PaperWithDetails(
                id=paper_obj.id,
                session_id=paper_obj.session_id,
                title=paper_obj.title,
                authors=paper_obj.authors,
                year=paper_obj.year,
                abstract=paper_obj.abstract,
                source_url=paper_obj.source_url,
                citation_count=paper_obj.citation_count,
                relevance_score=paper_obj.relevance_score,
                external_id=paper_obj.external_id,
                source=paper_obj.source,
                created_at=paper_obj.created_at,
                updated_at=paper_obj.updated_at,
                summary=SummaryResponse(
                    id=summary_obj.id,
                    paper_id=summary_obj.paper_id,
                    abstract_compression=summary_obj.abstract_compression,
                    key_contributions=summary_obj.key_contributions,
                    methodology=summary_obj.methodology,
                    limitations=summary_obj.limitations,
                    created_at=summary_obj.created_at,
                    updated_at=summary_obj.updated_at,
                )
                if summary_obj
                else None,
                citation=CitationResponse(
                    id=citation_obj.id,
                    paper_id=citation_obj.paper_id,
                    apa=citation_obj.apa,
                    mla=citation_obj.mla,
                    ieee=citation_obj.ieee,
                    chicago=citation_obj.chicago,
                    created_at=citation_obj.created_at,
                    updated_at=citation_obj.updated_at,
                )
                if citation_obj
                else None,
                notes=[],
            )
        )

    if result["analysis"]:
        analysis_types = [
            "publication_trend",
            "top_authors",
            "keyword_frequency",
            "citation_distribution",
            "emerging_topics",
        ]
        for atype in analysis_types:
            if atype in result["analysis"]:
                existing = (
                    db.query(Analysis)
                    .filter(
                        Analysis.session_id == session_id,
                        Analysis.analysis_type == atype,
                    )
                    .first()
                )
                if existing:
                    existing.data_json = result["analysis"][atype]
                else:
                    analysis = Analysis(
                        session_id=session_id,
                        analysis_type=atype,
                        data_json=result["analysis"][atype],
                    )
                    db.add(analysis)
        db.commit()

    if result.get("conflicts"):
        for conflict_data in result["conflicts"]:
            conflict = Conflict(
                session_id=session_id,
                conflict_type=conflict_data.get("conflict_type", "unknown"),
                severity=conflict_data.get("severity", "medium"),
                title=conflict_data.get("title", "Untitled Conflict"),
                description=conflict_data.get("description"),
                analysis_insight=conflict_data.get("analysis_insight"),
                summarization_insight=conflict_data.get("summarization_insight"),
                resolved=False,
            )
            db.add(conflict)
        db.commit()

    return OrchestrateResponse(
        papers=papers_with_details,
        analysis=result["analysis"],
        citations=result["citations"],
        summaries=result["summaries"],
        trace=result["trace"],
        conflicts=result.get("conflicts", []),
    )


@app.get("/sessions/{session_id}/conflicts", response_model=List[ConflictResponse])
def get_session_conflicts(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    conflicts = db.query(Conflict).filter(Conflict.session_id == session_id).all()
    return [
        ConflictResponse(
            id=c.id,
            session_id=c.session_id,
            conflict_type=c.conflict_type,
            severity=c.severity,
            title=c.title,
            description=c.description,
            analysis_insight=c.analysis_insight,
            summarization_insight=c.summarization_insight,
            resolved=c.resolved,
            resolution_notes=c.resolution_notes,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conflicts
    ]


@app.post("/sessions/{session_id}/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    session_id: str,
    conflict_id: str,
    resolution: ConflictResolve,
    db: Session = Depends(get_db),
):
    conflict = (
        db.query(Conflict)
        .filter(Conflict.id == conflict_id, Conflict.session_id == session_id)
        .first()
    )
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")

    conflict.resolved = True
    conflict.resolution_notes = resolution.resolution_notes
    db.commit()

    return {"status": "resolved", "conflict_id": conflict_id}


@app.post(
    "/sessions/{session_id}/detect-conflicts", response_model=ConflictDetectionResult
)
async def detect_conflicts(
    session_id: str,
    db: Session = Depends(get_db),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    analyses = db.query(Analysis).filter(Analysis.session_id == session_id).all()

    if not papers:
        raise HTTPException(status_code=400, detail="No papers in session")

    analysis_data = {}
    for a in analyses:
        analysis_data[a.analysis_type] = a.data_json

    papers_data = []
    summaries_data = []
    for paper in papers:
        papers_data.append(
            {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "year": paper.year,
            }
        )
        summary = db.query(Summary).filter(Summary.paper_id == paper.id).first()
        summaries_data.append(
            {
                "abstract_compression": summary.abstract_compression
                if summary
                else None,
                "key_contributions": summary.key_contributions if summary else None,
                "methodology": summary.methodology if summary else None,
                "limitations": summary.limitations if summary else None,
            }
        )

    result = await conflict_detector.detect_conflicts(
        papers_data, analysis_data, summaries_data
    )

    for conflict_data in result.get("conflicts", []):
        existing = (
            db.query(Conflict)
            .filter(
                Conflict.session_id == session_id,
                Conflict.title == conflict_data.get("title"),
                Conflict.conflict_type == conflict_data.get("conflict_type"),
            )
            .first()
        )
        if not existing:
            conflict = Conflict(
                session_id=session_id,
                conflict_type=conflict_data.get("conflict_type", "unknown"),
                severity=conflict_data.get("severity", "medium"),
                title=conflict_data.get("title", "Untitled Conflict"),
                description=conflict_data.get("description"),
                analysis_insight=conflict_data.get("analysis_insight"),
                summarization_insight=conflict_data.get("summarization_insight"),
                resolved=False,
            )
            db.add(conflict)
    db.commit()

    return ConflictDetectionResult(
        conflicts=result.get("conflicts", []),
        summary=result.get("summary", "No conflicts detected"),
    )


@app.patch("/papers/{paper_id}/note", response_model=NoteResponse)
def update_note(paper_id: str, note: NoteCreate, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    existing_note = db.query(Note).filter(Note.paper_id == paper_id).first()
    if existing_note:
        existing_note.content = note.content
        db.commit()
        db.refresh(existing_note)
        return NoteResponse(
            id=existing_note.id,
            paper_id=existing_note.paper_id,
            content=existing_note.content,
            created_at=existing_note.created_at,
            updated_at=existing_note.updated_at,
        )
    else:
        new_note = Note(paper_id=paper_id, content=note.content)
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        return NoteResponse(
            id=new_note.id,
            paper_id=new_note.paper_id,
            content=new_note.content,
            created_at=new_note.created_at,
            updated_at=new_note.updated_at,
        )


@app.post("/sessions/{session_id}/synthesize")
def synthesize_papers(
    session_id: str, paper_ids: List[str], db: Session = Depends(get_db)
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="No papers found")

    papers_dict = []
    for p in papers:
        papers_dict.append(
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract,
            }
        )

    import asyncio

    synthesis_text = asyncio.run(summarizer.synthesize_papers(papers_dict))

    synthesis = Synthesis(
        session_id=session_id, paper_ids=paper_ids, content=synthesis_text
    )
    db.add(synthesis)
    db.commit()
    db.refresh(synthesis)

    return {"id": synthesis.id, "content": synthesis_text}


@app.get("/sessions/{session_id}/export/bib")
def export_bib(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()

    bib_entries = []
    for paper in papers:
        first_author = paper.authors[0].split()[-1] if paper.authors else "Unknown"
        citekey = (
            f"{first_author}{paper.year}" if paper.year else f"{first_author}unknown"
        )
        citekey = citekey.replace(" ", "").replace(",", "")

        author_str = " and ".join(paper.authors) if paper.authors else "Unknown"

        bib_entry = f"""@article{{{citekey},
  title = {{{paper.title}}},
  author = {{{author_str}}},
  year = {{{paper.year or "n.d."}}},
  url = {{{paper.source_url or ""}}}
}}"""
        bib_entries.append(bib_entry)

    bib_content = "\n\n".join(bib_entries)

    return Response(
        content=bib_content,
        media_type="application/x-bibtex",
        headers={
            "Content-Disposition": f"attachment; filename=orchestrix_{session_id[:8]}.bib"
        },
    )


@app.get("/sessions/{session_id}/export/txt")
def export_txt(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    citations = (
        db.query(Citation).filter(Citation.paper_id.in_([p.id for p in papers])).all()
    )
    citation_map = {c.paper_id: c for c in citations}

    lines = []
    for paper in papers:
        citation = citation_map.get(paper.id)
        if citation and citation.apa:
            lines.append(citation.apa)
        else:
            author_str = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
            if len(paper.authors) > 3:
                author_str += ", et al."
            lines.append(f"{author_str} ({paper.year or 'n.d.'}). {paper.title}.")

    txt_content = "\n\n".join(lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=orchestrix_{session_id[:8]}.txt"
        },
    )


@app.post("/digests", response_model=ScheduledDigestResponse)
async def create_digest(digest: ScheduledDigestCreate, db: Session = Depends(get_db)):
    is_valid, error = await digest_scheduler.verify_query_syntax(digest.query)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    from agents.digest_scheduler import calculate_next_run

    now = datetime.now(timezone.utc)
    next_run = calculate_next_run(now, digest.frequency)

    db_digest = ScheduledDigest(
        name=digest.name,
        query=digest.query,
        frequency=digest.frequency,
        notify_email=digest.notify_email,
        next_run_at=next_run,
        is_active=True,
    )
    db.add(db_digest)
    db.commit()
    db.refresh(db_digest)

    scheduler.add_job(str(db_digest.id), db_digest.query, next_run)

    return ScheduledDigestResponse(
        id=db_digest.id,
        name=db_digest.name,
        query=db_digest.query,
        frequency=db_digest.frequency,
        last_run_at=db_digest.last_run_at,
        next_run_at=db_digest.next_run_at,
        is_active=db_digest.is_active,
        notify_email=db_digest.notify_email,
        created_at=db_digest.created_at,
        updated_at=db_digest.updated_at,
    )


@app.get("/digests", response_model=List[ScheduledDigestResponse])
def get_digests(db: Session = Depends(get_db)):
    digests = (
        db.query(ScheduledDigest).order_by(ScheduledDigest.created_at.desc()).all()
    )
    return [
        ScheduledDigestResponse(
            id=d.id,
            name=d.name,
            query=d.query,
            frequency=d.frequency,
            last_run_at=d.last_run_at,
            next_run_at=d.next_run_at,
            is_active=d.is_active,
            notify_email=d.notify_email,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in digests
    ]


@app.get("/digests/{digest_id}", response_model=ScheduledDigestWithRuns)
def get_digest(digest_id: str, db: Session = Depends(get_db)):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    runs = (
        db.query(DigestRun)
        .filter(DigestRun.scheduled_digest_id == digest_id)
        .order_by(DigestRun.created_at.desc())
        .limit(20)
        .all()
    )

    return ScheduledDigestWithRuns(
        id=digest.id,
        name=digest.name,
        query=digest.query,
        frequency=digest.frequency,
        last_run_at=digest.last_run_at,
        next_run_at=digest.next_run_at,
        is_active=digest.is_active,
        notify_email=digest.notify_email,
        created_at=digest.created_at,
        updated_at=digest.updated_at,
        runs=[
            DigestRunResponse(
                id=r.id,
                scheduled_digest_id=r.scheduled_digest_id,
                session_id=r.session_id,
                query=r.query,
                new_papers_count=r.new_papers_count,
                new_paper_ids=r.new_paper_ids,
                status=r.status,
                error_message=r.error_message,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in runs
        ],
    )


@app.delete("/digests/{digest_id}")
def delete_digest(digest_id: str, db: Session = Depends(get_db)):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    scheduler.remove_job(digest_id)

    db.delete(digest)
    db.commit()

    return {"status": "deleted", "digest_id": digest_id}


@app.patch("/digests/{digest_id}/toggle")
def toggle_digest(digest_id: str, db: Session = Depends(get_db)):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    digest.is_active = not digest.is_active

    if digest.is_active and digest.next_run_at:
        scheduler.add_job(digest_id, digest.query, digest.next_run_at)
    else:
        scheduler.remove_job(digest_id)

    db.commit()

    return {
        "status": "updated",
        "digest_id": digest_id,
        "is_active": digest.is_active,
    }


@app.post("/digests/{digest_id}/run")
def trigger_digest_run(digest_id: str, db: Session = Depends(get_db)):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    scheduler.trigger_manual_run(digest_id)

    return {"status": "triggered", "digest_id": digest_id}


@app.get("/digests/{digest_id}/preview")
async def preview_digest(digest_id: str, db: Session = Depends(get_db)):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.query == digest.query)
        .order_by(SessionModel.created_at.desc())
        .first()
    )

    existing_ids = []
    if sessions:
        existing_papers = db.query(Paper).filter(Paper.session_id == sessions.id).all()
        existing_ids = [p.external_id for p in existing_papers if p.external_id]

    result = await digest_scheduler.run_digest(
        query=digest.query,
        last_run_at=digest.last_run_at,
        existing_external_ids=existing_ids,
        limit=20,
    )

    return {
        "query": digest.query,
        "threshold_date": result.get("threshold_date"),
        "new_papers_preview": result.get("new_papers", [])[:5],
        "total_new_count": result.get("total_new", 0),
        "is_first_run": result.get("is_first_run", True),
    }


@app.post("/sessions/{session_id}/roadmap", response_model=RoadmapResponse)
async def generate_roadmap(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    analyses = db.query(Analysis).filter(Analysis.session_id == session_id).all()
    conflicts = db.query(Conflict).filter(Conflict.session_id == session_id).all()

    if not papers:
        raise HTTPException(status_code=400, detail="No papers in session")

    papers_data = [
        {
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "abstract": p.abstract,
            "citation_count": p.citation_count
        }
        for p in papers
    ]

    analysis_trend_data = {}
    for a in analyses:
        analysis_trend_data[a.analysis_type] = a.data_json

    summaries_data = []
    for p in papers:
        summary = db.query(Summary).filter(Summary.paper_id == p.id).first()
        if summary:
            summaries_data.append({
                "abstract_compression": summary.abstract_compression,
                "key_contributions": summary.key_contributions,
                "methodology": summary.methodology,
                "limitations": summary.limitations
            })

    notes_data = []
    for p in papers:
        notes = db.query(Note).filter(Note.paper_id == p.id).all()
        notes_data.extend([{"paper_id": n.paper_id, "content": n.content} for n in notes])

    result = await roadmap.run(
        papers=papers_data,
        analysis_trend_data=analysis_trend_data,
        summaries=summaries_data,
        notes=notes_data,
        conflicts=[
            {"title": c.title, "description": c.description, "severity": c.severity}
            for c in conflicts
        ],
        session_id=session_id
    )

    db_roadmap = Roadmap(
        session_id=session_id,
        foundational_papers_json=result["foundational_papers"],
        gap_areas_json=result["gap_areas"],
        next_queries_json=result["next_query_suggestions"]
    )
    db.add(db_roadmap)
    db.commit()

    return RoadmapResponse(**result)


@app.get("/sessions/{session_id}/roadmap", response_model=RoadmapResponse)
def get_roadmap(session_id: str, db: Session = Depends(get_db)):
    db_roadmap = db.query(Roadmap).filter(Roadmap.session_id == session_id).order_by(Roadmap.created_at.desc()).first()
    if not db_roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    return RoadmapResponse(
        foundational_papers=db_roadmap.foundational_papers_json,
        gap_areas=db_roadmap.gap_areas_json,
        next_query_suggestions=db_roadmap.next_queries_json
    )


@app.post("/sessions/{session_id}/roadmap/query")
async def execute_roadmap_query(
    session_id: str,
    query: str,
    db: Session = Depends(get_db)
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await orchestrate(query, session_id, page=0)

    return {
        "triggered_query": query,
        "orchestration_result": result
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
