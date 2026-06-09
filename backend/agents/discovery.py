"""
Research Discovery Agent - Queries Semantic Scholar, arXiv, and OpenAlex APIs.
"""

import asyncio
import logging
import math
import os
import re
from collections import Counter
from datetime import datetime
from urllib.parse import quote

import feedparser
import httpx
from dotenv import load_dotenv

from constants import STOPWORDS

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_URL = os.getenv("SEMANTIC_SCHOLAR_URL", "https://api.semanticscholar.org/graph/v1/paper/search")
ARXIV_URL = os.getenv("ARXIV_URL", "https://export.arxiv.org/api/query")
OPENALEX_URL = os.getenv("OPENALEX_URL", "https://api.openalex.org/works")

DEFAULT_LIMIT = 50
REQUEST_TIMEOUT = 30.0

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
    "arxiv": 0.5,
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
    "alt": 0.7, "algorithmic learning theory": 0.7,
    "bioinformatics": 0.6, "plos": 0.5, "ieee": 0.6, "acm": 0.6,
    "springer": 0.5, "elsevier": 0.5,
}


def decode_inverted_index(inverted_index: dict | None) -> str:
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
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_semantic_similarity(query: str, papers: list[dict]) -> list[dict]:
    if not papers:
        return papers

    query_normalized = normalize_text(query)
    query_normalized.split()

    def tokenize(text: str) -> list[str]:
        words = normalize_text(text).split()
        return [w for w in words if w not in STOPWORDS and len(w) > 1]

    all_docs = [query_normalized]
    for paper in papers:
        title = normalize_text(paper.get("title", ""))
        abstract = normalize_text(paper.get("abstract", "")[:1000])
        all_docs.append(f"{title} {abstract}")

    word_counts = Counter()
    for doc in all_docs:
        words = tokenize(doc)
        word_counts.update(words)

    vocab = [word for word, _ in word_counts.most_common(1000)]
    word_to_idx = {word: i for i, word in enumerate(vocab)}

    n_docs = len(all_docs)
    doc_vectors = []

    for doc_idx, doc in enumerate(all_docs):
        words = tokenize(doc)
        doc_word_counts = Counter(words)

        tf = {}
        for word, count in doc_word_counts.items():
            if word in word_to_idx:
                tf[word] = count / len(words) if words else 0

        idf = {}
        for word in word_to_idx:
            doc_count = sum(1 for d in all_docs if word in tokenize(d))
            idf[word] = math.log(n_docs / (1 + doc_count)) + 1

        vector = [0.0] * len(vocab)
        for word, tf_val in tf.items():
            idx = word_to_idx[word]
            vector[idx] = tf_val * idf[word]

        doc_vectors.append(vector)

    def normalize(v):
        magnitude = math.sqrt(sum(x * x for x in v))
        if magnitude == 0:
            return v
        return [x / magnitude for x in v]

    query_vec = normalize(doc_vectors[0])
    paper_vectors = [normalize(v) for v in doc_vectors[1:]]

    for i, paper in enumerate(papers):
        paper_vec = paper_vectors[i]
        similarity = sum(q * p for q, p in zip(query_vec, paper_vec))
        paper["semantic_score"] = float(similarity)

    return papers


def get_venue_quality(venue: str) -> float:
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
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def compute_relevance_score(
    paper: dict, query: str,
    min_citations: int, max_citations: int,
    min_year: int, max_year: int,
) -> float:
    score = 0.0

    citations = paper.get("citation_count") or 0
    if max_citations > min_citations:
        citation_score = (citations - min_citations) / (max_citations - min_citations)
    else:
        citation_score = 0.5
    score += 0.30 * citation_score

    year = paper.get("year") or min_year
    if max_year > min_year:
        year_score = (year - min_year) / (max_year - min_year)
    else:
        year_score = 0.5
    score += 0.15 * year_score

    query_words = normalize_text(query).split()
    if query_words:
        title_abstract = normalize_text(
            f"{paper.get('title', '')} {paper.get('abstract', '')}"
        )
        matches = sum(1 for kw in query_words if kw in title_abstract)
        keyword_score = matches / len(query_words)
        score += 0.20 * keyword_score

    semantic_score = paper.get("semantic_score", 0.5)
    score += 0.25 * semantic_score

    venue = paper.get("venue", "")
    venue_score = get_venue_quality(venue)
    score += 0.10 * venue_score

    return round(score, 4)


def deduplicate_papers(papers: list[dict], threshold: float = 0.7) -> list[dict]:
    if not papers:
        return papers

    seen: dict[str, dict] = {}
    for paper in papers:
        norm_title = normalize_text(paper.get("title", ""))
        if not norm_title:
            continue
        if norm_title not in seen:
            seen[norm_title] = paper
        elif (paper.get("citation_count") or 0) > (
            seen[norm_title].get("citation_count") or 0
        ):
            seen[norm_title] = paper

    result = list(seen.values())
    unique_papers = []

    for paper in result:
        is_duplicate = False
        for unique in unique_papers:
            if compute_similarity(paper.get("title", ""), unique.get("title", "")) >= threshold:
                is_duplicate = True
                if (paper.get("citation_count") or 0) > (unique.get("citation_count") or 0):
                    unique_papers.remove(unique)
                    unique_papers.append(paper)
                break
        if not is_duplicate:
            unique_papers.append(paper)

    return unique_papers


