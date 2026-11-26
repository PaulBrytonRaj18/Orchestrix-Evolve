"""Research Discovery Agent — Semantic Scholar, arXiv and OpenAlex.

Pipeline: fetch all sources concurrently over one pooled HTTP client → normalise
identifiers → merge duplicates (keeping the richest metadata) → TF-IDF similarity →
weighted relevance score → top-N.

The CPU-bound ranking runs in a worker thread so it never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

import feedparser
import httpx

from config import get_settings
from constants import STOPWORDS

logger = logging.getLogger(__name__)

SOURCES = ("semantic_scholar", "arxiv", "openalex")

VENUE_TIERS = {
    "neurips": 1.0, "nips": 1.0, "neural information processing systems": 1.0,
    "icml": 1.0, "international conference on machine learning": 1.0,
    "iclr": 1.0, "international conference on learning representations": 1.0,
    "cvpr": 1.0, "computer vision and pattern recognition": 1.0,
    "iccv": 1.0, "international conference on computer vision": 1.0,
    "eccv": 1.0, "european conference on computer vision": 1.0,
    "aaai": 1.0, "association for the advancement of artificial intelligence": 1.0,
    "ijcai": 1.0, "international joint conference on artificial intelligence": 1.0,
    "acl": 1.0, "association for computational linguistics": 1.0,
    "emnlp": 1.0, "empirical methods in natural language processing": 1.0,
    "naacl": 1.0, "north american chapter of the acl": 1.0,
    "coling": 1.0, "computational linguistics": 1.0,
    "nature": 1.0, "science": 1.0, "cell": 1.0,
    "jmlr": 1.0, "journal of machine learning research": 1.0,
    "pami": 1.0, "pattern analysis and machine intelligence": 1.0,
    "tnnls": 0.9, "neural networks and learning systems": 0.9,
    "tcbb": 0.8, "computational biology and bioinformatics": 0.8,
    "iros": 0.7, "intelligent robots and systems": 0.7,
    "robotics": 0.7, "accv": 0.7, "asian conference on computer vision": 0.7,
    "wacv": 0.7, "winter conference on applications of computer vision": 0.7,
    "icra": 0.7, "robotics and automation": 0.7,
    "aistats": 0.7, "artificial intelligence and statistics": 0.7,
    "uai": 0.7, "uncertainty in artificial intelligence": 0.7,
    "algorithmic learning theory": 0.7,
    "bioinformatics": 0.6, "ieee": 0.6, "acm": 0.6,
    "arxiv": 0.5, "plos": 0.5, "springer": 0.5, "elsevier": 0.5,
}  # fmt: skip

_ARXIV_VERSION = re.compile(r"v\d+$")
_WORD = re.compile(r"[a-z0-9]+")


# ─── Text helpers ────────────────────────────────────────────────────────────


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(_WORD.findall(text.lower()))


def tokenize(text: str | None) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if len(w) > 1 and w not in STOPWORDS]


def decode_inverted_index(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex stores abstracts as ``{word: [positions...]}``; rebuild the text."""
    if not inverted_index:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if isinstance(positions, list):
            positioned.extend((p, word) for p in positions if isinstance(p, int))
    positioned.sort()
    return " ".join(word for _, word in positioned)


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi


def normalize_arxiv_id(arxiv_id: str | None) -> str:
    if not arxiv_id:
        return ""
    arxiv_id = arxiv_id.strip().lower().rsplit("/abs/", 1)[-1].removeprefix("arxiv:")
    return _ARXIV_VERSION.sub("", arxiv_id)


def _make_paper(
    *,
    title: str | None,
    authors: list[str],
    year: int | None,
    abstract: str | None,
    source_url: str | None,
    citation_count: int | None,
    source: str,
    venue: str | None = "",
    doi: str | None = "",
    arxiv_id: str | None = "",
    publication_date: str | None = None,
) -> dict[str, Any]:
    doi_n, arxiv_n = normalize_doi(doi), normalize_arxiv_id(arxiv_id)
    return {
        "title": " ".join((title or "Untitled").split()),
        "authors": [a for a in authors if a][:50],
        "year": year,
        "abstract": " ".join((abstract or "").split())[:5000] or None,
        "source_url": source_url or (f"https://doi.org/{doi_n}" if doi_n else None),
        "citation_count": citation_count,
        "external_id": (f"arxiv:{arxiv_n}" if arxiv_n else doi_n) or None,
        "doi": doi_n or None,
        "arxiv_id": arxiv_n or None,
        "source": source,
        "venue": venue or "",
        "publication_date": publication_date,
    }


