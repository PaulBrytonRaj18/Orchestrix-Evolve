import re
from typing import List, Dict, Tuple
from datetime import datetime, timezone


NEGATION_WORDS = {
    "not",
    "no",
    "never",
    "neither",
    "nor",
    "none",
    "nothing",
    "cannot",
    "can't",
    "won't",
    "wouldn't",
    "shouldn't",
    "couldn't",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
    "doesn't",
    "don't",
    "haven't",
    "hasn't",
    "hadn't",
    "but",
    "however",
    "although",
    "unlike",
    "contrary",
    "opposite",
    "instead",
    "rather",
}

CONFLICT_INDICATORS = [
    "contradict",
    "conflict",
    "disagree",
    "oppose",
    "contrast",
    "however",
    "whereas",
    "but",
    "yet",
    "despite",
    "although",
    "unlike",
    "whereas",
    "while",
    "nevertheless",
    "nonetheless",
]

SCALE_WORDS = {
    "high": [
        "high",
        "large",
        "significant",
        "major",
        "substantial",
        "dramatic",
        "steep",
    ],
    "low": ["low", "small", "minor", "insignificant", "minimal", "slight", "modest"],
    "increase": ["increase", "increase", "grow", "rise", "improve", "enhance", "boost"],
    "decrease": ["decrease", "reduce", "lower", "decline", "drop", "worsen", "degrade"],
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_keywords(text: str, top_n: int = 20) -> List[str]:
    normalized = normalize_text(text)
    words = normalized.split()
    stopwords = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "been",
        "be",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
    }
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    return keywords[:top_n]


def detect_semantic_contradiction(text1: str, text2: str) -> Tuple[bool, str]:
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    words1 = set(norm1.split())
    words2 = set(norm2.split())

    negation_found = False
    for word in NEGATION_WORDS:
        if word in words1 or word in words2:
            negation_found = True
            break

    common_keywords = words1.intersection(words2)
    if len(common_keywords) < 3:
        return False, ""

    for indicator in CONFLICT_INDICATORS:
        if indicator in norm1 or indicator in norm2:
            return True, f"Contradiction indicator found: '{indicator}'"

    if negation_found:
        word_diff = len(words1.union(words2)) - len(common_keywords)
        if word_diff > len(common_keywords) * 0.5:
            return True, "Semantic opposition detected with negation patterns"

    return False, ""


def detect_scale_contradiction(
    analysis_data: Dict, summarization: Dict
) -> Tuple[bool, str]:
    analysis_keywords = extract_keywords(str(analysis_data))
    summary_keywords = extract_keywords(summarization.get("abstract_compression", ""))

    high_words = set()
    low_words = set()

    for kw in analysis_keywords:
        for scale, words in SCALE_WORDS.items():
            if any(w in kw for w in words):
                if scale in ["high", "increase"]:
                    high_words.add(kw)
                else:
                    low_words.add(kw)

    for kw in summary_keywords:
        for scale, words in SCALE_WORDS.items():
            if any(w in kw for w in words):
                if scale in ["high", "increase"]:
                    high_words.add(kw)
                else:
                    low_words.add(kw)

    if high_words and low_words:
        return (
            True,
            f"Scale contradiction: analysis suggests {', '.join(list(high_words)[:3])} while summary indicates {', '.join(list(low_words)[:3])}",
        )

    return False, ""


def detect_methodology_contradiction(
    analysis_keywords: List[str], methodology: str
) -> Tuple[bool, str]:
    if not methodology:
        return False, ""

    method_keywords = extract_keywords(methodology)
    common = set(analysis_keywords).intersection(set(method_keywords))

    if len(common) < 2:
        return (
            True,
            f"Methodology ('{methodology[:50]}...') may contradict analysis focus areas",
        )

    return False, ""


def detect_temporal_contradiction(
    analysis_data: Dict, summarization: Dict
) -> Tuple[bool, str]:
    emerging = analysis_data.get("emerging_topics", [])
    recent_keywords = set()

    for topic in emerging[:5]:
        if isinstance(topic, dict) and topic.get("delta", 0) > 0:
            recent_keywords.add(topic.get("word", ""))

    summary_text = normalize_text(
        summarization.get("abstract_compression", "")
        + " "
        + summarization.get("limitations", "")
    )

    historical_indicators = {
        "traditional",
        "older",
        "classical",
        "legacy",
        "outdated",
        "previous",
        "earlier",
    }
    if recent_keywords and any(ind in summary_text for ind in historical_indicators):
        return (
            True,
            "Temporal contradiction: Analysis shows emerging trends but summary mentions historical/classical approaches",
        )

    return False, ""


