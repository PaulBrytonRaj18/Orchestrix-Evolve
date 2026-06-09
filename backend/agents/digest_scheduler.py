import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

import feedparser
import httpx
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL = "http://export.arxiv.org/api/query"


def normalize_string(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_frequency_delta(frequency: str) -> timedelta:
    if frequency == "daily":
        return timedelta(days=1)
    elif frequency == "weekly":
        return timedelta(weeks=1)
    elif frequency == "biweekly":
        return timedelta(weeks=2)
    elif frequency == "monthly":
        return relativedelta(months=1)
    return timedelta(weeks=1)


def calculate_next_run(last_run: datetime, frequency: str) -> datetime:
    delta = get_frequency_delta(frequency)
    return last_run + delta


def get_session_date_threshold(session: dict, frequency: str) -> datetime:
    if not session.get("created_at"):
        threshold = get_frequency_delta(frequency)
        return datetime.now(UTC) - threshold
    return session["created_at"]


async def query_semantic_scholar_new(
    query: str, threshold_date: datetime | None = None, limit: int = 50
) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API_URL,
                params={
                    "query": query,
                    "fields": "title,authors,year,abstract,externalIds,citationCount,url",
                    "limit": limit,
                    "offset": 0,
                    "year": f"{threshold_date.year}-{datetime.now().year}"
                    if threshold_date
                    else None,
                },
            )
            response.raise_for_status()
            data = response.json()

            papers = []
            for item in data.get("data", []):
                if threshold_date and item.get("year"):
                    try:
                        paper_date = datetime(
                            item.get("year"), 1, 1, tzinfo=UTC
                        )
                        if paper_date < threshold_date:
                            continue
                    except (ValueError, TypeError):
                        pass

                authors = [
                    author.get("name", "Unknown") for author in item.get("authors", [])
                ]
                papers.append({
                    "title": item.get("title", ""),
                    "authors": authors,
                    "year": item.get("year"),
                    "abstract": item.get("abstract"),
                    "source_url": item.get("url"),
                    "citation_count": item.get("citationCount"),
                    "external_id": item.get("externalIds", {}).get("ArXiv")
                    or item.get("externalIds", {}).get("DOI", ""),
                    "source": "semantic_scholar",
                })
            return papers
    except Exception as e:
        logger.error(f"Semantic Scholar API error: {e}")
        return []


async def query_arxiv_new(
    query: str, threshold_date: datetime | None = None, limit: int = 50
) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_query = f"all:{query}"
            if threshold_date:
                start_date = threshold_date.strftime("%Y-%m-%d")
                search_query += f"+ AND submittedDate:[{start_date} TO NOW]"

            url = (
                f"{ARXIV_API_URL}?search_query={search_query}"
                f"&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
            )
            response = await client.get(url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)
            papers = []

            for entry in feed.entries:
                authors = [
                    author.get("name", "Unknown") for author in entry.get("authors", [])
                ]
                abstract = ""
                if hasattr(entry, "summary"):
                    abstract = entry.summary
                elif hasattr(entry, "summary_detail"):
                    abstract = entry.summary_detail.get("value", "")

                paper_id = ""
                if hasattr(entry, "id"):
                    paper_id = entry.id.split("/")[-1]

                papers.append({
                    "title": entry.get("title", "").replace("\n", " "),
                    "authors": authors,
                    "year": int(entry.published_parsed[0])
                    if hasattr(entry, "published_parsed") and entry.published_parsed
                    else None,
                    "abstract": abstract.replace("\n", " ")[:2000],
                    "source_url": entry.get("id", ""),
                    "citation_count": None,
                    "external_id": paper_id,
                    "source": "arxiv",
                })
            return papers
    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        return []


