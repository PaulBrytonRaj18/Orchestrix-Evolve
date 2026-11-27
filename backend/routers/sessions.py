"""Research sessions: CRUD, orchestration, conflicts, notes, synthesis, export, roadmap.

Long-running endpoints (orchestrate, synthesize, roadmap query) never hold a DB
connection while agents run: they read what they need, release the session, await
the agents, then persist in a fresh short transaction inside the threadpool.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import claims as claims_agent
from agents import roadmap, summarizer
from auth import get_current_user
from database import get_db, get_db_context
from models import Conflict, Note, Paper, Roadmap, Synthesis
from models import Session as SessionModel
from orchestrator import orchestrate
from schemas import (
    AnswerResponse,
    AskRequest,
    ConflictDetectionResult,
    ConflictResolve,
    ConflictResponse,
    GraphResponse,
    NoteCreate,
    NoteResponse,
    OrchestrateResponse,
    RelatedPapersResponse,
    RoadmapQueryRequest,
    RoadmapQueryResponse,
    RoadmapResponse,
    SessionCreate,
    SessionFullResponse,
    SessionResponse,
    SynthesisResponse,
    SynthesizeRequest,
)
from services import persistence, related

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ─── Helpers ─────────────────────────────────────────────────────────────────


def get_owned_session(db: Session, session_id: str, user_id: str) -> SessionModel:
    """404 for both "missing" and "someone else's" — avoids leaking which ids exist."""
    record = db.get(SessionModel, session_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return record


def _session_response(s: SessionModel, paper_count: int = 0) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        query=s.query,
        created_at=s.created_at,
        updated_at=s.updated_at,
        paper_count=paper_count,
    )


def _read_session_query(session_id: str, user_id: str) -> str:
    with get_db_context() as db:
        return get_owned_session(db, session_id, user_id).query


def _persist_and_view(session_id: str, user_id: str, result: dict[str, Any]) -> dict:
    try:
        return persistence.persist_and_view(session_id, user_id, result)
    except LookupError as exc:  # session deleted while the agents were running
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found") from exc


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _export_name(session_id: str, ext: str) -> str:
    return f"orchestrix_{_FILENAME_SAFE.sub('', session_id)[:8]}.{ext}"


# ─── CRUD ────────────────────────────────────────────────────────────────────


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> SessionResponse:
    record = SessionModel(name=body.name, query=body.query, user_id=user_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _session_response(record)


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[SessionResponse]:
    sessions = db.scalars(
        select(SessionModel)
        .where(SessionModel.user_id == user_id)
        .order_by(SessionModel.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    counts = persistence.paper_counts(db, [s.id for s in sessions])  # one query, not N
    return [_session_response(s, counts.get(s.id, 0)) for s in sessions]


@router.get("/{session_id}", response_model=SessionFullResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> SessionFullResponse:
    record = get_owned_session(db, session_id, user_id)
    papers = persistence.load_papers(db, session_id)
    syntheses = db.scalars(select(Synthesis).where(Synthesis.session_id == session_id)).all()
    conflicts = db.scalars(
        select(Conflict)
        .where(Conflict.session_id == session_id)
        .order_by(Conflict.created_at.desc())
    ).all()
    return SessionFullResponse(
        id=record.id,
        user_id=record.user_id,
        name=record.name,
        query=record.query,
        created_at=record.created_at,
        updated_at=record.updated_at,
        papers=papers,
        analyses=persistence.analysis_responses(db, session_id),
        syntheses=[SynthesisResponse.model_validate(s) for s in syntheses],
        conflicts=[ConflictResponse.model_validate(c) for c in conflicts],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Response:
    db.delete(get_owned_session(db, session_id, user_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Orchestration ───────────────────────────────────────────────────────────


@router.post("/{session_id}/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_session(
    session_id: str,
    page: int = Query(0, ge=0, le=20),
    user_id: str = Depends(get_current_user),
) -> dict:
    query = await run_in_threadpool(_read_session_query, session_id, user_id)
    result = await orchestrate(query, session_id, page=page)
    return await run_in_threadpool(_persist_and_view, session_id, user_id, result)


@router.post("/{session_id}/roadmap/query", response_model=RoadmapQueryResponse)
async def execute_roadmap_query(
    session_id: str,
    query: str | None = Query(None, min_length=1, max_length=1000),
    body: RoadmapQueryRequest | None = None,
    user_id: str = Depends(get_current_user),
) -> dict:
    """Run a suggested follow-up query and add its papers to this session."""
    text = (body.query if body else query) or ""
    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "query is required")
    await run_in_threadpool(_read_session_query, session_id, user_id)  # ownership check
    result = await orchestrate(text.strip(), session_id)
    result["roadmap"] = None  # keep the session's roadmap tied to its main query
    view = await run_in_threadpool(_persist_and_view, session_id, user_id, result)
    return {"triggered_query": text.strip(), "orchestration_result": view}


@router.get("/{session_id}/graph", response_model=GraphResponse, tags=["Graph"])
async def citation_graph(session_id: str, user_id: str = Depends(get_current_user)) -> dict:
    """Who-cites-whom among the session's papers, PageRank, missing key papers, clusters.

    The first call fetches reference lists from OpenAlex (stored on the shared works).
    """
    from services.graph import session_graph

    return await session_graph(session_id, user_id)


@router.post("/{session_id}/ask", response_model=AnswerResponse, tags=["Q&A"])
async def ask(session_id: str, body: AskRequest, user_id: str = Depends(get_current_user)) -> dict:
    """Answer a question from the session's papers, citing the passages used.

    The first question downloads and indexes full texts (arXiv) or abstracts, which
    can take up to a minute; later questions reuse the stored passages.
    """
    from services import qa

    try:
        return await qa.answer(session_id, user_id, body.question.strip())
    except qa.QAUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


# ─── Conflicts ───────────────────────────────────────────────────────────────


@router.get("/{session_id}/conflicts", response_model=list[ConflictResponse], tags=["Conflicts"])
def list_conflicts(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> list[Conflict]:
    get_owned_session(db, session_id, user_id)
    return list(
        db.scalars(
            select(Conflict)
            .where(Conflict.session_id == session_id)
            .order_by(Conflict.created_at.desc())
        )
    )


@router.post("/{session_id}/conflicts/{conflict_id}/resolve", tags=["Conflicts"])
def resolve_conflict(
    session_id: str,
    conflict_id: str,
    body: ConflictResolve,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    get_owned_session(db, session_id, user_id)
    conflict = db.scalar(
        select(Conflict).where(Conflict.id == conflict_id, Conflict.session_id == session_id)
    )
    if conflict is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflict not found")
    conflict.resolved = True
    conflict.resolution_notes = body.resolution_notes
    db.commit()
    return {"status": "resolved", "conflict_id": conflict_id}


@router.post(
    "/{session_id}/detect-conflicts", response_model=ConflictDetectionResult, tags=["Conflicts"]
)
async def detect_conflicts(
    session_id: str, user_id: str = Depends(get_current_user)
) -> ConflictDetectionResult:
    """Re-run detection on stored data; replaces open conflicts, keeps resolved ones."""

    def load() -> dict[str, Any]:
        with get_db_context() as db:
            get_owned_session(db, session_id, user_id)
            return persistence.session_inputs(db, session_id)

    inputs = await run_in_threadpool(load)
    result = await claims_agent.detect_conflicts(inputs["papers"])

    def save() -> list[ConflictResponse]:
        with get_db_context() as db:
            persistence.save_orchestration(
                db, session_id, {"conflicts": result["conflicts"], "claims": result["claims"]}
            )
            db.commit()
            rows = db.scalars(
                select(Conflict)
                .where(Conflict.session_id == session_id)
                .order_by(Conflict.created_at.desc())
            ).all()
            return [ConflictResponse.model_validate(c) for c in rows]

    stored = await run_in_threadpool(save)
    return ConflictDetectionResult(
        conflicts=stored, summary=result["summary"], stats=result.get("stats", {})
    )


# ─── Notes ───────────────────────────────────────────────────────────────────

notes_router = APIRouter(prefix="/papers", tags=["Papers"])


@notes_router.patch("/{paper_id}/note", response_model=NoteResponse)
def update_note(
    paper_id: str,
    body: NoteCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Note:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
    get_owned_session(db, paper.session_id, user_id)
    note = db.scalar(select(Note).where(Note.paper_id == paper_id))
    if note is None:
        note = Note(paper_id=paper_id, content=body.content)
        db.add(note)
    else:
        note.content = body.content
    db.commit()
    db.refresh(note)
    return note


@notes_router.get("/{paper_id}/related", response_model=RelatedPapersResponse)
async def related_papers(
    paper_id: str,
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user),
) -> RelatedPapersResponse:
    """Papers most similar in meaning to this one (embedding nearest neighbours)."""

    def find() -> RelatedPapersResponse:
        with get_db_context() as db:
            paper = db.get(Paper, paper_id)
            if paper is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
            get_owned_session(db, paper.session_id, user_id)
            embedder = related.get_embedder()
            if embedder is None or not embedder.available:
                return RelatedPapersResponse(paper_id=paper_id, available=False)
            neighbours = related.nearest_works(db, paper.work, limit)
            in_session = set(
                db.scalars(select(Paper.work_id).where(Paper.session_id == paper.session_id))
            )
            return RelatedPapersResponse(
                paper_id=paper_id,
                available=True,
                model=paper.work.embedding_model,
                related=[
                    related.related_payload(w, sim, w.id in in_session) for w, sim in neighbours
                ],
            )

    return await run_in_threadpool(find)


# ─── Synthesis ───────────────────────────────────────────────────────────────


@router.post("/{session_id}/synthesize", response_model=SynthesisResponse, tags=["Synthesis"])
async def synthesize(
    session_id: str,
    body: SynthesizeRequest,
    user_id: str = Depends(get_current_user),
) -> Synthesis:
    def load() -> list[dict[str, Any]]:
        with get_db_context() as db:
            get_owned_session(db, session_id, user_id)
            papers = db.scalars(
                select(Paper).where(Paper.session_id == session_id, Paper.id.in_(body.paper_ids))
            ).all()
            return [persistence.paper_to_dict(p) for p in papers]

    papers = await run_in_threadpool(load)
    if not papers:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "None of the papers belong to this session")
    result = await summarizer.synthesize_papers(papers)

    def save() -> Synthesis:
        with get_db_context() as db:
            record = Synthesis(
                session_id=session_id,
                paper_ids=[p["id"] for p in papers],
                content=result["synthesis"],
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

    return await run_in_threadpool(save)


# ─── Export ──────────────────────────────────────────────────────────────────


def escape_bibtex(text: str | None) -> str:
    if text is None:
        return ""
    for old, new in (
        ("\\", "\\textbackslash{}"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("$", "\\$"),
        ("&", "\\&"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("%", "\\%"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ):
        text = text.replace(old, new)
    return text


def _bib_key(paper: Paper, used: set[str]) -> str:
    last = (paper.authors[0].split()[-1] if paper.authors else "unknown").lower()
    first_word = next(
        (w for w in re.findall(r"[a-z]+", paper.title.lower()) if len(w) > 3), "paper"
    )
    base = re.sub(r"[^a-z0-9]", "", f"{last}{paper.year or 'nd'}{first_word}") or "ref"
    key, n = base, 1
    while key in used:  # BibTeX keys must be unique within a file
        n += 1
        key = f"{base}{chr(96 + n) if n <= 26 else n}"
    used.add(key)
    return key


@router.get("/{session_id}/export/bib", tags=["Export"])
def export_bib(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Response:
    get_owned_session(db, session_id, user_id)
    used: set[str] = set()
    entries = []
    for paper in persistence.load_papers(db, session_id):
        arxiv = (paper.external_id or "").startswith("arxiv:")
        fields = [f"  title = {{{escape_bibtex(paper.title)}}}"]
        if paper.authors:
            fields.append(f"  author = {{{escape_bibtex(' and '.join(paper.authors))}}}")
        if paper.year:
            fields.append(f"  year = {{{paper.year}}}")
        if paper.external_id and not arxiv:
            fields.append(f"  doi = {{{escape_bibtex(paper.external_id)}}}")
        if arxiv:
            fields.append(f"  eprint = {{{paper.external_id.removeprefix('arxiv:')}}}")
            fields.append("  archivePrefix = {arXiv}")
        if paper.source_url:
            fields.append(f"  url = {{{paper.source_url}}}")
        kind = "misc" if arxiv else "article"
        entries.append(f"@{kind}{{{_bib_key(paper, used)},\n" + ",\n".join(fields) + "\n}")
    return Response(
        content="\n\n".join(entries) + "\n",
        media_type="application/x-bibtex",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_name(session_id, "bib")}"'
        },
    )


@router.get("/{session_id}/export/txt", tags=["Export"])
def export_txt(
    session_id: str,
    style: str = Query("apa", pattern="^(apa|mla|ieee|chicago)$"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> Response:
    get_owned_session(db, session_id, user_id)
    lines = []
    for paper in persistence.load_papers(db, session_id):
        text = getattr(paper.citation, style, None) if paper.citation else None
        if not text:
            authors = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
            if len(paper.authors or []) > 3:
                authors += ", et al."
            text = f"{authors} ({paper.year or 'n.d.'}). {paper.title}."
        lines.append(text)
    return Response(
        content="\n\n".join(lines) + "\n",
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_export_name(session_id, "txt")}"'
        },
    )


# ─── Roadmap ─────────────────────────────────────────────────────────────────


@router.post("/{session_id}/roadmap", response_model=RoadmapResponse, tags=["Roadmap"])
async def generate_roadmap(session_id: str, user_id: str = Depends(get_current_user)):
    """Rebuild the roadmap from the session's *stored* papers, summaries, notes and
    conflicts. (The old endpoint re-ran discovery and every LLM call just to do this.)"""

    def load() -> tuple[str, dict[str, Any]]:
        with get_db_context() as db:
            record = get_owned_session(db, session_id, user_id)
            return record.query, persistence.session_inputs(db, session_id)

    query, inputs = await run_in_threadpool(load)
    if not inputs["papers"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Run a search for this session first")
    result = await roadmap.run(
        papers=inputs["papers"],
        analysis_trend_data=inputs["analysis"] or {},
        summaries=inputs["summaries"],
        notes=inputs["notes"],
        conflicts=inputs["conflicts"],
        session_id=session_id,
        query=query,
    )

    def save() -> None:
        with get_db_context() as db:
            persistence.save_roadmap(db, session_id, result)

    await run_in_threadpool(save)
    return result


@router.get("/{session_id}/roadmap", response_model=RoadmapResponse, tags=["Roadmap"])
def get_roadmap(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> RoadmapResponse:
    get_owned_session(db, session_id, user_id)
    record = db.scalar(select(Roadmap).where(Roadmap.session_id == session_id))
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Roadmap not found. Generate one first.")
    return persistence.roadmap_response(record)
