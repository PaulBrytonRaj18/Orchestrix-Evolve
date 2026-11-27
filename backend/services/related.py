"""Nearest-neighbour search over stored work embeddings ("related papers").

PostgreSQL uses pgvector's cosine-distance operator (``<=>``) inside the database;
SQLite falls back to NumPy over the stored JSON vectors. Searches cover every
stored work (public bibliographic metadata only — nothing about who found it).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models import Work
from services.embeddings import document_text, get_embedder

logger = logging.getLogger(__name__)
_SQLITE_SCAN_LIMIT = 20_000


def ensure_embedding(db: Session, work: Work) -> list[float] | None:
    """The work's embedding for the configured model, computing and storing it if needed."""
    embedder = get_embedder()
    if embedder is None or not embedder.available:
        return None
    if work.embedding is not None and work.embedding_model == embedder.model_name:
        return list(work.embedding)
    vector = embedder.embed_documents(
        [document_text({"title": work.title, "abstract": work.abstract})]
    )[0]
    work.embedding = [float(x) for x in vector]
    work.embedding_model = embedder.model_name
    db.flush()
    return work.embedding


def nearest_works(db: Session, work: Work, limit: int = 10) -> list[tuple[Work, float]]:
    """``[(work, cosine similarity)]`` most similar to ``work``, best first."""
    vector = ensure_embedding(db, work)
    if vector is None:
        return []
    model = work.embedding_model
    if db.get_bind().dialect.name == "postgresql":
        literal = "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
        rows = db.execute(
            text(
                "SELECT id, 1 - (embedding <=> CAST(:v AS vector)) AS similarity FROM works"
                " WHERE embedding_model = :m AND id <> :id AND embedding IS NOT NULL"
                " ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"
            ),
            {"v": literal, "m": model, "id": work.id, "k": limit},
        ).all()
        scores = {r.id: float(r.similarity) for r in rows}
    else:
        candidates = db.execute(
            select(Work.id, Work.embedding)
            .where(Work.embedding_model == model, Work.id != work.id, Work.embedding.is_not(None))
            .limit(_SQLITE_SCAN_LIMIT)
        ).all()
        if not candidates:
            return []
        matrix = np.asarray([c.embedding for c in candidates], dtype=np.float32)
        sims = matrix @ np.asarray(vector, dtype=np.float32)
        top = np.argsort(-sims)[:limit]
        scores = {candidates[i].id: float(sims[i]) for i in top}
    works = {w.id: w for w in db.scalars(select(Work).where(Work.id.in_(list(scores))))}
    return sorted(((works[i], s) for i, s in scores.items() if i in works), key=lambda t: -t[1])


def related_payload(work: Work, similarity: float, in_session: bool) -> dict[str, Any]:
    return {
        "work_id": work.id,
        "title": work.title,
        "authors": work.authors or [],
        "year": work.year,
        "citation_count": work.citation_count,
        "source_url": work.source_url,
        "external_id": work.external_id,
        "similarity": round(similarity, 4),
        "in_session": in_session,
    }