# ─── HTTP ────────────────────────────────────────────────────────────────────


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_retries: int = 2,
    max_wait: float = 5.0,
) -> httpx.Response | None:
    """GET with bounded exponential backoff on 429/5xx/network errors.

    Honours ``Retry-After`` but never waits longer than ``max_wait`` per attempt, so a
    rate-limited source degrades the result set instead of stalling the request.
    """
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.warning("%s request error: %s", url, exc)
            if attempt == max_retries:
                return None
            await asyncio.sleep(min(2**attempt, max_wait))
            continue
        if response.status_code == 200:
            return response
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == max_retries:
                logger.warning(
                    "%s gave HTTP %s after %d attempts", url, response.status_code, attempt + 1
                )
                return None
            retry_after = response.headers.get("Retry-After", "")
            wait = float(retry_after) if retry_after.isdigit() else 2**attempt
            await asyncio.sleep(min(wait, max_wait))
            continue
        logger.error("%s gave HTTP %s: %s", url, response.status_code, response.text[:200])
        return None
    return None


# ─── Sources ─────────────────────────────────────────────────────────────────


async def query_semantic_scholar(
    client: httpx.AsyncClient, query: str, page: int, limit: int, since: date | None = None
) -> list[dict[str, Any]]:
    s = get_settings()
    params: dict[str, Any] = {
        "query": query,
        "fields": "title,authors,year,abstract,externalIds,citationCount,url,venue,publicationDate",
        "limit": min(limit, 100),
        "offset": page * min(limit, 100),
    }
    if since:
        params["publicationDateOrYear"] = f"{since.isoformat()}:"
    headers = {"x-api-key": s.semantic_scholar_api_key} if s.semantic_scholar_api_key else None
    response = await fetch_with_retry(client, s.semantic_scholar_url, params, headers)
    if response is None:
        return []
    papers = []
    for item in response.json().get("data") or []:
        ids = item.get("externalIds") or {}
        papers.append(
            _make_paper(
                title=item.get("title"),
                authors=[a.get("name", "") for a in item.get("authors") or []],
                year=item.get("year"),
                abstract=item.get("abstract"),
                source_url=item.get("url"),
                citation_count=item.get("citationCount"),
                source="semantic_scholar",
                venue=item.get("venue"),
                doi=ids.get("DOI"),
                arxiv_id=ids.get("ArXiv"),
                publication_date=item.get("publicationDate"),
            )
        )
    return papers


def _arxiv_search_query(query: str, since: date | None) -> str:
    terms = [t for t in re.findall(r"\w+", query) if t.lower() not in STOPWORDS] or query.split()
    expr = " AND ".join(f"all:{t}" for t in terms[:12])
    if since:
        expr = f"({expr}) AND submittedDate:[{since:%Y%m%d}0000 TO 209912312359]"
    return expr


async def query_arxiv(
    client: httpx.AsyncClient, query: str, page: int, limit: int, since: date | None = None
) -> list[dict[str, Any]]:
    s = get_settings()
    limit = min(limit, 100)
    params = {
        "search_query": _arxiv_search_query(query, since),
        "start": page * limit,
        "max_results": limit,
        "sortBy": "submittedDate" if since else "relevance",
        "sortOrder": "descending",
    }
    response = await fetch_with_retry(client, s.arxiv_url, params)
    if response is None:
        return []
    feed = feedparser.parse(response.text)
    papers = []
    for entry in feed.entries:
        published = entry.get("published", "")
        year = int(published[:4]) if published[:4].isdigit() else None
        papers.append(
            _make_paper(
                title=entry.get("title"),
                authors=[a.get("name", "") for a in entry.get("authors", [])],
                year=year,
                abstract=entry.get("summary"),
                source_url=entry.get("id"),
                citation_count=None,
                source="arxiv",
                venue="arXiv",
                doi=entry.get("arxiv_doi"),
                arxiv_id=entry.get("id"),
                publication_date=published[:10] or None,
            )
        )
    return papers


