"""
Research Discovery Agent - Queries Semantic Scholar, arXiv, and OpenAlex APIs.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote

import httpx
import feedparser
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Endpoints
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_URL = "https://export.arxiv.org/api/query"
OPENALEX_URL = "https://api.openalex.org/works"

DEFAULT_LIMIT = 20
REQUEST_TIMEOUT = 30.0


def decode_inverted_index(inverted_index: Optional[Dict]) -> str:
    """Decode OpenAlex abstract_inverted_index to plain text."""
    if not inverted_index:
        return ""
    try:
        words = []
        for pos in sorted(inverted_index.keys(), key=int):
            words.append(inverted_index[pos])
        return " ".join(words)
    except Exception:
        return ""


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_similarity(title1: str, title2: str) -> float:
    """Jaccard similarity between two titles."""
    words1 = set(normalize_text(title1).split())
    words2 = set(normalize_text(title2).split())
    if not words1 or not words2:
        return 0.0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def compute_relevance_score(
    paper: Dict,
    query: str,
    min_citations: int,
    max_citations: int,
    min_year: int,
    max_year: int,
) -> float:
    """Compute relevance score based on citations, year, and keyword matching."""
    score = 0.0

    # Citation score (40% weight)
    citations = paper.get("citation_count") or 0
    if max_citations > min_citations:
        citation_score = (citations - min_citations) / (max_citations - min_citations)
    else:
        citation_score = 0.5
    score += 0.40 * citation_score

    # Year score (30% weight)
    year = paper.get("year") or min_year
    if max_year > min_year:
        year_score = (year - min_year) / (max_year - min_year)
    else:
        year_score = 0.5
    score += 0.30 * year_score

    # Keyword matching (30% weight) - no stopwords
    query_words = normalize_text(query).split()
    if query_words:
        title_abstract = normalize_text(
            f"{paper.get('title', '')} {paper.get('abstract', '')}"
        )
        matches = sum(1 for kw in query_words if kw in title_abstract)
        keyword_score = matches / len(query_words)
        score += 0.30 * keyword_score

    return round(score, 4)


def deduplicate_papers(papers: List[Dict], threshold: float = 0.7) -> List[Dict]:
    """Remove duplicate papers using similarity matching."""
    if not papers:
        return papers

    # First pass: exact title match
    seen: Dict[str, Dict] = {}
    for paper in papers:
        norm_title = normalize_text(paper.get("title", ""))
        if not norm_title:
            continue
        if norm_title not in seen:
            seen[norm_title] = paper
        else:
            if (paper.get("citation_count") or 0) > (
                seen[norm_title].get("citation_count") or 0
            ):
                seen[norm_title] = paper

    # Second pass: fuzzy matching
    result = list(seen.values())
    unique_papers = []

    for paper in result:
        is_duplicate = False
        for unique in unique_papers:
            if (
                compute_similarity(paper.get("title", ""), unique.get("title", ""))
                >= threshold
            ):
                is_duplicate = True
                if (paper.get("citation_count") or 0) > (
                    unique.get("citation_count") or 0
                ):
                    unique_papers.remove(unique)
                    unique_papers.append(paper)
                break
        if not is_duplicate:
            unique_papers.append(paper)

    return unique_papers


async def fetch_with_retry(
    client: httpx.AsyncClient, url: str, params: Dict = None, max_retries: int = 3
) -> Optional[Dict]:
    """Fetch URL with retry logic for rate limits and server errors."""
    for attempt in range(max_retries):
        try:
            response = await client.get(
                url, params=params, timeout=REQUEST_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = 2**attempt
                logger.warning(f"Rate limited, waiting {wait}s")
                await asyncio.sleep(wait)
            elif e.response.status_code >= 500:
                wait = 2**attempt
                logger.warning(f"Server error, retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"HTTP error: {e}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(2**attempt)
    return None


async def query_semantic_scholar(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT
) -> List[Dict]:
    """Query Semantic Scholar API."""
    try:
        async with httpx.AsyncClient() as client:
            params = {
                "query": query,
                "fields": "title,authors,year,abstract,externalIds,citationCount,url,venue",
                "limit": min(limit, 100),
                "offset": page * limit,
                "sort": "relevance",
            }

            data = await fetch_with_retry(client, SEMANTIC_SCHOLAR_URL, params)

            if not data or "data" not in data:
                return []

            papers = []
            for item in data["data"]:
                authors = [a.get("name", "Unknown") for a in item.get("authors", [])]
                external_ids = item.get("externalIds", {})

                papers.append(
                    {
                        "title": item.get("title", "Untitled"),
                        "authors": authors,
                        "year": item.get("year"),
                        "abstract": item.get("abstract"),
                        "source_url": item.get("url"),
                        "citation_count": item.get("citationCount"),
                        "external_id": external_ids.get("ArXiv")
                        or external_ids.get("DOI", ""),
                        "source": "semantic_scholar",
                        "venue": item.get("venue", ""),
                    }
                )
            return papers

    except Exception as e:
        logger.error(f"Semantic Scholar error: {e}")
        return []


async def query_arxiv(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT
) -> List[Dict]:
    """Query arXiv API."""
    try:
        async with httpx.AsyncClient() as client:
            search_query = f"all:{query.replace(' ', '+')}"
            start = page * limit

            url = f"{ARXIV_URL}?search_query={quote(search_query)}&start={start}&max_results={min(limit, 50)}&sortBy=relevance"

            response = await client.get(
                url, timeout=REQUEST_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()

            feed = feedparser.parse(response.text)

            papers = []
            for entry in feed.entries:
                authors = [a.get("name", "Unknown") for a in entry.get("authors", [])]

                abstract = ""
                if hasattr(entry, "summary"):
                    abstract = entry.summary
                elif hasattr(entry, "summary_detail"):
                    abstract = entry.summary_detail.get("value", "")

                paper_id = ""
                if hasattr(entry, "id"):
                    paper_id = entry.id.split("/")[-1].replace("arxiv:", "")

                year = None
                if hasattr(entry, "published"):
                    try:
                        year = int(entry.published[:4])
                    except (ValueError, TypeError):
                        pass

                papers.append(
                    {
                        "title": entry.get("title", "Untitled")
                        .replace("\n", " ")
                        .strip(),
                        "authors": authors,
                        "year": year,
                        "abstract": abstract.replace("\n", " ")[:2000]
                        if abstract
                        else "",
                        "source_url": entry.get("id", ""),
                        "citation_count": None,
                        "external_id": paper_id,
                        "source": "arxiv",
                        "venue": "arXiv",
                    }
                )
            return papers

    except Exception as e:
        logger.error(f"arXiv error: {e}")
        return []


async def query_openalex(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT
) -> List[Dict]:
    """Query OpenAlex API."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{OPENALEX_URL}?search={quote(query)}&per_page={min(limit, 200)}&page={page + 1}&select=id,title,authorships,publication_year,doi,cited_by_count,host_venue,abstract_inverted_index"

            data = await fetch_with_retry(client, url)

            if not data or "results" not in data:
                return []

            papers = []
            for item in data["results"]:
                authors = []
                if "authorships" in item:
                    authors = [
                        a.get("author", {}).get("display_name", "Unknown")
                        for a in item["authorships"][:10]
                    ]

                year = None
                if "publication_year" in item:
                    year = item["publication_year"]
                elif "publication_date" in item:
                    try:
                        year = int(item["publication_date"][:4])
                    except (ValueError, TypeError):
                        pass

                citation_count = item.get("cited_by_count")

                doi = ""
                if "doi" in item and item["doi"]:
                    doi = item["doi"].replace("https://doi.org/", "")

                papers.append(
                    {
                        "title": item.get("title", "Untitled") or "Untitled",
                        "authors": authors,
                        "year": year,
                        "abstract": decode_inverted_index(
                            item.get("abstract_inverted_index")
                        ),
                        "source_url": item.get("doi", item.get("id", "")),
                        "citation_count": citation_count,
                        "external_id": doi,
                        "source": "openalex",
                        "venue": item.get("host_venue", {}).get("display_name", "")
                        if isinstance(item.get("host_venue"), dict)
                        else "",
                    }
                )
            return papers

    except Exception as e:
        logger.error(f"OpenAlex error: {e}")
        return []


