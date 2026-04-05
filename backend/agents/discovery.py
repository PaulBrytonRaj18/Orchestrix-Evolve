import asyncio
import httpx
import feedparser
import re
from datetime import datetime
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL = "http://export.arxiv.org/api/query"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "done",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "make",
    "me",
    "might",
    "more",
    "most",
    "my",
    "no",
    "not",
    "now",
    "of",
    "on",
    "one",
    "only",
    "or",
    "our",
    "out",
    "own",
    "really",
    "said",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "up",
    "us",
    "very",
    "was",
    "we",
    "well",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "will",
    "with",
    "would",
    "you",
    "your",
    "also",
    "about",
    "after",
    "all",
    "any",
    "because",
    "before",
    "between",
    "both",
    "each",
    "even",
    "few",
    "first",
    "get",
    "go",
    "going",
    "good",
    "got",
    "however",
    "know",
    "last",
    "like",
    "long",
    "made",
    "many",
    "may",
    "much",
    "must",
    "need",
    "new",
    "next",
    "nothing",
    "often",
    "old",
    "once",
    "only",
    "other",
    "over",
    "own",
    "part",
    "people",
    "put",
    "right",
    "same",
    "say",
    "see",
    "set",
    "several",
    "show",
    "since",
    "still",
    "such",
    "take",
    "thing",
    "think",
    "though",
    "three",
    "time",
    "two",
    "under",
    "upon",
    "use",
    "want",
    "way",
    "well",
    "work",
    "year",
    "yet",
    "use",
    "used",
    "using",
    "showed",
    "shown",
    "gives",
    "given",
    "means",
    "within",
    "without",
    "became",
    "become",
    "makes",
    "based",
    "approach",
    "result",
    "results",
    "paper",
    "study",
    "work",
    "research",
    "method",
    "methods",
    "model",
    "data",
    "system",
    "performance",
    "problem",
    "propose",
    "proposed",
    "present",
    "presented",
    "provide",
    "provided",
    "high",
    "low",
    "large",
    "small",
    "different",
    "various",
    "number",
    "number",
    "case",
    "point",
    "term",
    "field",
    "area",
    "type",
    "level",
    "group",
}


def normalize_string(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_relevance_score(papers: List[Dict], query: str) -> List[Dict]:
    if not papers:
        return papers

    citations = [p.get("citation_count", 0) or 0 for p in papers]
    years = [p.get("year", 2000) or 2000 for p in papers]
    current_year = datetime.now().year

    min_citations = min(citations) if citations else 0
    max_citations = max(citations) if citations else 1
    min_year = min(years) if years else 1990
    max_year = max(years) if years else current_year

    citation_range = (
        max_citations - min_citations if max_citations > min_citations else 1
    )
    year_range = max_year - min_year if max_year > min_year else 1

    query_words = normalize_string(query).split()
    query_words = [w for w in query_words if w and w not in STOPWORDS]

    for paper in papers:
        citation_count = paper.get("citation_count", 0) or 0
        year = paper.get("year", 2000) or 2000

        norm_citations = (citation_count - min_citations) / citation_range
        norm_year = (year - min_year) / year_range

        title_abstract = normalize_string(
            (paper.get("title", "") or "") + " " + (paper.get("abstract", "") or "")
        )

        keyword_matches = sum(1 for w in query_words if w in title_abstract)
        keyword_ratio = keyword_matches / len(query_words) if query_words else 0

        score = 0.5 * norm_citations + 0.3 * norm_year + 0.2 * keyword_ratio
        paper["relevance_score"] = round(score, 4)

    return papers


def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    seen = {}
    result = []

    for paper in papers:
        norm_title = normalize_string(paper.get("title", "") or "")
        if not norm_title:
            result.append(paper)
            continue

        if norm_title not in seen:
            seen[norm_title] = paper
            result.append(paper)
        else:
            existing = seen[norm_title]
            if (paper.get("citation_count") or 0) > (
                existing.get("citation_count") or 0
            ):
                seen[norm_title] = paper

    return list(seen.values())


async def query_semantic_scholar(
    query: str, page: int = 0, limit: int = 20
) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEMANTIC_SCHOLAR_API_URL,
                params={
                    "query": query,
                    "fields": "title,authors,year,abstract,externalIds,citationCount,url",
                    "limit": limit,
                    "offset": page * limit,
                },
            )
            response.raise_for_status()
            data = response.json()

            papers = []
            for item in data.get("data", []):
                authors = [
                    author.get("name", "Unknown") for author in item.get("authors", [])
                ]
                papers.append(
                    {
                        "title": item.get("title", ""),
                        "authors": authors,
                        "year": item.get("year"),
                        "abstract": item.get("abstract"),
                        "source_url": item.get("url"),
                        "citation_count": item.get("citationCount"),
                        "external_id": item.get("externalIds", {}).get("ArXiv")
                        or item.get("externalIds", {}).get("DOI", ""),
                        "source": "semantic_scholar",
                    }
                )
            return papers
    except Exception as e:
        print(f"Semantic Scholar API error: {e}")
        return []


async def query_arxiv(query: str, page: int = 0, limit: int = 20) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_query = f"all:{query}"
            start = page * limit

            url = f"{ARXIV_API_URL}?search_query={search_query}&start={start}&max_results={limit}"
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

                papers.append(
                    {
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
                    }
                )
            return papers
    except Exception as e:
        print(f"arXiv API error: {e}")
        return []


async def run(query: str, page: int = 0, limit: int = 20) -> List[Dict]:
    """
    Discovery Agent: Queries both Semantic Scholar and arXiv APIs in parallel,
    normalizes results, deduplicates, computes relevance scores, and returns
    sorted papers.
    """
    ss_task = query_semantic_scholar(query, page, limit)
    arxiv_task = query_arxiv(query, page, limit)

    ss_papers, arxiv_papers = await asyncio.gather(ss_task, arxiv_task)

    all_papers = ss_papers + arxiv_papers

    all_papers = deduplicate_papers(all_papers)

    all_papers = compute_relevance_score(all_papers, query)

    all_papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    return all_papers