async def query_openalex(
    client: httpx.AsyncClient, query: str, page: int, limit: int, since: date | None = None
) -> list[dict[str, Any]]:
    s = get_settings()
    params: dict[str, Any] = {
        "search": query,
        "per_page": min(limit, 200),
        "page": page + 1,
        "select": "id,title,authorships,publication_year,publication_date,doi,"
        "cited_by_count,primary_location,abstract_inverted_index,ids",
    }
    if since:
        params["filter"] = f"from_publication_date:{since.isoformat()}"
    if s.openalex_mailto:
        params["mailto"] = s.openalex_mailto
    response = await fetch_with_retry(client, s.openalex_url, params)
    if response is None:
        return []
    papers = []
    for item in response.json().get("results") or []:
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        arxiv_id = ""
        landing = location.get("landing_page_url") or ""
        if "arxiv.org/abs/" in landing:
            arxiv_id = landing
        papers.append(
            _make_paper(
                title=item.get("title"),
                authors=[
                    (a.get("author") or {}).get("display_name", "")
                    for a in (item.get("authorships") or [])[:50]
                ],
                year=item.get("publication_year"),
                abstract=decode_inverted_index(item.get("abstract_inverted_index")),
                source_url=item.get("doi") or landing or item.get("id"),
                citation_count=item.get("cited_by_count"),
                source="openalex",
                venue=source.get("display_name"),
                doi=item.get("doi"),
                arxiv_id=arxiv_id,
                publication_date=item.get("publication_date"),
            )
        )
    return papers


_FETCHERS = {
    "semantic_scholar": query_semantic_scholar,
    "arxiv": query_arxiv,
    "openalex": query_openalex,
}


