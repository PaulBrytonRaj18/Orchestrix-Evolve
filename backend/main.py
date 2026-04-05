from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime
from dotenv import load_dotenv

from database import get_db, init_db
from models import (
    Session as SessionModel,
    Paper,
    Analysis,
    Summary,
    Synthesis,
    Citation,
    Note,
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
)
from orchestrator import orchestrate
from agents import summarizer

load_dotenv()

app = FastAPI(title="Orchestrix API", version="1.0.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = [FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"]

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
    )


@app.post("/sessions/{session_id}/orchestrate", response_model=OrchestrateResponse)
async def run_orchestration(
    session_id: str, page: int = Query(0, ge=0), db: Session = Depends(get_db)
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await orchestrate(db_session.query, session_id, page)

    papers_data = result["papers"]
    papers_with_details = []

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

        summaries_data = result["summaries"]
        for summary_data in summaries_data:
            if not isinstance(summary_data, dict):
                continue
            existing_summary = (
                db.query(Summary).filter(Summary.paper_id == paper.id).first()
            )
            if existing_summary:
                existing_summary.abstract_compression = summary_data.get(
                    "abstract_compression", ""
                )
                existing_summary.key_contributions = summary_data.get(
                    "key_contributions", ""
                )
                existing_summary.methodology = summary_data.get("methodology", "")
                existing_summary.limitations = summary_data.get("limitations", "")
            else:
                summary = Summary(
                    paper_id=paper.id,
                    abstract_compression=summary_data.get("abstract_compression", ""),
                    key_contributions=summary_data.get("key_contributions", ""),
                    methodology=summary_data.get("methodology", ""),
                    limitations=summary_data.get("limitations", ""),
                )
                db.add(summary)

        db.commit()

        paper_obj = db.query(Paper).filter(Paper.id == paper.id).first()
        summary_obj = db.query(Summary).filter(Summary.paper_id == paper.id).first()
        citation_obj = db.query(Citation).filter(Citation.paper_id == paper.id).first()

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

    return OrchestrateResponse(
        papers=papers_with_details,
        analysis=result["analysis"],
        citations=result["citations"],
        summaries=result["summaries"],
        trace=result["trace"],
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

    synthesis_text = asyncio.run(synthesizer.synthesize_papers(papers_dict))

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
