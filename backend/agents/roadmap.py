from typing import List, Dict, Optional
from datetime import datetime


def _generate_uuid() -> str:
    import uuid
    return str(uuid.uuid4())


def _compute_weighted_score(paper: Dict) -> float:
    citation_count = paper.get("citation_count") or 0
    year = paper.get("year") or 2000
    
    current_year = datetime.now().year
    recency = min((current_year - year) / 10, 1.0)
    
    citation_score = min(citation_count / 1000, 1.0)
    
    return (citation_score * 0.6) + (recency * 0.4)


def _extract_years(analysis_trend_data: Dict) -> Dict:
    publication_trend = analysis_trend_data.get("publication_trend", [])
    years = [item.get("year") for item in publication_trend if item.get("year")]
    current_year = datetime.now().year
    return {
        "min": min(years) if years else 2000,
        "max": max(years) if years else current_year
    }


def _identify_foundational_papers(papers: List[Dict], analysis_trend_data: Dict) -> List[Dict]:
    current_year = datetime.now().year
    
    filtered = [p for p in papers if p.get("year", 0) >= 2015]
    
    for paper in filtered:
        paper["_weighted_score"] = _compute_weighted_score(paper)
    
    sorted_papers = sorted(filtered, key=lambda x: x.get("_weighted_score", 0), reverse=True)
    
    foundational = []
    for idx, paper in enumerate(sorted_papers[:8]):
        citation_count = paper.get("citation_count") or 0
        year = paper.get("year") or "N/A"
        
        if citation_count > 500:
            reason = f"Highly cited ({citation_count}+ citations) foundational work"
        elif citation_count > 100:
            reason = f"Well-cited paper with significant impact"
        elif year >= current_year - 3:
            reason = f"Recent paper with potential for future impact"
        else:
            reason = f"Established reference in the field"
        
        foundational.append({
            "paper_id": paper.get("id", _generate_uuid()),
            "title": paper.get("title", "Untitled"),
            "reason": reason,
            "citation_count": citation_count,
            "year": year,
            "priority": idx + 1
        })
    
    return foundational


def _get_summary_text(summary: Dict) -> str:
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
            summary.get("methodology", "")
        ]
        return " ".join(str(p) for p in text_parts if p)
    return str(summary) if summary else ""


def _identify_gap_areas(
    papers: List[Dict],
    analysis_trend_data: Dict,
    summaries: List[Dict],
    notes: List[Dict],
    conflicts: List[Dict]
) -> List[Dict]:
    gaps = []
    paper_titles = {p.get("id"): p.get("title", "") for p in papers}
    
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
        gaps.append({
            "question": f"How to effectively address {', '.join(missing_areas[:2])} in current research?",
            "evidence": f"Limited discussion of {missing_areas[0]} found across collected papers",
            "related_papers": [],
            "severity": "medium"
        })
    
    emerging_topics = analysis_trend_data.get("emerging_topics", [])
    if emerging_topics:
        top_emerging = emerging_topics[:3]
        emerging_words = [t.get("word", "") for t in top_emerging]
        gaps.append({
            "question": f"What are the latest developments in {', '.join(emerging_words)}?",
            "evidence": f"Emerging topics detected with positive delta in recent years",
            "related_papers": [],
            "severity": "high"
        })
    
    if conflicts:
        high_severity = [c for c in conflicts if c.get("severity") == "high"]
        if high_severity:
            conflict = high_severity[0]
            gaps.append({
                "question": conflict.get("title", "Unresolved conflict detected"),
                "evidence": conflict.get("description", "Contradictory findings in existing research"),
                "related_papers": [],
                "severity": "high"
            })
    
    paper_years = [p.get("year") for p in papers if p.get("year")]
    if paper_years:
        year_range = max(paper_years) - min(paper_years)
        if year_range < 3 and len(papers) < 10:
            gaps.append({
                "question": "Are there foundational papers from earlier years that provide context?",
                "evidence": f"Limited year range ({min(paper_years)}-{max(paper_years)}) suggests narrow temporal coverage",
                "related_papers": [],
                "severity": "low"
            })
    
    top_authors = analysis_trend_data.get("top_authors", [])
    if len(top_authors) < 5:
        gaps.append({
            "question": "Are there important researchers not represented in this collection?",
            "evidence": "Limited author diversity detected in current papers",
            "related_papers": [],
            "severity": "medium"
        })
    
    if not gaps:
        gaps.append({
            "question": "What are the key open questions in this research area?",
            "evidence": "Based on analysis of collected papers",
            "related_papers": [],
            "severity": "medium"
        })
    
    return gaps[:6]