async def fetch_all_sources(
    query: str,
    page: int = 0,
    limit: int | None = None,
    since: date | None = None,
    sources: tuple[str, ...] = SOURCES,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Query every source concurrently. Returns ``(papers, {source: count or -1 on error})``."""
    s = get_settings()
    limit = limit or s.discovery_per_source_limit
    async with httpx.AsyncClient(
        timeout=s.discovery_timeout,
        follow_redirects=True,
        headers={"User-Agent": "Orchestrix/2.1 (research discovery)"},
    ) as client:
        results = await asyncio.gather(
            *(_FETCHERS[name](client, query, page, limit, since) for name in sources),
            return_exceptions=True,
        )
    papers: list[dict[str, Any]] = []
    stats: dict[str, int] = {}
    for name, result in zip(sources, results, strict=True):
        if isinstance(result, BaseException):
            logger.error("Discovery source %s failed: %s", name, result)
            stats[name] = -1
        else:
            stats[name] = len(result)
            papers.extend(result)
    return papers, stats


# ─── Ranking ─────────────────────────────────────────────────────────────────


def compute_semantic_similarity(query: str, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TF-IDF cosine similarity between the query and each paper's title + abstract.

    Each document is tokenised exactly once and document frequencies are computed in
    one pass: O(total tokens). (The previous version re-tokenised every document for
    every vocabulary word inside the per-document loop — cubic, ~70 s for 60 papers.)
    """
    if not papers:
        return papers
    docs = [tokenize(query)] + [
        tokenize(f"{p.get('title', '')} {(p.get('abstract') or '')[:2000]}") for p in papers
    ]
    n_docs = len(docs)
    df: Counter[str] = Counter()
    for tokens in docs:
        df.update(set(tokens))
    idf = {w: math.log(n_docs / (1 + c)) + 1.0 for w, c in df.items()}

    def vector(tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        vec = {w: (c / total) * idf[w] for w, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {w: v / norm for w, v in vec.items()} if norm else vec

    query_vec = vector(docs[0])
    for paper, tokens in zip(papers, docs[1:], strict=True):
        pv = vector(tokens)
        paper["semantic_score"] = float(sum(v * pv.get(w, 0.0) for w, v in query_vec.items()))
    return papers


def get_venue_quality(venue: str | None) -> float:
    if not venue:
        return 0.3
    venue_lower = venue.lower()
    for key, score in VENUE_TIERS.items():
        if key in venue_lower:
            return score
    return 0.3


def compute_similarity(title1: str, title2: str) -> float:
    words1 = set(normalize_text(title1).split())
    words2 = set(normalize_text(title2).split())
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def compute_relevance_score(
    paper: dict[str, Any],
    query: str,
    max_citations: int,
    min_year: int,
    max_year: int,
) -> float:
    """Weighted blend in [0, 1]: semantic 35%, keyword 20%, citations 25%, recency 10%, venue 10%.

    Citations are log-scaled: counts are heavy-tailed, and linear scaling let one
    landmark paper flatten every other paper's citation score to ~0.
    """
    citations = paper.get("citation_count") or 0
    citation_score = math.log1p(citations) / math.log1p(max_citations) if max_citations > 0 else 0.0

    year = paper.get("year") or min_year
    year_score = (year - min_year) / (max_year - min_year) if max_year > min_year else 0.5

    query_words = set(tokenize(query))
    text = set(tokenize(f"{paper.get('title', '')} {paper.get('abstract') or ''}"))
    keyword_score = len(query_words & text) / len(query_words) if query_words else 0.0

    score = (
        0.35 * paper.get("semantic_score", 0.0)
        + 0.20 * keyword_score
        + 0.25 * citation_score
        + 0.10 * year_score
        + 0.10 * get_venue_quality(paper.get("venue"))
    )
    return round(min(max(score, 0.0), 1.0), 4)


def _merge(primary: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Fill gaps in ``primary`` from a duplicate record of the same work."""
    for key in ("abstract", "year", "doi", "arxiv_id", "venue", "source_url", "publication_date"):
        if not primary.get(key) and other.get(key):
            primary[key] = other[key]
    if (other.get("citation_count") or 0) > (primary.get("citation_count") or 0):
        primary["citation_count"] = other["citation_count"]
    if len(other.get("authors") or []) > len(primary.get("authors") or []):
        primary["authors"] = other["authors"]
    if primary.get("arxiv_id") and not primary.get("doi"):
        primary["external_id"] = f"arxiv:{primary['arxiv_id']}"
    elif primary.get("doi"):
        primary["external_id"] = primary["doi"]
    return primary


def deduplicate_papers(
    papers: list[dict[str, Any]], threshold: float = 0.85
) -> list[dict[str, Any]]:
    """Collapse the same work reported by several sources.

    Matches on DOI, arXiv id, exact normalised title, then title Jaccard ≥ threshold.
    The record with more citations wins and missing fields are merged in.
    """
    unique: list[dict[str, Any]] = []
    by_key: dict[str, int] = {}

    for paper in papers:
        norm_title = normalize_text(paper.get("title"))
        if not norm_title:
            continue
        keys = [f"t:{norm_title}"]
        if paper.get("doi"):
            keys.append(f"d:{paper['doi']}")
        if paper.get("arxiv_id"):
            keys.append(f"a:{paper['arxiv_id']}")

        idx = next((by_key[k] for k in keys if k in by_key), None)
        if idx is None:
            idx = next(
                (
                    i
                    for i, u in enumerate(unique)
                    if compute_similarity(paper["title"], u["title"]) >= threshold
                ),
                None,
            )
        if idx is None:
            unique.append(dict(paper))
            idx = len(unique) - 1
        else:
            existing = unique[idx]
            if (paper.get("citation_count") or 0) > (existing.get("citation_count") or 0):
                unique[idx] = _merge(dict(paper), existing)
            else:
                _merge(existing, paper)
        for k in keys:
            by_key[k] = idx
    return unique


def rank_papers(query: str, papers: list[dict[str, Any]], return_top: int) -> list[dict[str, Any]]:
    """Pure CPU work: dedupe → similarity → score → sort. Run via ``asyncio.to_thread``."""
    papers = deduplicate_papers(papers)
    if not papers:
        return []
    papers = compute_semantic_similarity(query, papers)
    max_citations = max((p.get("citation_count") or 0) for p in papers)
    years = [p["year"] for p in papers if p.get("year")]
    current_year = datetime.now(UTC).year
    min_year, max_year = (min(years), max(years)) if years else (current_year - 10, current_year)
    for paper in papers:
        paper["relevance_score"] = compute_relevance_score(
            paper, query, max_citations, min_year, max_year
        )
    papers.sort(key=lambda p: p["relevance_score"], reverse=True)
    return papers[:return_top]


async def run(
    query: str,
    page: int = 0,
    limit: int | None = None,
    return_top: int | None = None,
) -> list[dict[str, Any]]:
    s = get_settings()
    return_top = return_top or s.discovery_return_top
    papers, stats = await fetch_all_sources(query, page, limit)
    logger.info("Discovery '%s' page=%d source counts: %s", query, page, stats)
    if not papers:
        logger.error("All discovery sources returned nothing for '%s'", query)
        return []
    return await asyncio.to_thread(rank_papers, query, papers, return_top)