def detect_citation_contradiction(
    analysis_data: Dict, papers: List[Dict]
) -> Tuple[bool, str]:
    citation_dist = analysis_data.get("citation_distribution", [])

    total_papers = sum(b.get("count", 0) for b in citation_dist)
    if total_papers == 0:
        return False, ""

    highly_cited = 0
    for bucket in citation_dist:
        if bucket.get("bucket", "") in ["201-1000", "1000+"]:
            highly_cited += bucket.get("count", 0)

    highly_cited_ratio = highly_cited / total_papers if total_papers > 0 else 0

    low_cited_summaries = 0
    for paper in papers:
        summary = paper.get("summary", {})
        if summary and summary.get("limitations"):
            if "limited" in normalize_text(
                summary.get("limitations", "")
            ) or "small" in normalize_text(summary.get("limitations", "")):
                low_cited_summaries += 1

    if highly_cited_ratio > 0.3 and low_cited_summaries > len(papers) * 0.3:
        return (
            True,
            f"Contradiction: {highly_cited_ratio * 100:.0f}% papers are highly cited but {low_cited_summaries} summaries mention limited impact",
        )

    return False, ""


def detect_author_dominance_contradiction(
    analysis_data: Dict, papers: List[Dict]
) -> Tuple[bool, str]:
    top_authors = analysis_data.get("top_authors", [])

    if not top_authors or len(top_authors) < 5:
        return False, ""

    top_3_authors = set(a.get("name", "").lower() for a in top_authors[:3])

    diverse_authors = set()
    for paper in papers:
        for author in paper.get("authors", []):
            diverse_authors.add(author.lower())

    top_3_diversity_ratio = (
        len(top_3_authors) / len(diverse_authors) if diverse_authors else 0
    )

    summary_mentions = 0
    for paper in papers:
        summary = paper.get("summary", {})
        if summary:
            contrib = summary.get("key_contributions", "").lower()
            for author in top_3_authors:
                if author in contrib:
                    summary_mentions += 1
                    break

    if top_3_diversity_ratio < 0.3 and summary_mentions < len(papers) * 0.2:
        return (
            True,
            "Contradiction: Few authors dominate but their contributions are rarely highlighted in summaries",
        )

    return False, ""


def detect_keyword_mismatch(
    analysis_data: Dict, papers: List[Dict]
) -> Tuple[bool, str]:
    analysis_keywords = set(
        k.get("word", "").lower()
        for k in analysis_data.get("keyword_frequency", [])[:20]
    )

    summary_keywords = set()
    for paper in papers:
        summary = paper.get("summary", {})
        if summary:
            contrib = summary.get("key_contributions", "") or ""
            summary_keywords.update(extract_keywords(contrib, 30))

    analysis_keywords = {k for k in analysis_keywords if len(k) > 4}
    summary_keywords = {k for k in summary_keywords if len(k) > 4}

    overlap = analysis_keywords.intersection(summary_keywords)

    if len(analysis_keywords) > 5 and len(overlap) / len(analysis_keywords) < 0.3:
        missing = analysis_keywords - overlap
        return (
            True,
            f"Keyword mismatch: Analysis highlights {', '.join(list(missing)[:5])} but these aren't emphasized in summaries",
        )

    return False, ""


