"""Persistence for orchestration output and read-models for session views.

Every write path (the orchestrate endpoint, roadmap follow-up queries and the digest
scheduler) goes through :func:`save_orchestration`, so papers are de-duplicated,
summaries are linked to their papers, and re-running a session updates rather than
duplicates its analysis, conflicts and roadmap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from agents.discovery import normalize_text
from models import Analysis, Citation, Conflict, Paper, Roadmap, Summary
from models import Session as SessionModel
from schemas import (
    AnalysisResponse,
    ConflictResponse,
    PaperWithDetails,
    RoadmapResponse,
    SummaryResponse,
)


def _clip(value: Any, limit: int) -> Any:
    return value[:limit] if isinstance(value, str) else value


def _valid_year(year: Any) -> int | None:
    return year if isinstance(year, int) and 1900 <= year <= 2100 else None


def _paper_query(session_id: str):
    return (
        select(Paper)
        .where(Paper.session_id == session_id)
        .options(
            selectinload(Paper.summary), selectinload(Paper.citation), selectinload(Paper.notes)
        )
        .order_by(Paper.relevance_score.desc().nulls_last(), Paper.created_at)
    )


def load_papers(db: Session, session_id: str) -> list[Paper]:
    """All papers of a session with summary/citation/notes eagerly loaded (3 queries, not 3N)."""
    return list(db.scalars(_paper_query(session_id)))


def paper_counts(db: Session, session_ids: list[str]) -> dict[str, int]:
    if not session_ids:
        return {}
    rows = db.execute(
        select(Paper.session_id, func.count(Paper.id))
        .where(Paper.session_id.in_(session_ids))
        .group_by(Paper.session_id)
    )
    return dict(rows.all())


def _get_or_create(db: Session, model: type, where: dict[str, Any], **values: Any) -> Any:
    """Race-safe upsert helper.

    Looks the row up; if absent, inserts it inside a SAVEPOINT. When a concurrent
    writer inserted the same unique key first, the unique index rejects ours, the
    savepoint rolls back (the outer transaction survives) and the winner's row is used.
    """
    stmt = select(model).filter_by(**where)
    row = db.scalar(stmt)
    if row is not None:
        return row
    row = model(**where, **values)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        row = db.scalar(stmt)
        if row is None:
            raise
    return row


def save_papers(db: Session, session_id: str, papers: list[dict[str, Any]]) -> dict[str, str]:
    """Insert new papers (+ citations); return ``{provisional_id: stored_id}``."""
    existing = db.execute(
        select(Paper.id, Paper.external_id, Paper.title).where(Paper.session_id == session_id)
    ).all()
    by_ext = {e: pid for pid, e, _ in existing if e}
    by_title = {normalize_text(t): pid for pid, _, t in existing}

    id_map: dict[str, str] = {}
    for data in papers:
        provisional = data.get("id")
        ext = _clip(data.get("external_id"), 500)
        stored = by_ext.get(ext) if ext else None
        stored = stored or by_title.get(normalize_text(data.get("title")))
        if stored:
            if provisional:
                id_map[provisional] = stored
            continue

        paper = Paper(
            session_id=session_id,
            title=_clip(data.get("title") or "Untitled", 1000),
            authors=list(data.get("authors") or [])[:500],
            year=_valid_year(data.get("year")),
            abstract=_clip(data.get("abstract"), 10000),
            source_url=_clip(data.get("source_url"), 2000),
            citation_count=data.get("citation_count"),
            relevance_score=data.get("relevance_score"),
            external_id=ext,
            source=_clip(data.get("source") or "unknown", 100),
        )
        if provisional:
            paper.id = provisional
        try:
            with db.begin_nested():
                db.add(paper)
                db.flush()
        except IntegrityError:
            # A concurrent run stored this work first (uq_papers_session_external).
            winner = db.scalar(
                select(Paper.id).where(Paper.session_id == session_id, Paper.external_id == ext)
            )
            if winner is None:
                raise
            if provisional:
                id_map[provisional] = winner
            continue
        cit = data.get("citation")
        if cit:
            record = _get_or_create(db, Citation, {"paper_id": paper.id})
            record.apa, record.mla = cit.get("apa"), cit.get("mla")
            record.ieee, record.chicago = cit.get("ieee"), cit.get("chicago")
        if ext:
            by_ext[ext] = paper.id
        by_title[normalize_text(paper.title)] = paper.id
        id_map[provisional or paper.id] = paper.id
    return id_map


def save_summaries(db: Session, summaries: list[dict[str, Any]], id_map: dict[str, str]) -> None:
    for data in summaries:
        paper_id = id_map.get(data.get("paper_id") or "")
        if not paper_id:
            continue
        summary = _get_or_create(db, Summary, {"paper_id": paper_id})
        summary.abstract_compression = data.get("abstract_compression") or None
        summary.key_contributions = data.get("key_contributions") or None
        summary.methodology = data.get("methodology") or None
        summary.limitations = data.get("limitations") or None


def save_roadmap(
    db: Session, session_id: str, roadmap: dict[str, Any], id_map: dict[str, str] | None = None
) -> None:
    id_map = id_map or {}
    foundational = [
        {**fp, "paper_id": id_map.get(fp.get("paper_id"), fp.get("paper_id"))}
        for fp in roadmap.get("foundational_papers", [])
    ]
    record = _get_or_create(
        db,
        Roadmap,
        {"session_id": session_id},
        foundational_papers_json=[],
        gap_areas_json=[],
        next_queries_json=[],
    )
    record.foundational_papers_json = foundational
    record.gap_areas_json = roadmap.get("gap_areas", [])
    record.next_queries_json = roadmap.get("next_query_suggestions", [])


def save_orchestration(db: Session, session_id: str, result: dict[str, Any]) -> dict[str, str]:
    """Persist one orchestration run atomically (caller commits)."""
    id_map = save_papers(db, session_id, result.get("papers") or [])

    if result.get("analysis"):
        record = _get_or_create(
            db,
            Analysis,
            {"session_id": session_id, "analysis_type": "full"},
            data_json=result["analysis"],
        )
        record.data_json = result["analysis"]

    save_summaries(db, result.get("summaries") or [], id_map)

    if result.get("conflicts") is not None:
        # Replace this session's open conflicts; keep the ones a user already resolved.
        for stale in db.scalars(
            select(Conflict).where(Conflict.session_id == session_id, Conflict.resolved.is_(False))
        ):
            db.delete(stale)
        for c in result["conflicts"]:
            db.add(
                Conflict(
                    session_id=session_id,
                    conflict_type=c.get("conflict_type", "unknown"),
                    severity=c.get("severity", "medium"),
                    title=c.get("title", "")[:500],
                    description=c.get("description"),
                    analysis_insight=c.get("analysis_insight"),
                    summarization_insight=c.get("summarization_insight"),
                )
            )

    if result.get("roadmap"):
        save_roadmap(db, session_id, result["roadmap"], id_map)

    session = db.get(SessionModel, session_id)
    if session is not None:
        session.updated_at = datetime.now(UTC)
    db.flush()
    return id_map


# ─── Read models ─────────────────────────────────────────────────────────────


def paper_to_dict(p: Paper) -> dict[str, Any]:
    return {
        "id": p.id,
        "title": p.title,
        "authors": p.authors or [],
        "year": p.year,
        "abstract": p.abstract,
        "source": p.source,
        "source_url": p.source_url,
        "citation_count": p.citation_count,
        "external_id": p.external_id,
    }


def summary_to_dict(s: Summary) -> dict[str, Any]:
    return {
        "paper_id": s.paper_id,
        "abstract_compression": s.abstract_compression,
        "key_contributions": s.key_contributions,
        "methodology": s.methodology,
        "limitations": s.limitations,
    }


def session_inputs(db: Session, session_id: str) -> dict[str, Any]:
    """Stored papers/summaries/notes/analysis/conflicts as plain dicts for the agents."""
    papers = load_papers(db, session_id)
    analysis = db.scalar(
        select(Analysis)
        .where(Analysis.session_id == session_id)
        .order_by(Analysis.created_at.desc())
    )
    conflicts = db.scalars(select(Conflict).where(Conflict.session_id == session_id)).all()
    return {
        "papers": [paper_to_dict(p) for p in papers],
        "summaries": [summary_to_dict(p.summary) for p in papers if p.summary],
        "notes": [{"paper_id": n.paper_id, "content": n.content} for p in papers for n in p.notes],
        "analysis": analysis.data_json if analysis else None,
        "conflicts": [
            {"severity": c.severity, "title": c.title, "description": c.description}
            for c in conflicts
            if not c.resolved
        ],
    }


def build_orchestrate_response(db: Session, session_id: str, result: dict[str, Any]) -> dict:
    """The session as the UI shows it after a run. Without an ``analysis`` key in
    ``result`` (e.g. a finished job replayed later) the stored analysis is used."""
    papers = load_papers(db, session_id)
    if "analysis" in result:
        analysis = result["analysis"]
    else:
        stored = db.scalar(
            select(Analysis)
            .where(Analysis.session_id == session_id)
            .order_by(Analysis.updated_at.desc())
        )
        analysis = stored.data_json if stored else None
    paper_models = [PaperWithDetails.model_validate(p) for p in papers]
    conflicts = db.scalars(
        select(Conflict).where(Conflict.session_id == session_id).order_by(Conflict.created_at)
    ).all()
    roadmap = db.scalar(select(Roadmap).where(Roadmap.session_id == session_id))
    return {
        "papers": paper_models,
        "analysis": analysis,
        "citations": [
            {"paper_id": p.id, "title": p.title, "citation": p.citation.model_dump(mode="json")}
            for p in paper_models
            if p.citation
        ],
        "summaries": [SummaryResponse.model_validate(p.summary) for p in papers if p.summary],
        "trace": result.get("trace", []),
        "conflicts": [ConflictResponse.model_validate(c) for c in conflicts],
        "conflict_summary": result.get("conflict_summary"),
        "roadmap": roadmap_response(roadmap) if roadmap else None,
    }


def roadmap_response(record: Roadmap) -> RoadmapResponse:
    return RoadmapResponse(
        foundational_papers=record.foundational_papers_json or [],
        gap_areas=record.gap_areas_json or [],
        next_query_suggestions=record.next_queries_json or [],
    )


def analysis_responses(db: Session, session_id: str) -> list[AnalysisResponse]:
    rows = db.scalars(select(Analysis).where(Analysis.session_id == session_id)).all()
    return [AnalysisResponse.model_validate(a) for a in rows]


__all__ = [
    "analysis_responses",
    "build_orchestrate_response",
    "load_papers",
    "paper_counts",
    "paper_to_dict",
    "roadmap_response",
    "save_orchestration",
    "save_papers",
    "save_roadmap",
    "save_summaries",
    "session_inputs",
]


def persist_and_view(session_id: str, user_id: str, result: dict[str, Any]) -> dict:
    """Save one run for ``user_id``'s session and return the refreshed session view.

    Runs in a worker thread with its own short transaction (never across agent work).
    """
    from database import get_db_context

    with get_db_context() as db:
        session = db.get(SessionModel, session_id)
        if session is None or session.user_id != user_id:
            raise LookupError("Session not found")
        save_orchestration(db, session_id, result)
        db.commit()
        return build_orchestrate_response(db, session_id, result)
