"""Reads against the shared ``works`` table used *before* persistence: reuse stored
summaries and embeddings instead of recomputing them for papers seen before.

All functions are blocking (run them in a worker thread) and never raise: on any
database problem they return nothing and the caller computes as usual.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import Work, work_key_for

logger = logging.getLogger(__name__)


def _keys(papers: list[dict[str, Any]]) -> dict[str, str]:
    """``{work_key: provisional paper id}`` for papers that carry an id."""
    return {
        work_key_for(p.get("external_id"), p.get("title")): p["id"] for p in papers if p.get("id")
    }


def stored_summaries(papers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Existing work summaries, keyed by the *provisional* paper id they apply to."""
    from database import get_db_context

    keys = _keys(papers)
    if not keys:
        return {}
    try:
        with get_db_context() as db:
            works = db.scalars(
                select(Work)
                .where(Work.work_key.in_(list(keys)))
                .options(selectinload(Work.summary))
            ).all()
            found = {}
            for w in works:
                s = w.summary
                if s is None or not (s.abstract_compression or s.key_contributions):
                    continue
                found[keys[w.work_key]] = {
                    "paper_id": keys[w.work_key],
                    "title": w.title,
                    "abstract_compression": s.abstract_compression or "",
                    "key_contributions": s.key_contributions or "",
                    "methodology": s.methodology or "",
                    "limitations": s.limitations or "",
                    "generated_by": s.generated_by or "llm",
                    "reused": True,
                }
            return found
    except Exception as exc:
        logger.warning("Could not read stored summaries: %s", exc)
        return {}


def stored_embeddings(work_keys: list[str], model: str) -> dict[str, list[float]]:
    """Embeddings already computed with ``model``, keyed by work key."""
    from database import get_db_context

    if not work_keys:
        return {}
    try:
        with get_db_context() as db:
            rows = db.execute(
                select(Work.work_key, Work.embedding).where(
                    Work.work_key.in_(work_keys),
                    Work.embedding_model == model,
                    Work.embedding.is_not(None),
                )
            ).all()
            return {k: v for k, v in rows if v}
    except Exception as exc:
        logger.warning("Could not read stored embeddings: %s", exc)
        return {}