async def detect_conflicts(
    papers: List[Dict], analysis_data: Dict, summarizations: List[Dict]
) -> Dict:
    """
    Detects conflicts between Analysis Agent insights and Summarization Agent outputs.

    Returns a dict with:
    - conflicts: List of detected conflict objects
    - summary: Human-readable summary of conflicts found
    """
    conflicts = []

    paper_summaries = {}
    for paper, summary in zip(papers, summarizations):
        if isinstance(summary, dict):
            derived = summary.get("derived_content", {}) or {}
            inferred = summary.get("inferred_content", {}) or {}
            paper_summaries[paper.get("id", paper.get("title", ""))] = {
                "abstract_compression": derived.get("abstract_compression", ""),
                "limitations": inferred.get("limitations", ""),
                "methodology": inferred.get("explanation_approach", ""),
                "key_contributions": "\n".join(derived.get("key_points", [])) if isinstance(derived.get("key_points"), list) else str(derived.get("key_points", "")),
            }

    analysis_keywords = []
    if analysis_data.get("keyword_frequency"):
        analysis_keywords = [
            k.get("word", "").lower() for k in analysis_data["keyword_frequency"][:20]
        ]

    for paper_id, summary in paper_summaries.items():
        abstract = summary.get("abstract_compression", "")
        limitations = summary.get("limitations", "")
        methodology = summary.get("methodology", "")
        contributions = summary.get("key_contributions", "")

        all_summary_text = f"{abstract} {limitations} {methodology} {contributions}"

        is_contradict, reason = detect_semantic_contradiction(
            str(analysis_keywords), all_summary_text
        )
        if is_contradict:
            conflicts.append(
                {
                    "conflict_type": "semantic_contradiction",
                    "severity": "medium",
                    "title": f"Semantic Contradiction in Paper Analysis",
                    "description": reason,
                    "analysis_insight": f"Analysis highlights: {', '.join(analysis_keywords[:10])}",
                    "summarization_insight": f"Summary states: {abstract[:200]}...",
                    "paper_id": paper_id,
                }
            )

        is_contradict, reason = detect_methodology_contradiction(
            analysis_keywords, methodology
        )
        if is_contradict:
            conflicts.append(
                {
                    "conflict_type": "methodology_mismatch",
                    "severity": "low",
                    "title": f"Methodology Alignment Issue",
                    "description": reason,
                    "analysis_insight": f"Primary analysis keywords: {', '.join(analysis_keywords[:10])}",
                    "summarization_insight": f"Methodology: {methodology[:150]}...",
                    "paper_id": paper_id,
                }
            )

    is_contradict, reason = detect_temporal_contradiction(analysis_data, {})
    if is_contradict:
        conflicts.append(
            {
                "conflict_type": "temporal_contradiction",
                "severity": "high",
                "title": "Temporal Perspective Conflict",
                "description": reason,
                "analysis_insight": f"Emerging topics detected: {[t.get('word') for t in analysis_data.get('emerging_topics', [])[:5]]}",
                "summarization_insight": "Summary contains historical/traditional references",
                "paper_id": None,
            }
        )

    is_contradict, reason = detect_citation_contradiction(analysis_data, papers)
    if is_contradict:
        conflicts.append(
            {
                "conflict_type": "citation_impact_contradiction",
                "severity": "medium",
                "title": "Citation Impact vs Perceived Limitations",
                "description": reason,
                "analysis_insight": f"Citation distribution shows highly cited papers",
                "summarization_insight": "Multiple papers mention limited impact",
                "paper_id": None,
            }
        )

    is_contradict, reason = detect_author_dominance_contradiction(analysis_data, papers)
    if is_contradict:
        conflicts.append(
            {
                "conflict_type": "author_impact_contradiction",
                "severity": "low",
                "title": "Author Dominance vs Contribution Visibility",
                "description": reason,
                "analysis_insight": f"Top authors by publication count",
                "summarization_insight": "Dominant authors' contributions underemphasized",
                "paper_id": None,
            }
        )

    is_contradict, reason = detect_keyword_mismatch(analysis_data, papers)
    if is_contradict:
        conflicts.append(
            {
                "conflict_type": "keyword_mismatch",
                "severity": "medium",
                "title": "Analysis vs Summary Keyword Discrepancy",
                "description": reason,
                "analysis_insight": f"Analysis keywords: {', '.join([k.get('word') if isinstance(k, dict) else str(k) for k in list(analysis_data.get('keyword_frequency', [])[:10])])}",
                "summarization_insight": "Summaries focus on different themes",
                "paper_id": None,
            }
        )

    high_severity = sum(1 for c in conflicts if c.get("severity") == "high")
    medium_severity = sum(1 for c in conflicts if c.get("severity") == "medium")
    low_severity = sum(1 for c in conflicts if c.get("severity") == "low")

    if conflicts:
        summary = f"Detected {len(conflicts)} potential conflicts: {high_severity} high severity, {medium_severity} medium severity, {low_severity} low severity. Review the conflicts panel for details."
    else:
        summary = "No significant conflicts detected between Analysis and Summarization outputs."

    return {
        "conflicts": conflicts,
        "summary": summary,
        "stats": {
            "total": len(conflicts),
            "high": high_severity,
            "medium": medium_severity,
            "low": low_severity,
        },
    }
