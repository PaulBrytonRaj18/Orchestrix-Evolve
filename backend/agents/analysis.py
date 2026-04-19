import re
from collections import Counter
from datetime import datetime
from typing import List, Dict

from constants import STOPWORDS


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = text.lower()
    tokens = re.split(r"[^a-z0-9]+", text)
    tokens = [t for t in tokens if t and len(t) > 2 and t not in STOPWORDS]
    return tokens


def compute_keyword_frequency(papers: List[Dict], top_n: int = 40) -> List[Dict]:
    all_text = ""
    for paper in papers:
        title = paper.get("title", "") or ""
        abstract = paper.get("abstract", "") or ""
        all_text += " " + title + " " + abstract

    tokens = tokenize(all_text)
    counter = Counter(tokens)
    top_words = counter.most_common(top_n)

    return [{"word": word, "count": count} for word, count in top_words]


async def run(papers: List[Dict]) -> Dict:
    """
    Analysis Agent: Analyzes papers and generates 5 types of analysis:
    - publication_trend: Papers per year
    - top_authors: Top 15 authors by frequency
    - keyword_frequency: Top 40 keywords
    - citation_distribution: Citation count histogram buckets
    - emerging_topics: Words with highest delta (recent vs historical)
    """
    if not papers:
        return {
            "publication_trend": [],
            "top_authors": [],
            "keyword_frequency": [],
            "citation_distribution": [],
            "emerging_topics": [],
        }

    year_counts = {}
    for paper in papers:
        year = paper.get("year")
        if year:
            year_counts[year] = year_counts.get(year, 0) + 1
    publication_trend = sorted(
        [{"year": y, "count": c} for y, c in year_counts.items()],
        key=lambda x: x["year"],
    )

    author_counter = Counter()
    for paper in papers:
        authors = paper.get("authors", [])
        for author in authors:
            if author and author != "Unknown":
                author_counter[author] += 1
    top_authors = [
        {"name": name, "count": count} for name, count in author_counter.most_common(15)
    ]

    keyword_frequency = compute_keyword_frequency(papers, 40)

    citation_buckets = {
        "0": 0,
        "1-10": 0,
        "11-50": 0,
        "51-200": 0,
        "201-1000": 0,
        "1000+": 0,
    }
    for paper in papers:
        citations = paper.get("citation_count") or 0
        if citations == 0:
            citation_buckets["0"] += 1
        elif citations <= 10:
            citation_buckets["1-10"] += 1
        elif citations <= 50:
            citation_buckets["11-50"] += 1
        elif citations <= 200:
            citation_buckets["51-200"] += 1
        elif citations <= 1000:
            citation_buckets["201-1000"] += 1
        else:
            citation_buckets["1000+"] += 1
    citation_distribution = [
        {"bucket": k, "count": v} for k, v in citation_buckets.items()
    ]

    recent_papers = []
    historical_papers = []
    for paper in papers:
        year = paper.get("year", 2000) or 2000
        if year >= 2020:
            recent_papers.append(paper)
        else:
            historical_papers.append(paper)

    recent_keywords = {
        item["word"]: item["count"]
        for item in compute_keyword_frequency(recent_papers, 100)
        if recent_papers
    }
    historical_keywords = {
        item["word"]: item["count"]
        for item in compute_keyword_frequency(historical_papers, 100)
        if historical_papers
    }

    deltas = []
    total_recent = sum(recent_keywords.values()) if recent_keywords else 1
    total_historical = sum(historical_keywords.values()) if historical_keywords else 1

    for word in recent_keywords:
        recent_freq = recent_keywords[word] / total_recent
        historical_freq = historical_keywords.get(word, 0) / total_historical
        delta = recent_freq - historical_freq
        deltas.append(
            {
                "word": word,
                "delta": round(delta, 6),
                "recent_count": recent_keywords[word],
                "historical_count": historical_keywords.get(word, 0),
            }
        )

    deltas.sort(key=lambda x: x["delta"], reverse=True)
    emerging_topics = deltas[:10]

    return {
        "publication_trend": publication_trend,
        "top_authors": top_authors,
        "keyword_frequency": keyword_frequency,
        "citation_distribution": citation_distribution,
        "emerging_topics": emerging_topics,
    }