def _extract_keywords_from_papers(papers: List[Dict]) -> List[str]:
    common_words = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", 
        "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
        "its", "may", "new", "now", "old", "see", "two", "way", "who", "boy",
        "did", "man", "end", "put", "say", "she", "too", "use", "this", "that",
        "with", "have", "from", "they", "will", "would", "there", "their", "what",
        "about", "which", "when", "make", "like", "time", "just", "into", "year",
        "paper", "research", "study", "method", "result", "data", "system", "model"
    }
    
    word_counts = {}
    for paper in papers:
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract
        words = text.split()
        for word in words:
            word = ''.join(c for c in word if c.isalnum())
            if len(word) > 4 and word not in common_words:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:20]]


def _generate_next_queries(
    papers: List[Dict],
    analysis_trend_data: Dict,
    gaps: List[Dict]
) -> List[Dict]:
    queries = []
    paper_keywords = _extract_keywords_from_papers(papers)
    
    emerging_topics = analysis_trend_data.get("emerging_topics", [])
    if emerging_topics:
        top_topic = emerging_topics[0]
        word = top_topic.get("word", "")
        if word:
            queries.append({
                "query": f"{word} latest research 2024 2025",
                "rationale": f"Follow up on emerging topic '{word}' identified in analysis",
                "trigger_action": "discovery",
                "expected_insight": f"Latest developments in {word}"
            })
    
    keyword_freq = analysis_trend_data.get("keyword_frequency", [])
    if len(keyword_freq) > 10:
        second_topic = keyword_freq[5].get("word", "")
        if second_topic and second_topic.lower() not in [q.get("query", "").lower() for q in queries]:
            queries.append({
                "query": f"{second_topic} survey review",
                "rationale": f"Deep dive into '{second_topic}' area",
                "trigger_action": "discovery",
                "expected_insight": f"Comprehensive overview of {second_topic}"
            })
    
    if gaps:
        for gap in gaps[:2]:
            question = gap.get("question", "")
            if question and len(queries) < 5:
                query_terms = " ".join(question.split()[:5])
                if query_terms.lower() not in [q.get("query", "").lower() for q in queries]:
                    queries.append({
                        "query": f"{query_terms}",
                        "rationale": f"Address gap: {question[:50]}...",
                        "trigger_action": "discovery",
                        "expected_insight": "Fill identified research gap"
                    })
    
    top_authors = analysis_trend_data.get("top_authors", [])
    if top_authors:
        top_author = top_authors[0].get("name", "")
        if top_author and len(queries) < 5:
            last_name = top_author.split()[-1] if " " in top_author else top_author
            queries.append({
                "query": f"{last_name} latest publications",
                "rationale": f"Follow work of leading researcher {top_author}",
                "trigger_action": "discovery",
                "expected_insight": f"Recent work by {top_author}"
            })
    
    if paper_keywords and len(queries) < 5:
        main_topic = paper_keywords[0] if paper_keywords else None
        if main_topic:
            queries.append({
                "query": f"{main_topic} challenges limitations",
                "rationale": f"Explore open challenges in {main_topic}",
                "trigger_action": "discovery",
                "expected_insight": f"Identify limitations and future directions in {main_topic}"
            })
    
    if paper_keywords and len(queries) < 5:
        second_topic = paper_keywords[1] if len(paper_keywords) > 1 else paper_keywords[0]
        queries.append({
            "query": f"{second_topic} comparison baseline",
            "rationale": f"Compare different approaches in {second_topic}",
            "trigger_action": "discovery",
            "expected_insight": f"Comparative analysis of {second_topic}"
        })
    
    default_query = "future research directions open problems"
    if default_query.lower() not in [q.get("query", "").lower() for q in queries]:
        queries.append({
            "query": default_query,
            "rationale": "Identify open problems and future research opportunities",
            "trigger_action": "discovery",
            "expected_insight": "Potential research directions"
        })
    
    return queries[:5]


async def run(
    papers: List[Dict],
    analysis_trend_data: Dict,
    summaries: List[Dict],
    notes: List[Dict],
    conflicts: List[Dict],
    session_id: str
) -> Dict:
    if not papers:
        return {
            "foundational_papers": [],
            "gap_areas": [],
            "next_query_suggestions": []
        }
    
    total_papers = len(papers)
    
    foundational_papers = _identify_foundational_papers(papers, analysis_trend_data)
    
    gap_areas = _identify_gap_areas(papers, analysis_trend_data, summaries, notes, conflicts)
    
    next_query_suggestions = _generate_next_queries(papers, analysis_trend_data, gap_areas)
    
    return {
        "foundational_papers": foundational_papers,
        "gap_areas": gap_areas,
        "next_query_suggestions": next_query_suggestions
    }
