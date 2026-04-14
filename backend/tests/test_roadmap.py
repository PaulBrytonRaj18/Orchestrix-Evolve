import pytest
import asyncio
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.roadmap import (
    _compute_weighted_score,
    _identify_foundational_papers,
    _identify_gap_areas,
    _generate_next_queries,
    _extract_keywords_from_papers,
    _get_summary_text,
    run
)


class TestComputeWeightedScore:
    def test_high_citation_paper(self):
        paper = {"citation_count": 800, "year": 2018}
        score = _compute_weighted_score(paper)
        assert 0.8 <= score <= 1.0

    def test_low_citation_recent_paper(self):
        paper = {"citation_count": 50, "year": 2024}
        score = _compute_weighted_score(paper)
        assert 0.0 <= score <= 1.0

    def test_no_citations_old_paper(self):
        paper = {"citation_count": 0, "year": 2010}
        score = _compute_weighted_score(paper)
        assert score >= 0.3
        assert score <= 0.5

    def test_missing_fields(self):
        paper = {}
        score = _compute_weighted_score(paper)
        assert 0.0 <= score <= 1.0


class TestIdentifyFoundationalPapers:
    def test_filters_papers_before_2015(self):
        papers = [
            {"id": "1", "title": "Old Paper", "year": 2010, "citation_count": 500},
            {"id": "2", "title": "Recent Paper", "year": 2020, "citation_count": 100},
        ]
        analysis_data = {}
        result = _identify_foundational_papers(papers, analysis_data)
        assert len(result) <= 8
        assert all(p["year"] >= 2015 for p in result)

    def test_ranks_by_weighted_score(self):
        papers = [
            {"id": "1", "title": "High Impact", "year": 2020, "citation_count": 1000},
            {"id": "2", "title": "Low Impact", "year": 2020, "citation_count": 10},
        ]
        analysis_data = {}
        result = _identify_foundational_papers(papers, analysis_data)
        assert len(result) == 2
        assert result[0]["citation_count"] >= result[1]["citation_count"]

    def test_limits_to_8_papers(self):
        papers = [
            {"id": str(i), "title": f"Paper {i}", "year": 2020, "citation_count": 100 + i}
            for i in range(15)
        ]
        analysis_data = {}
        result = _identify_foundational_papers(papers, analysis_data)
        assert len(result) == 8

    def test_includes_priority_ranking(self):
        papers = [
            {"id": "1", "title": "Paper 1", "year": 2020, "citation_count": 100},
            {"id": "2", "title": "Paper 2", "year": 2020, "citation_count": 200},
        ]
        analysis_data = {}
        result = _identify_foundational_papers(papers, analysis_data)
        priorities = [p["priority"] for p in result]
        assert priorities == sorted(priorities)


class TestIdentifyGapAreas:
    def test_identifies_missing_areas(self):
        papers = [{"id": "1", "title": "Test", "year": 2020}]
        analysis_data = {"keyword_frequency": [], "emerging_topics": []}
        summaries = [{"abstract_compression": "Simple summary"}]
        notes = []
        conflicts = []
        result = _identify_gap_areas(papers, analysis_data, summaries, notes, conflicts)
        assert len(result) >= 1
        assert all("question" in gap for gap in result)

    def test_uses_conflicts_for_gaps(self):
        papers = [{"id": "1", "title": "Test", "year": 2020}]
        analysis_data = {"keyword_frequency": [], "emerging_topics": []}
        summaries = []
        notes = []
        conflicts = [
            {"severity": "high", "title": "Methodology conflict", "description": "Different methods used"}
        ]
        result = _identify_gap_areas(papers, analysis_data, summaries, notes, conflicts)
        assert any("Methodology conflict" in gap["question"] for gap in result)

    def test_uses_emerging_topics(self):
        papers = [{"id": "1", "title": "Test", "year": 2020}]
        analysis_data = {
            "keyword_frequency": [],
            "emerging_topics": [
                {"word": "transformer", "delta": 0.5}
            ]
        }
        summaries = []
        notes = []
        conflicts = []
        result = _identify_gap_areas(papers, analysis_data, summaries, notes, conflicts)
        assert any("transformer" in gap["question"].lower() for gap in result)

    def test_handles_empty_papers(self):
        papers = []
        analysis_data = {}
        summaries = []
        notes = []
        conflicts = []
        result = _identify_gap_areas(papers, analysis_data, summaries, notes, conflicts)
        assert isinstance(result, list)


class TestExtractKeywordsFromPapers:
    def test_extracts_title_keywords(self):
        papers = [
            {"title": "Deep Learning for Image Recognition", "abstract": "This paper presents a new approach."}
        ]
        keywords = _extract_keywords_from_papers(papers)
        assert "learning" in keywords or "image" in keywords or "recognition" in keywords

    def test_filters_common_words(self):
        papers = [
            {"title": "The Quick Brown Fox Jumps", "abstract": "This is a test."}
        ]
        keywords = _extract_keywords_from_papers(papers)
        assert "the" not in keywords
        assert "this" not in keywords
        assert "quick" in keywords or "brown" in keywords


class TestGetSummaryText:
    def test_handles_new_format(self):
        summary = {
            "derived_content": {
                "abstract_compression": "Test compression",
                "key_points": ["point1", "point2"]
            },
            "inferred_content": {
                "limitations": "Test limitations"
            }
        }
        text = _get_summary_text(summary)
        assert "Test compression" in text
        assert "Test limitations" in text

    def test_handles_flat_format(self):
        summary = {
            "abstract_compression": "Flat format compression",
            "limitations": "Flat format limitations"
        }
        text = _get_summary_text(summary)
        assert "Flat format compression" in text
        assert "Flat format limitations" in text

    def test_handles_empty_summary(self):
        text = _get_summary_text({})
        assert text == ""
        text = _get_summary_text(None)
        assert text == ""


