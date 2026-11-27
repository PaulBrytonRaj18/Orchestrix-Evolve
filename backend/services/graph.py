"""Citation graph of a session, built from OpenAlex reference lists.

* Each work's OpenAlex id and outgoing references are fetched once (batched by DOI;
  arXiv papers via their ``10.48550/arxiv.<id>`` DOI) and stored on the work.
* Within a session, an edge A → B means paper A cites paper B.
* **PageRank** over that graph ranks foundational papers by citation structure.
* **Missing key papers**: works cited by several session papers but not in it.
* **Clusters**: connected groups of papers; groups that never cite each other hint
  at disconnected sub-literatures (a research gap or a bridging opportunity).
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from agents.discovery import fetch_with_retry, normalize_arxiv_id, normalize_doi
from config import get_settings
from models import Paper, Work

logger = logging.getLogger(__name__)
_BATCH = 50


def _doi_for(work: Work) -> str | None:
    ext = work.external_id or ""
    if ext.startswith("arxiv:"):
        return f"10.48550/arxiv.{normalize_arxiv_id(ext.removeprefix('arxiv:'))}"
    if ext.startswith("10."):
        return normalize_doi(ext)
    return None


def _short(openalex_id: str | None) -> str | None:
    return openalex_id.rsplit("/", 1)[-1] if openalex_id else None


async def fetch_references(works: list[Work]) -> dict[str, dict[str, Any]]:
    """``{work id: {"openalex_id", "references"}}`` for works OpenAlex knows (by DOI)."""
    s = get_settings()
    by_doi: dict[str, Work] = {}
    for w in works:
        doi = _doi_for(w)
        if doi:
            by_doi[doi] = w
    found: dict[str, dict[str, Any]] = {}
    dois = list(by_doi)
    async with httpx.AsyncClient(timeout=s.discovery_timeout, follow_redirects=True) as client:
        for start in range(0, len(dois), _BATCH):
            chunk = dois[start : start + _BATCH]
            params = {
                "filter": "doi:" + "|".join(chunk),
                "per_page": _BATCH,
                "select": "id,doi,referenced_works",
            }
            if s.openalex_mailto:
                params["mailto"] = s.openalex_mailto
            response = await fetch_with_retry(client, s.openalex_url, params)
            if response is None:
                continue
            for item in response.json().get("results") or []:
                work = by_doi.get(normalize_doi(item.get("doi")))
                if work is not None:
                    found[work.id] = {
                        "openalex_id": _short(item.get("id")),
                        "references": [_short(r) for r in item.get("referenced_works") or []],
                    }
    return found


async def lookup_titles(openalex_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Bibliographic basics for OpenAlex works (used for missing key papers)."""
    s = get_settings()
    if not openalex_ids:
        return {}
    params = {
        "filter": "openalex_id:" + "|".join(openalex_ids[:_BATCH]),
        "per_page": _BATCH,
        "select": "id,title,doi,publication_year,cited_by_count,authorships",
    }
    async with httpx.AsyncClient(timeout=s.discovery_timeout, follow_redirects=True) as client:
        response = await fetch_with_retry(client, s.openalex_url, params)
    out = {}
    for item in (response.json().get("results") if response else None) or []:
        out[_short(item["id"])] = {
            "openalex_id": _short(item["id"]),
            "title": item.get("title") or "Untitled",
            "year": item.get("publication_year"),
            "citation_count": item.get("cited_by_count"),
            "doi": normalize_doi(item.get("doi")) or None,
            "authors": [
                (a.get("author") or {}).get("display_name", "")
                for a in (item.get("authorships") or [])[:3]
            ],
        }
    return out


def pagerank(
    nodes: list[str], edges: list[tuple[str, str]], damping: float = 0.85
) -> dict[str, float]:
    """Power-iteration PageRank (dangling mass spread uniformly), scores sum to 1."""
    n = len(nodes)
    if n == 0:
        return {}
    out: dict[str, list[str]] = {v: [] for v in nodes}
    for a, b in edges:
        out[a].append(b)
    rank = dict.fromkeys(nodes, 1.0 / n)
    for _ in range(100):
        dangling = sum(rank[v] for v in nodes if not out[v])
        new = {v: (1 - damping) / n + damping * dangling / n for v in nodes}
        for v in nodes:
            for target in out[v]:
                new[target] += damping * rank[v] / len(out[v])
        if sum(abs(new[v] - rank[v]) for v in nodes) < 1e-10:
            rank = new
            break
        rank = new
    return rank


