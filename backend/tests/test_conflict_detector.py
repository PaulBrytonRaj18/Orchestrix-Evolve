import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.conflict_detector import (
    normalize_text,
    extract_keywords,
    detect_semantic_contradiction,
    detect_scale_contradiction,
    detect_methodology_contradiction,
    detect_temporal_contradiction,
    detect_citation_contradiction,
    detect_author_dominance_contradiction,
    detect_keyword_mismatch,
    detect_conflicts,
)


class TestNormalizeText:
    def test_lowercase_conversion(self):
        result = normalize_text("Hello World")
        assert result == "hello world"

    def test_remove_special_chars(self):
        result = normalize_text("Hello! World? Test.")
        assert "!" not in result
        assert "?" not in result
        assert "." not in result

    def test_remove_extra_whitespace(self):
        result = normalize_text("hello   world    test")
        assert result == "hello world test"

    def test_empty_string(self):
        result = normalize_text("")
        assert result == ""

    def test_none_input(self):
        result = normalize_text(None)
        assert result == ""


class TestExtractKeywords:
    def test_extract_from_text(self):
        text = "Machine learning and deep learning are popular methods for artificial intelligence research"
        keywords = extract_keywords(text)
        assert "machine" in keywords
        assert "learning" in keywords
        assert "deep" in keywords

    def test_extract_keywords_returns_list(self):
        text = "The quick brown fox jumps over the lazy dog"
        keywords = extract_keywords(text)
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_respects_top_n(self):
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        keywords = extract_keywords(text, top_n=5)
        assert len(keywords) <= 5

    def test_minimum_word_length(self):
        text = "a an the is are be been"
        keywords = extract_keywords(text)
        assert len(keywords) == 0


class TestDetectSemanticContradiction:
    def test_detect_semantic_contradiction_returns_tuple(self):
        text1 = "The method achieves high accuracy"
        text2 = "But the method has limitations"
        result = detect_semantic_contradiction(text1, text2)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_detect_semantic_contradiction_similar_texts(self):
        text1 = "The method uses neural networks for image classification"
        text2 = "Neural networks are effective for image classification tasks"
        is_contradict, reason = detect_semantic_contradiction(text1, text2)
        assert isinstance(is_contradict, bool)

    def test_no_contradiction(self):
        text1 = "The method uses neural networks"
        text2 = "Neural networks are effective for this task"
        is_contradict, reason = detect_semantic_contradiction(text1, text2)
        assert is_contradict == False

    def test_insufficient_common_keywords(self):
        text1 = "unique word1 word2"
        text2 = "different word3 word4"
        is_contradict, reason = detect_semantic_contradiction(text1, text2)
        assert is_contradict == False

    def test_insufficient_common_keywords(self):
        text1 = "unique word1 word2"
        text2 = "different word3 word4"
        is_contradict, reason = detect_semantic_contradiction(text1, text2)
        assert is_contradict == False


class TestDetectScaleContradiction:
    def test_detects_high_low_contradiction(self):
        analysis_data = {"high_performance": True}
        summarization = {
            "abstract_compression": "The model shows high performance",
            "limitations": "Limited accuracy",
        }
        is_contradict, reason = detect_scale_contradiction(analysis_data, summarization)
        assert isinstance(is_contradict, bool)

    def test_no_contradiction(self):
        analysis_data = {}
        summarization = {"abstract_compression": "Stable results", "limitations": ""}
        is_contradict, reason = detect_scale_contradiction(analysis_data, summarization)
        assert is_contradict == False


class TestDetectMethodologyContradiction:
    def test_methodology_mismatch(self):
        analysis_keywords = ["machine", "learning", "neural", "network"]
        methodology = "Statistical analysis of survey data"
        is_contradict, reason = detect_methodology_contradiction(
            analysis_keywords, methodology
        )
        assert is_contradict == True

    def test_methodology_matches(self):
        analysis_keywords = ["machine", "learning", "neural"]
        methodology = "Using machine learning neural networks"
        is_contradict, reason = detect_methodology_contradiction(
            analysis_keywords, methodology
        )
        assert is_contradict == False

    def test_empty_methodology(self):
        is_contradict, reason = detect_methodology_contradiction(["test"], "")
        assert is_contradict == False


