import math
import re
import uuid
from datetime import UTC, datetime

from constants import STOPWORDS

_QUESTION_WORDS = {
    "what",
    "which",
    "effective",
    "ways",
    "address",
    "latest",
    "developments",
    "there",
    "important",
    "researchers",
    "represented",
    "collection",
    "papers",
    "provide",
    "context",
    "earlier",
    "years",
    "unresolved",
    "conflict",
    "detected",
    "foundational",
    "open",
    "questions",
    "area",
    "research",
    "about",
}


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _current_year() -> int:
    return datetime.now(UTC).year


def _compute_weighted_score(paper: dict) -> float:
    """Foundational-ness in [0, 1].

    Blends absolute impact (log citations, saturating at ~10k) with citation
    *velocity* (citations per year since publication), so both classics and fast-rising
    recent work surface. The old formula rewarded age itself and hard-excluded
    everything before 2015 — which removed the truly foundational papers.
    """
    citations = max(paper.get("citation_count") or 0, 0)
    year = paper.get("year") or _current_year()
    age = max(_current_year() - year, 0) + 1
    impact = min(math.log1p(citations) / math.log1p(10_000), 1.0)
    velocity = min(math.log1p(citations / age) / math.log1p(500), 1.0)
    return round(0.65 * impact + 0.35 * velocity, 4)


def _extract_years(analysis_trend_data: dict) -> dict:
    publication_trend = analysis_trend_data.get("publication_trend", [])
    years = [item.get("year") for item in publication_trend if item.get("year")]
    return {"min": min(years, default=2000), "max": max(years, default=_current_year())}


def _identify_foundational_papers(papers: list[dict], analysis_trend_data: dict) -> list[dict]:
    current_year = _current_year()
    ranked = sorted(papers, key=_compute_weighted_score, reverse=True)

    foundational = []
    for idx, paper in enumerate(ranked[:8]):
        citation_count = paper.get("citation_count") or 0
        year = paper.get("year")
        if citation_count > 500:
            reason = f"Highly cited ({citation_count:,} citations) foundational work"
        elif citation_count > 100:
            reason = "Well-cited paper with significant impact"
        elif year and year >= current_year - 3:
            reason = "Recent paper with potential for future impact"
        else:
            reason = "Established reference in the field"

        foundational.append(
            {
                "paper_id": paper.get("id") or _generate_uuid(),
                "title": paper.get("title", "Untitled"),
                "reason": reason,
                "citation_count": citation_count,
                "year": year,
                "priority": idx + 1,
            }
        )
    return foundational


def _get_summary_text(summary: dict) -> str:
    if isinstance(summary, dict):
        derived = summary.get("derived_content", {}) or {}
        inferred = summary.get("inferred_content", {}) or {}
        text_parts = [
            derived.get("abstract_compression", ""),
            derived.get("key_points", []),
            inferred.get("explanation_approach", ""),
            inferred.get("limitations", ""),
            inferred.get("strengths", ""),
            summary.get("abstract_compression", ""),
            summary.get("key_contributions", ""),
            summary.get("limitations", ""),
            summary.get("methodology", ""),
        ]
        return " ".join(str(p) for p in text_parts if p)
    return str(summary) if summary else ""


def _identify_gap_areas(
    papers: list[dict],
    analysis_trend_data: dict,
    summaries: list[dict],
    notes: list[dict],
    conflicts: list[dict],
) -> list[dict]:
    gaps = []

    keyword_freq = analysis_trend_data.get("keyword_frequency", [])
    high_freq_keywords = {item.get("word", "").lower() for item in keyword_freq[:30]}

    common_research_patterns = [
        ("methodology", "method", "approach"),
        ("performance", "accuracy", "efficiency"),
        ("comparison", "baseline", "evaluation"),
        ("application", "use case", "deployment"),
        ("limitation", "challenge", "problem"),
    ]

    discussed_areas = set()
    for summary in summaries:
        text = _get_summary_text(summary).lower()
        for pattern_group in common_research_patterns:
            for pattern in pattern_group:
                if pattern in text:
                    discussed_areas.add(pattern_group[0])

    missing_areas = []
    for pattern_group in common_research_patterns:
        area = pattern_group[0]
        if area not in discussed_areas and area not in high_freq_keywords:
            missing_areas.append(area)

    if missing_areas:
        gaps.append(
            {
                "question": f"Effective ways to address {', '.join(missing_areas[:2])} in research?",
                "evidence": f"Limited discussion of {missing_areas[0]} found across collected papers",
                "related_papers": [],
                "severity": "medium",
            }
        )

    emerging_topics = analysis_trend_data.get("emerging_topics", [])
    if emerging_topics:
        top_emerging = emerging_topics[:3]
        emerging_words = [t.get("word", "") for t in top_emerging]
        gaps.append(
            {
                "question": f"What are the latest developments in {', '.join(emerging_words)}?",
                "evidence": "Emerging topics detected with positive delta in recent years",
                "related_papers": [],
                "severity": "high",
            }
        )

    if conflicts:
        high_severity = [c for c in conflicts if c.get("severity") == "high"]
        if high_severity:
            conflict = high_severity[0]
            gaps.append(
                {
                    "question": conflict.get("title", "Unresolved conflict detected"),
                    "evidence": conflict.get(
                        "description", "Contradictory findings in existing research"
                    ),
                    "related_papers": [],
                    "severity": "high",
                }
            )

    paper_years = [p.get("year") for p in papers if p.get("year")]
    if paper_years:
        year_range = max(paper_years) - min(paper_years)
        if year_range < 3 and len(papers) < 10:
            gaps.append(
                {
                    "question": "Are there foundational papers from earlier"
                    " years that provide context?",
                    "evidence": (
                        f"Limited year range ({min(paper_years)}-{max(paper_years)})"
                        " suggests narrow temporal coverage"
                    ),
                    "related_papers": [],
                    "severity": "low",
                }
            )

    top_authors = analysis_trend_data.get("top_authors", [])
    if len(top_authors) < 5:
        gaps.append(
            {
                "question": "Are there important researchers not represented in this collection?",
                "evidence": "Limited author diversity detected in current papers",
                "related_papers": [],
                "severity": "medium",
            }
        )

    if not gaps:
        gaps.append(
            {
                "question": "What are the key open questions in this research area?",
                "evidence": "Based on analysis of collected papers",
                "related_papers": [],
                "severity": "medium",
            }
        )

    return gaps[:6]