async def run_digest(
    query: str,
    last_run_at: datetime | None = None,
    existing_external_ids: list[str] | None = None,
    limit: int = 30,
) -> dict:
    existing_ids = set(existing_external_ids or [])

    threshold = (
        last_run_at if last_run_at else datetime.now(UTC) - timedelta(days=7)
    )

    ss_task = query_semantic_scholar_new(query, threshold, limit)
    arxiv_task = query_arxiv_new(query, threshold, limit)

    ss_papers, arxiv_papers = await asyncio.gather(ss_task, arxiv_task)

    all_papers = ss_papers + arxiv_papers

    new_papers = []
    for paper in all_papers:
        ext_id = paper.get("external_id", "")
        if ext_id and ext_id not in existing_ids:
            new_papers.append(paper)
            existing_ids.add(ext_id)

    new_papers.sort(key=lambda x: x.get("year", 2000) or 2000, reverse=True)
    new_papers = new_papers[:limit]

    deduplicated = []
    seen_titles = set()
    for paper in new_papers:
        norm_title = normalize_string(paper.get("title", ""))
        if norm_title and norm_title not in seen_titles:
            seen_titles.add(norm_title)
            deduplicated.append(paper)

    return {
        "new_papers": deduplicated,
        "total_new": len(deduplicated),
        "is_first_run": last_run_at is None,
        "query": query,
        "threshold_date": threshold.isoformat() if last_run_at else None,
    }


async def check_for_updates(query: str, existing_external_ids: list[str]) -> dict:
    datetime.now(UTC) - timedelta(days=1)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API_URL,
                params={"query": query, "fields": "title,year", "limit": 100},
            )
            response.raise_for_status()
            data = response.json()

            new_count = 0
            for item in data.get("data", []):
                ext_id = item.get("externalIds", {}).get("DOI", "")
                if ext_id and ext_id not in existing_external_ids:
                    new_count += 1

            return {"has_updates": new_count > 0, "potential_new_count": new_count}
    except Exception as e:
        logger.error(f"Update check error: {e}")
        return {"has_updates": False, "potential_new_count": 0}


def generate_digest_notification(
    digest_name: str, query: str, new_papers: list[dict], frequency: str
) -> str:
    if not new_papers:
        return f"""
Orchestrix Research Digest: {digest_name}

No new papers found for your query "{query}" since the last run.

This is expected if:
- The research area is stable with few new publications
- Your search query is very specific
- The frequency is set to daily and yesterday had no new papers

To modify your digest settings, visit your Orchestrix dashboard.

---
Orchestrix - Multi-Agent Research Intelligence Platform
"""

    top_papers = new_papers[:5]

    papers_list = []
    for i, paper in enumerate(top_papers, 1):
        authors = ", ".join(paper.get("authors", ["Unknown"])[:3])
        if len(paper.get("authors", [])) > 3:
            authors += " et al."

        paper_text = f"""
{i}. {paper.get("title", "Untitled")}
   Authors: {authors}
   Year: {paper.get("year", "N/A")}
   Citations: {paper.get("citation_count", 0) or 0}
   Source: {paper.get("source", "Unknown")}
   URL: {paper.get("source_url", "N/A")}
"""
        papers_list.append(paper_text)

    more_count = len(new_papers) - 5

    return f"""
Orchestrix Research Digest: {digest_name}

New papers found for your query: "{query}"
Run frequency: {frequency}

=== Top {len(top_papers)} Papers ===

{"".join(papers_list)}

{"=" * 50}
{f"Plus {more_count} more new papers. See dashboard." if more_count > 0 else ""}
{"=" * 50}

Total new papers this digest: {len(new_papers)}

---
Orchestrix - Multi-Agent Research Intelligence Platform
"""


async def verify_query_syntax(query: str) -> tuple[bool, str | None]:
    if not query or len(query.strip()) < 3:
        return False, "Query must be at least 3 characters"

    if len(query) > 500:
        return False, "Query must be less than 500 characters"

    dangerous_patterns = ["--", "/*", "*/", "xp_", "sp_", "exec", "execute", "union", "select"]
    query_lower = query.lower()
    for pattern in dangerous_patterns:
        if pattern in query_lower:
            return False, f"Query contains potentially dangerous pattern: {pattern}"

    return True, None