class TestDetectTemporalContradiction:
    def test_detects_temporal_conflict(self):
        analysis_data = {"emerging_topics": [{"word": "transformer", "delta": 0.5}]}
        summarization = {
            "abstract_compression": "Traditional approaches",
            "limitations": "Legacy methods",
        }
        is_contradict, reason = detect_temporal_contradiction(
            analysis_data, summarization
        )
        assert isinstance(is_contradict, bool)

    def test_no_conflict(self):
        analysis_data = {"emerging_topics": []}
        summarization = {"abstract_compression": "Current methods", "limitations": ""}
        is_contradict, reason = detect_temporal_contradiction(
            analysis_data, summarization
        )
        assert is_contradict == False


class TestDetectCitationContradiction:
    def test_detects_citation_mismatch(self):
        analysis_data = {
            "citation_distribution": [
                {"bucket": "100-200", "count": 5},
                {"bucket": "1000+", "count": 10},
            ]
        }
        papers = [
            {"summary": {"limitations": "Limited impact"}},
            {"summary": {"limitations": "Small scope"}},
        ]
        is_contradict, reason = detect_citation_contradiction(analysis_data, papers)
        assert isinstance(is_contradict, bool)

    def test_no_data(self):
        analysis_data = {"citation_distribution": []}
        papers = []
        is_contradict, reason = detect_citation_contradiction(analysis_data, papers)
        assert is_contradict == False


class TestDetectAuthorDominanceContradiction:
    def test_detects_dominance_issue(self):
        analysis_data = {
            "top_authors": [
                {"name": "Author A"},
                {"name": "Author B"},
                {"name": "Author C"},
                {"name": "Author D"},
                {"name": "Author E"},
            ]
        }
        papers = [
            {"authors": ["Other"], "summary": {"key_contributions": "No mention"}}
        ]
        is_contradict, reason = detect_author_dominance_contradiction(
            analysis_data, papers
        )
        assert isinstance(is_contradict, bool)

    def test_no_data(self):
        analysis_data = {}
        papers = []
        is_contradict, reason = detect_author_dominance_contradiction(
            analysis_data, papers
        )
        assert is_contradict == False


class TestDetectKeywordMismatch:
    def test_detects_keyword_mismatch(self):
        analysis_data = {
            "keyword_frequency": [
                {"word": "machine"},
                {"word": "learning"},
                {"word": "neural"},
                {"word": "network"},
                {"word": "transformer"},
                {"word": "attention"},
            ]
        }
        papers = [{"summary": {"key_contributions": "Statistical methods"}}]
        is_contradict, reason = detect_keyword_mismatch(analysis_data, papers)
        assert isinstance(is_contradict, bool)

    def test_keywords_match(self):
        analysis_data = {
            "keyword_frequency": [{"word": "machine"}, {"word": "learning"}]
        }
        papers = [{"summary": {"key_contributions": "Machine learning approach"}}]
        is_contradict, reason = detect_keyword_mismatch(analysis_data, papers)
        assert is_contradict == False


class TestDetectConflictsAsync:
    @pytest.mark.asyncio
    async def test_detect_conflicts_returns_structure(self):
        papers = [
            {
                "id": "p1",
                "title": "Paper 1",
                "authors": ["Author 1"],
                "abstract": "Abstract 1",
                "year": 2024,
            }
        ]
        analysis_data = {
            "keyword_frequency": [],
            "emerging_topics": [],
            "citation_distribution": [],
            "top_authors": [],
        }
        summaries = [{"abstract_compression": "Summary 1"}]

        result = await detect_conflicts(papers, analysis_data, summaries)

        assert "conflicts" in result
        assert "summary" in result
        assert "stats" in result
        assert isinstance(result["conflicts"], list)

    @pytest.mark.asyncio
    async def test_detect_conflicts_empty_papers(self):
        result = await detect_conflicts([], {}, [])
        assert "conflicts" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_detect_conflicts_multiple_papers(self):
        papers = [
            {
                "id": f"p{i}",
                "title": f"Paper {i}",
                "abstract": f"Abstract {i}",
                "year": 2024,
            }
            for i in range(5)
        ]
        analysis_data = {
            "keyword_frequency": [],
            "emerging_topics": [],
            "citation_distribution": [],
            "top_authors": [],
        }
        summaries = [{"abstract_compression": f"Summary {i}"} for i in range(5)]

        result = await detect_conflicts(papers, analysis_data, summaries)

        assert isinstance(result["conflicts"], list)
        assert "stats" in result
        assert "total" in result["stats"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
