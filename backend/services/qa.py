"""Ask questions about a session's papers (retrieval-augmented answers with citations).

1. **Ingest** (once per work, shared by every session): full text for arXiv papers,
   the abstract otherwise → ~1,000-character passages → embeddings → ``chunks``.
2. **Retrieve** the passages closest to the question among the session's papers
   (pgvector on PostgreSQL, NumPy on SQLite), at most 3 per paper.
3. **Answer** with the LLM using only those passages, citing them as [n]; citation
   numbers that do not match a shown passage are removed. Without an LLM the most
   relevant sentences are returned, each cited, instead of a generated answer.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
import numpy as np
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text

from config import get_settings
from database import get_db_context
from llm import get_llm
from models import Chunk, Paper, Work
from services import fulltext
from services.embeddings import get_embedder

logger = logging.getLogger(__name__)

INGEST_DEADLINE = 45.0  # seconds for downloading full texts in one request
MAX_PER_PAPER = 3
_CITE = re.compile(r"\[(\d+)\]")


class QAUnavailableError(RuntimeError):
    """No embedding model is loaded, so passages cannot be retrieved."""


def _session_works(session_id: str, user_id: str) -> list[dict[str, Any]]:
    from routers.sessions import get_owned_session

    with get_db_context() as db:
        get_owned_session(db, session_id, user_id)
        # Answer from the session's most relevant papers: bounded indexing cost even
        # after deep research has grown the session to dozens of papers.
        rows = db.execute(
            select(Paper.id, Work)
            .join(Work, Paper.work_id == Work.id)
            .where(Paper.session_id == session_id)
            .order_by(Paper.relevance_score.desc().nulls_last(), Paper.created_at)
            .limit(get_settings().qa_max_papers)
        ).all()
        return [
            {
                "paper_id": pid,
                "work_id": w.id,
                "title": w.title,
                "abstract": w.abstract,
                "external_id": w.external_id,
                "passages_source": w.passages_source,
            }
            for pid, w in rows
        ]


async def ingest(works: list[dict[str, Any]], model: str) -> None:
    """Store passages for works that have none yet for ``model``."""
    with get_db_context() as db:
        have = set(
            db.scalars(
                select(Chunk.work_id)
                .where(
                    Chunk.work_id.in_([w["work_id"] for w in works]), Chunk.embedding_model == model
                )
                .distinct()
            )
        )
    todo = [w for w in works if w["work_id"] not in have]
    if not todo:
        return
    texts: dict[str, str | None] = {}
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True, headers={"User-Agent": "Orchestrix/2.3 (research Q&A)"}
    ) as client:
        # Where to get each full text: its own arXiv id, else whatever OpenAlex knows
        # for its DOI (an arXiv copy first, then an open-access PDF).
        plan: dict[str, tuple[str, str]] = {}
        by_doi: dict[str, str] = {}
        for w in todo:
            aid = fulltext.arxiv_id_of(w["external_id"])
            if aid:
                plan[w["work_id"]] = ("arxiv", aid)
            elif (w["external_id"] or "").startswith("10."):
                by_doi[w["external_id"].lower()] = w["work_id"]
        if by_doi:
            try:
                resolved = await asyncio.wait_for(
                    fulltext.resolve_sources(client, list(by_doi)), timeout=15
                )
            except Exception as exc:
                logger.info("Could not resolve open-access sources: %s", exc)
                resolved = {}
            for doi, source in resolved.items():
                if doi in by_doi:
                    plan[by_doi[doi]] = source
        sem = asyncio.Semaphore(4)

        async def one(wid: str, kind: str, ref: str) -> None:
            async with sem:
                if kind == "arxiv":
                    texts[wid] = await fulltext.fetch_arxiv_text(client, ref)
                else:
                    texts[wid] = await fulltext.fetch_pdf_text(client, ref)

        tasks = [asyncio.create_task(one(wid, k, ref)) for wid, (k, ref) in plan.items()]
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=INGEST_DEADLINE)
            for t in pending:
                t.cancel()

    def store() -> None:
        embedder = get_embedder()
        with get_db_context() as db:
            for w in todo:
                chunks, source = fulltext.passages_for(
                    w["title"], w["abstract"], texts.get(w["work_id"])
                )
                vectors = embedder.embed_documents(chunks)
                db.query(Chunk).filter(Chunk.work_id == w["work_id"]).delete()
                for pos, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True)):
                    db.add(
                        Chunk(
                            work_id=w["work_id"],
                            position=pos,
                            text=chunk,
                            source=source,
                            embedding=[float(x) for x in vec],
                            embedding_model=model,
                        )
                    )
                work = db.get(Work, w["work_id"])
                work.passages_source = source
                db.flush()

    await run_in_threadpool(store)


def retrieve(
    work_ids: list[str], question_vec: np.ndarray, model: str, k: int
) -> list[dict[str, Any]]:
    with get_db_context() as db:
        if db.get_bind().dialect.name == "postgresql":
            literal = "[" + ",".join(f"{x:.7f}" for x in question_vec) + "]"
            rows = db.execute(
                text(
                    "SELECT work_id, text, source, 1 - (embedding <=> CAST(:v AS vector)) AS sim "
                    "FROM chunks WHERE embedding_model = :m AND work_id = ANY(:ids) "
                    "ORDER BY embedding <=> CAST(:v AS vector) LIMIT :lim"
                ),
                {"v": literal, "m": model, "ids": work_ids, "lim": k * 4},
            ).all()
            ranked = [(r.work_id, r.text, r.source, float(r.sim)) for r in rows]
        else:
            rows = db.execute(
                select(Chunk.work_id, Chunk.text, Chunk.source, Chunk.embedding).where(
                    Chunk.work_id.in_(work_ids), Chunk.embedding_model == model
                )
            ).all()
            if not rows:
                return []
            sims = np.asarray([r.embedding for r in rows], dtype=np.float32) @ question_vec
            ranked = sorted(
                ((r.work_id, r.text, r.source, float(s)) for r, s in zip(rows, sims, strict=True)),
                key=lambda t: -t[3],
            )
    picked, per_paper = [], {}
    for work_id, chunk, source, sim in ranked:
        if per_paper.get(work_id, 0) >= MAX_PER_PAPER:
            continue
        per_paper[work_id] = per_paper.get(work_id, 0) + 1
        picked.append(
            {"work_id": work_id, "text": chunk, "source": source, "similarity": round(sim, 4)}
        )
        if len(picked) == k:
            break
    return picked


_SYSTEM = (
    "You answer questions about research papers using ONLY the numbered passages given. "
    "Cite every statement with the passage number in square brackets, e.g. [2]. If the "
    "passages do not answer the question, say so plainly. Respond with a JSON object only."
)


def _best_sentence(passage: str, question: str) -> str:
    words = {w for w in re.findall(r"[a-z]{4,}", question.lower())}
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", passage) if len(s) > 30] or [passage]
    return max(sentences, key=lambda s: len(words & set(re.findall(r"[a-z]{4,}", s.lower()))))[:400]


async def answer(session_id: str, user_id: str, question: str, k: int = 8) -> dict[str, Any]:
    works = await run_in_threadpool(_session_works, session_id, user_id)  # ownership first
    embedder = get_embedder()
    if embedder is None or not embedder.available:
        raise QAUnavailableError("The embedding model is not available on this server")
    if not works:
        return {
            "question": question,
            "answer": "This session has no papers yet.",
            "mode": "none",
            "passages": [],
            "coverage": {"papers": 0, "fulltext": 0, "abstract_only": 0},
        }
    await ingest(works, embedder.model_name)
    qvec = await run_in_threadpool(embedder.embed_query, question)
    passages = await run_in_threadpool(
        retrieve, [w["work_id"] for w in works], qvec, embedder.model_name, k
    )
    by_work = {w["work_id"]: w for w in works}
    shown = [
        {
            "n": i,
            "paper_id": by_work[p["work_id"]]["paper_id"],
            "title": by_work[p["work_id"]]["title"],
            "text": p["text"],
            "source": p["source"],
            "similarity": p["similarity"],
        }
        for i, p in enumerate(passages, 1)
    ]
    mode, text_answer = "extractive", ""
    llm = get_llm()
    if shown and llm.enabled:
        listing = "\n\n".join(f"[{p['n']}] ({p['title']}) {p['text']}" for p in shown)
        data = await llm.chat_json(
            _SYSTEM,
            f"Question: {question}\n\nPassages:\n{listing}\n\n"
            'Return {"answer": "a concise answer with [n] citations"}.',
            max_tokens=700,
            temperature=0.1,
        )
        candidate = str((data or {}).get("answer") or "").strip()
        if candidate:
            valid = {str(p["n"]) for p in shown}
            text_answer = _CITE.sub(lambda m: m.group(0) if m.group(1) in valid else "", candidate)
            text_answer = re.sub(r"\s+([.,;])", r"\1", text_answer).strip()
            mode = "llm"
    if mode == "extractive" and shown:
        lines = [f"• {_best_sentence(p['text'], question)} [{p['n']}]" for p in shown[:3]]
        text_answer = "Most relevant evidence from your papers:\n" + "\n".join(lines)
    cited = {int(n) for n in _CITE.findall(text_answer)}
    for p in shown:
        p["cited"] = p["n"] in cited
    sources = await run_in_threadpool(_coverage, [w["work_id"] for w in works])
    return {
        "question": question,
        "answer": text_answer or "No passages found.",
        "mode": mode,
        "passages": shown,
        "coverage": sources,
    }


def _coverage(work_ids: list[str]) -> dict[str, int]:
    with get_db_context() as db:
        sources = db.scalars(select(Work.passages_source).where(Work.id.in_(work_ids))).all()
    return {
        "papers": len(work_ids),
        "fulltext": sum(1 for s in sources if s == "fulltext"),
        "abstract_only": sum(1 for s in sources if s == "abstract"),
    }