async def fetch_with_retry(
    client: httpx.AsyncClient, url: str, params: dict = None, max_retries: int = 3
) -> dict | None:
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
) -> list[dict]:
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

                papers.append({
                    "title": item.get("title", "Untitled"),
                    "authors": authors,
                    "year": item.get("year"),
                    "abstract": item.get("abstract"),
                    "source_url": item.get("url"),
                    "citation_count": item.get("citationCount"),
                    "external_id": external_ids.get("ArXiv") or external_ids.get("DOI", ""),
                    "source": "semantic_scholar",
                    "venue": item.get("venue", ""),
                })
            return papers
    except Exception as e:
        logger.error(f"Semantic Scholar error: {e}")
        return []


async def query_arxiv(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT
) -> list[dict]:
    try:
        async with httpx.AsyncClient() as client:
            search_query = f"all:{query.replace(' ', '+')}"
            start = page * limit
            url = (
                f"{ARXIV_URL}?search_query={quote(search_query)}"
                f"&start={start}&max_results={min(limit, 50)}&sortBy=relevance"
            )

            response = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
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

                papers.append({
                    "title": entry.get("title", "Untitled").replace("\n", " ").strip(),
                    "authors": authors,
                    "year": year,
                    "abstract": abstract.replace("\n", " ")[:2000] if abstract else "",
                    "source_url": entry.get("id", ""),
                    "citation_count": None,
                    "external_id": paper_id,
                    "source": "arxiv",
                    "venue": "arXiv",
                })
            return papers
    except Exception as e:
        logger.error(f"arXiv error: {e}")
        return []


async def query_openalex(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT
) -> list[dict]:
    try:
        async with httpx.AsyncClient() as client:
            url = (
                f"{OPENALEX_URL}?search={quote(query)}&per_page={min(limit, 200)}"
                f"&page={page + 1}&select=id,title,authorships,publication_year,doi,"
                "cited_by_count,host_venue,abstract_inverted_index"
            )

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

                papers.append({
                    "title": item.get("title", "Untitled") or "Untitled",
                    "authors": authors,
                    "year": year,
                    "abstract": decode_inverted_index(item.get("abstract_inverted_index")),
                    "source_url": item.get("doi", item.get("id", "")),
                    "citation_count": citation_count,
                    "external_id": doi,
                    "source": "openalex",
                    "venue": item.get("host_venue", {}).get("display_name", "")
                    if isinstance(item.get("host_venue"), dict)
                    else "",
                })
            return papers
    except Exception as e:
        logger.error(f"OpenAlex error: {e}")
        return []


async def run(
    query: str, page: int = 0, limit: int = DEFAULT_LIMIT, return_top: int = 20
) -> list[dict]:
    logger.info(f"Discovery: query='{query}', page={page}, limit={limit}, return_top={return_top}")

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
            logger.warning(f"{source_names[i]} failed: {result} - continuing with other sources")
            failed_sources.append(source_names[i])
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"{source_names[i]}: {len(result) if result else 0} papers")
            successful_sources.append(source_names[i])
            if result and len(result) > 0:
                all_papers.extend(result)

    if failed_sources:
        logger.warning(f"Falling back to {len(successful_sources)} sources: {successful_sources}")

    if not all_papers:
        logger.error("All discovery sources failed - no papers available")
        return []

    all_papers = compute_semantic_similarity(query, all_papers)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Computed semantic scores for {len(all_papers)} papers")

    all_papers = deduplicate_papers(all_papers)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"After dedup: {len(all_papers)} papers")

    citations = [p.get("citation_count") or 0 for p in all_papers]
    years = [p.get("year") or 2000 for p in all_papers if p.get("year")]

    min_citations = min(citations) if citations else 0
    max_citations = max(citations) if citations else 1
    min_year = min(years) if years else 1990
    max_year = max(years) if years else datetime.now().year

    for paper in all_papers:
        paper["relevance_score"] = compute_relevance_score(
            paper, query, min_citations, max_citations, min_year, max_year
        )

    all_papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    top_papers = all_papers[:return_top]

    if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Final: {len(top_papers)} papers (from {len(all_papers)} ranked)"
                f" from {successful_sources} (failed: {failed_sources})"
            )
    return top_papers


if __name__ == "__main__":
    async def test():
        results = await run("machine learning", 0, 10)
        print(f"\nFound {len(results)} papers:")
        for p in results[:5]:
            print(
                f"- {p['title'][:60]}... ({p['source']}, cites={p.get('citation_count')},"
                f" score={p.get('relevance_score', 0):.3f})"
            )

    asyncio.run(test())