async def run(query: str, page: int = 0, limit: int = DEFAULT_LIMIT) -> List[Dict]:
    """Main discovery function - queries all sources in parallel.

    Gracefully handles API failures by continuing with results from working sources.
    """
    logger.info(f"Discovery: query='{query}', page={page}, limit={limit}")

    tasks = [
        query_semantic_scholar(query, page, limit),
        query_arxiv(query, page, limit),
        query_openalex(query, page, limit),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers = []
    source_names = ["semantic_scholar", "arxiv", "openalex"]
    failed_sources = []
    successful_sources = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(
                f"{source_names[i]} failed: {result} - continuing with other sources"
            )
            failed_sources.append(source_names[i])
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"{source_names[i]}: {len(result) if result else 0} papers"
                )
            successful_sources.append(source_names[i])
            if result and len(result) > 0:
                all_papers.extend(result)

    if failed_sources:
        logger.warning(
            f"Falling back to {len(successful_sources)} sources: {successful_sources}"
        )

    if not all_papers:
        logger.error("All discovery sources failed - no papers available")
        return []

    # Deduplicate
    all_papers = deduplicate_papers(all_papers)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"After dedup: {len(all_papers)} papers")

    # Compute scores
    citations = [p.get("citation_count") or 0 for p in all_papers]
    years = [p.get("year") or 2000 for p in all_papers if p.get("year")]

    min_citations = min(citations) if citations else 0
    max_citations = max(citations) if citations else 1
    min_year = min(years) if years else 1990
    from datetime import datetime

    max_year = max(years) if years else datetime.now().year

    for paper in all_papers:
        paper["relevance_score"] = compute_relevance_score(
            paper, query, min_citations, max_citations, min_year, max_year
        )

    all_papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            f"Final: {len(all_papers)} papers from {successful_sources} (failed: {failed_sources})"
        )
    return all_papers


if __name__ == "__main__":

    async def test():
        results = await run("machine learning", 0, 10)
        print(f"\nFound {len(results)} papers:")
        for p in results[:5]:
            print(
                f"- {p['title'][:60]}... ({p['source']}, cites={p.get('citation_count')}, score={p.get('relevance_score', 0):.3f})"
            )

    asyncio.run(test())