def clusters(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Connected components of the undirected citation graph, largest first."""
    parent = {v: v for v in nodes}

    def find(v: str) -> str:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in edges:
        parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for v in nodes:
        groups.setdefault(find(v), []).append(v)
    return sorted(groups.values(), key=len, reverse=True)


def store_references(db: Session, found: dict[str, dict[str, Any]], tried: list[str]) -> None:
    now = datetime.now(UTC)
    for work_id in tried:
        work = db.get(Work, work_id)
        if work is None:
            continue
        info = found.get(work_id)
        if info:
            work.openalex_id = info["openalex_id"]
            work.references = info["references"]
        work.references_fetched_at = now  # also for misses, so we do not retry every call


def build_graph(papers: list[Paper], missing_info: dict[str, dict[str, Any]] | None = None) -> dict:
    """The graph payload for a session's papers (their works must carry references)."""
    by_oa = {p.work.openalex_id: p for p in papers if p.work.openalex_id}
    nodes = [p.id for p in papers]
    edges = []
    outside: Counter[str] = Counter()
    for p in papers:
        for ref in p.work.references or []:
            target = by_oa.get(ref)
            if target is not None and target.id != p.id:
                edges.append((p.id, target.id))
            elif target is None:
                outside[ref] += 1
    ranks = pagerank(nodes, edges)
    in_degree = Counter(b for _, b in edges)
    groups = clusters(nodes, edges)
    title = {p.id: p.title for p in papers}
    connected = [g for g in groups if len(g) > 1]
    gaps = []
    if len(connected) >= 2:
        for i, g in enumerate(connected[:3]):
            top = max(g, key=lambda v: ranks[v])
            gaps.append(
                {
                    "cluster": i + 1,
                    "size": len(g),
                    "anchor_paper_id": top,
                    "anchor_title": title[top],
                }
            )
    missing = [
        {**(missing_info or {}).get(ref, {"openalex_id": ref}), "cited_by_session_papers": count}
        for ref, count in outside.most_common(10)
        if count >= 2
    ]
    return {
        "nodes": [
            {
                "id": p.id,
                "title": p.title,
                "year": p.year,
                "citation_count": p.citation_count,
                "pagerank": round(ranks[p.id], 5),
                "cited_by_in_session": in_degree[p.id],
                "has_references": p.work.references is not None,
            }
            for p in papers
        ],
        "edges": [{"source": a, "target": b} for a, b in edges],
        "foundational": [
            {
                "paper_id": v,
                "title": title[v],
                "pagerank": round(ranks[v], 5),
                "cited_by_in_session": in_degree[v],
            }
            for v in sorted(nodes, key=lambda v: -ranks[v])[:8]
            if in_degree[v] > 0
        ],
        "missing_key_papers": missing,
        "disconnected_clusters": gaps,
        "coverage": {
            "papers": len(nodes),
            "with_references": sum(1 for p in papers if p.work.references is not None),
            "edges": len(edges),
        },
    }


async def session_graph(session_id: str, user_id: str) -> dict:
    """Fetch any missing reference lists, then build the session's graph."""
    from fastapi.concurrency import run_in_threadpool

    from database import get_db_context
    from routers.sessions import get_owned_session
    from services.persistence import load_papers

    def load_pending() -> list[Work]:
        with get_db_context() as db:
            get_owned_session(db, session_id, user_id)
            papers = load_papers(db, session_id)
            pending = [p.work for p in papers if p.work.references_fetched_at is None]
            for w in pending:
                db.expunge(w)
            return pending

    pending = await run_in_threadpool(load_pending)
    if pending:
        found = await fetch_references(pending)

        def save() -> None:
            with get_db_context() as db:
                store_references(db, found, [w.id for w in pending])

        await run_in_threadpool(save)

    def build() -> tuple[dict, list[str]]:
        with get_db_context() as db:
            papers = load_papers(db, session_id)
            graph = build_graph(papers)
            return graph, [m["openalex_id"] for m in graph["missing_key_papers"]]

    graph, missing_ids = await run_in_threadpool(build)
    if missing_ids:
        info = await lookup_titles(missing_ids)
        graph["missing_key_papers"] = [
            {**info.get(m["openalex_id"], {}), **m} for m in graph["missing_key_papers"]
        ]
    return graph