class TestGenerateNextQueries:
    def test_generates_queries_from_emerging_topics(self):
        papers = [{"title": "Test", "abstract": "Test abstract"}]
        analysis_data = {
            "emerging_topics": [{"word": "transformer", "delta": 0.5}],
            "keyword_frequency": [],
            "top_authors": []
        }
        gaps = []
        result = _generate_next_queries(papers, analysis_data, gaps)
        assert len(result) >= 1
        assert any("transformer" in q["query"].lower() for q in result)
        assert all(q["trigger_action"] == "discovery" for q in result)

    def test_generates_queries_from_gaps(self):
        papers = [{"title": "Test", "abstract": "Test abstract"}]
        analysis_data = {"emerging_topics": [], "keyword_frequency": [], "top_authors": []}
        gaps = [{"question": "What about methodology comparison?"}]
        result = _generate_next_queries(papers, analysis_data, gaps)
        assert len(result) >= 1

    def test_limits_to_5_queries(self):
        papers = [{"title": "Test", "abstract": "Test abstract"}]
        analysis_data = {
            "emerging_topics": [
                {"word": f"topic{i}", "delta": 0.5} for i in range(5)
            ],
            "keyword_frequency": [
                {"word": f"keyword{i}"} for i in range(20)
            ],
            "top_authors": [{"name": "Test Author"}]
        }
        gaps = [{"question": f"Gap question {i}?"} for i in range(5)]
        result = _generate_next_queries(papers, analysis_data, gaps)
        assert len(result) <= 5

    def test_includes_default_query(self):
        papers = [{"title": "Test", "abstract": "Test abstract"}]
        analysis_data = {"emerging_topics": [], "keyword_frequency": [], "top_authors": []}
        gaps = []
        result = _generate_next_queries(papers, analysis_data, gaps)
        assert len(result) >= 1
        assert any("future research" in q["query"].lower() for q in result)


class TestRunFunction:
    def test_returns_valid_structure(self):
        papers = [
            {"id": "1", "title": "Test Paper 1", "year": 2020, "citation_count": 100, "abstract": "Test abstract 1"},
            {"id": "2", "title": "Test Paper 2", "year": 2021, "citation_count": 200, "abstract": "Test abstract 2"},
        ]
        analysis_data = {
            "publication_trend": [{"year": 2020, "count": 1}],
            "top_authors": [],
            "keyword_frequency": [],
            "citation_distribution": [],
            "emerging_topics": []
        }
        summaries = [
            {"abstract_compression": "Summary 1", "key_contributions": "Contributions 1"}
        ]
        notes = []
        conflicts = []

        result = asyncio.run(run(papers, analysis_data, summaries, notes, conflicts, "test-session"))

        assert "foundational_papers" in result
        assert "gap_areas" in result
        assert "next_query_suggestions" in result
        assert isinstance(result["foundational_papers"], list)
        assert isinstance(result["gap_areas"], list)
        assert isinstance(result["next_query_suggestions"], list)

    def test_handles_empty_papers(self):
        result = asyncio.run(run([], {}, [], [], [], "test-session"))
        assert result["foundational_papers"] == []
        assert result["gap_areas"] == []
        assert result["next_query_suggestions"] == []

    def test_handles_minimal_data(self):
        papers = [{"id": "1", "title": "Single Paper"}]
        analysis_data = {}
        summaries = []
        notes = []
        conflicts = []

        result = asyncio.run(run(papers, analysis_data, summaries, notes, conflicts, "test-session"))

        assert len(result["foundational_papers"]) >= 0
        assert len(result["gap_areas"]) >= 0
        assert len(result["next_query_suggestions"]) >= 0

    def test_foundational_papers_structure(self):
        papers = [
            {"id": "1", "title": "Paper 1", "year": 2020, "citation_count": 500},
            {"id": "2", "title": "Paper 2", "year": 2021, "citation_count": 300},
        ]
        analysis_data = {}
        summaries = []
        notes = []
        conflicts = []

        result = asyncio.run(run(papers, analysis_data, summaries, notes, conflicts, "test-session"))

        for paper in result["foundational_papers"]:
            assert "paper_id" in paper
            assert "title" in paper
            assert "reason" in paper
            assert "citation_count" in paper
            assert "year" in paper
            assert "priority" in paper

    def test_gap_areas_structure(self):
        papers = [{"id": "1", "title": "Paper 1", "year": 2020}]
        analysis_data = {}
        summaries = []
        notes = []
        conflicts = []

        result = asyncio.run(run(papers, analysis_data, summaries, notes, conflicts, "test-session"))

        for gap in result["gap_areas"]:
            assert "question" in gap
            assert "evidence" in gap
            assert "related_papers" in gap
            assert "severity" in gap

    def test_next_queries_structure(self):
        papers = [{"id": "1", "title": "Paper 1", "year": 2020}]
        analysis_data = {}
        summaries = []
        notes = []
        conflicts = []

        result = asyncio.run(run(papers, analysis_data, summaries, notes, conflicts, "test-session"))

        for query in result["next_query_suggestions"]:
            assert "query" in query
            assert "rationale" in query
            assert "trigger_action" in query
            assert "expected_insight" in query
            assert query["trigger_action"] == "discovery"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