def _extract_keywords_from_papers(papers: list[dict]) -> list[str]:
    word_counts = {}
    for paper in papers:
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract
        words = text.split()
        for word in words:
            word = "".join(c for c in word if c.isalnum())
            if len(word) > 4 and word not in STOPWORDS:
                word_counts[word] = word_counts.get(word, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:20]]


def _topic_from(papers: list[dict], query: str | None) -> str:
    if query:
        return " ".join(query.split()[:6])
    keywords = _extract_keywords_from_papers(papers)
    return " ".join(keywords[:2])


def _add_query(queries: list[dict], query: str, rationale: str, insight: str) -> None:
    query = " ".join(query.split())
    if query and query.lower() not in {q["query"].lower() for q in queries}:
        queries.append(
            {
                "query": query,
                "rationale": rationale,
                "trigger_action": "discovery",
                "expected_insight": insight,
            }
        )


def _generate_next_queries(
    papers: list[dict],
    analysis_trend_data: dict,
    gaps: list[dict],
    query: str | None = None,
) -> list[dict]:
    """Up to five follow-up searches, each anchored on the session topic so they are
    runnable queries (not truncated question fragments like "What are the latest")."""
    queries: list[dict] = []
    topic = _topic_from(papers, query)
    year = _current_year()

    for item in (analysis_trend_data.get("emerging_topics") or [])[:2]:
        word = item.get("word", "")
        if word and word.lower() not in topic.lower():
            _add_query(
                queries,
                f"{topic} {word} {year - 1} {year}",
                f"'{word}' is rising in recent papers of this collection",
                f"Latest developments combining {topic or 'this area'} and {word}",
            )

    keywords = [
        k.get("word", "")
        for k in (analysis_trend_data.get("keyword_frequency") or [])
        if k.get("word") and k.get("word", "").lower() not in topic.lower()
    ]
    if keywords:
        _add_query(
            queries,
            f"{topic} {keywords[0]} survey",
            f"'{keywords[0]}' is a dominant theme; a survey consolidates it",
            f"Comprehensive overview of {keywords[0]}",
        )

    for gap in gaps:
        if len(queries) >= 3:
            break
        gap_terms = [
            w
            for w in re.findall(r"[a-z]+", gap.get("question", "").lower())
            if len(w) > 3 and w not in STOPWORDS and w not in _QUESTION_WORDS
        ][:3]
        if gap_terms:
            _add_query(
                queries,
                f"{topic} {' '.join(gap_terms)}",
                f"Address gap: {gap.get('question', '')[:80]}",
                "Evidence to close an identified research gap",
            )

    top_authors = analysis_trend_data.get("top_authors") or []
    if top_authors and top_authors[0].get("name"):
        author = top_authors[0]["name"]
        _add_query(
            queries,
            f"{author} {topic}",
            f"{author} is the most prolific author in this collection",
            f"Recent work by {author}",
        )

    _add_query(
        queries,
        f"{topic} future research directions open problems",
        "Identify open problems and future research opportunities",
        "Potential research directions",
    )
    if len(queries) > 5:  # keep the always-useful open-problems query
        queries = queries[:4] + queries[-1:]
    return queries


async def run(
    papers: list[dict],
    analysis_trend_data: dict,
    summaries: list[dict],
    notes: list[dict],
    conflicts: list[dict],
    session_id: str,
    query: str | None = None,
) -> dict:
    if not papers:
        return {"foundational_papers": [], "gap_areas": [], "next_query_suggestions": []}

    foundational_papers = _identify_foundational_papers(papers, analysis_trend_data)

    gap_areas = _identify_gap_areas(papers, analysis_trend_data, summaries, notes, conflicts)

    next_query_suggestions = _generate_next_queries(papers, analysis_trend_data, gap_areas, query)

    return {
        "foundational_papers": foundational_papers,
        "gap_areas": gap_areas,
        "next_query_suggestions": next_query_suggestions,
    }
