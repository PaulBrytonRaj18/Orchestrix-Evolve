import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.citation import (
    format_authors_apa,
    format_authors_mla,
    format_authors_ieee,
    format_authors_chicago,
    generate_citation,
    run,
)


class TestFormatAuthorsAPA:
    def test_single_author(self):
        authors = ["John Smith"]
        result = format_authors_apa(authors)
        assert result == "John Smith"

    def test_multiple_authors(self):
        authors = ["John Smith", "Jane Doe", "Bob Wilson"]
        result = format_authors_apa(authors)
        assert "John Smith" in result
        assert "Jane Doe" in result
        assert "Bob Wilson" in result

    def test_empty_authors(self):
        result = format_authors_apa([])
        assert result == "Unknown Author"

    def test_none_authors(self):
        result = format_authors_apa(None)
        assert result == "Unknown Author"


class TestFormatAuthorsMLA:
    def test_single_author(self):
        authors = ["John Smith"]
        result = format_authors_mla(authors)
        assert result == "John Smith"

    def test_multiple_authors(self):
        authors = ["John Smith", "Jane Doe"]
        result = format_authors_mla(authors)
        assert result == "John Smith et al."

    def test_empty_authors(self):
        result = format_authors_mla([])
        assert result == "Unknown Author"


class TestFormatAuthorsIEEE:
    def test_single_author(self):
        authors = ["John Smith"]
        result = format_authors_ieee(authors)
        assert result == "John Smith"

    def test_multiple_authors(self):
        authors = ["John Smith", "Jane Doe"]
        result = format_authors_ieee(authors)
        assert "John Smith" in result
        assert "Jane Doe" in result


class TestFormatAuthorsChicago:
    def test_single_author(self):
        authors = ["John Smith"]
        result = format_authors_chicago(authors)
        assert result == "John Smith"

    def test_multiple_authors(self):
        authors = ["John Smith", "Jane Doe"]
        result = format_authors_chicago(authors)
        assert "John Smith" in result
        assert "Jane Doe" in result


class TestGenerateCitation:
    def test_complete_paper(self):
        paper = {
            "title": "Deep Learning Research",
            "authors": ["John Smith", "Jane Doe"],
            "year": 2024,
            "source_url": "https://example.com/paper",
        }
        result = generate_citation(paper)

        assert "apa" in result
        assert "mla" in result
        assert "ieee" in result
        assert "chicago" in result

        assert "John Smith" in result["apa"]
        assert "Deep Learning Research" in result["apa"]
        assert "2024" in result["apa"]

    def test_missing_year(self):
        paper = {
            "title": "Test Paper",
            "authors": ["Author"],
            "year": None,
            "source_url": "https://example.com",
        }
        result = generate_citation(paper)
        assert "Test Paper" in result["apa"]

    def test_missing_title(self):
        paper = {
            "title": "",
            "authors": ["Author"],
            "year": 2024,
            "source_url": "https://example.com",
        }
        result = generate_citation(paper)
        assert "Author" in result["apa"]

    def test_missing_authors(self):
        paper = {
            "title": "Test Paper",
            "authors": [],
            "year": 2024,
            "source_url": "https://example.com",
        }
        result = generate_citation(paper)
        assert "Unknown Author" in result["apa"]

    def test_no_url(self):
        paper = {
            "title": "Test Paper",
            "authors": ["Author"],
            "year": 2024,
            "source_url": "",
        }
        result = generate_citation(paper)
        assert "apa" in result


class TestCitationRun:
    def test_run_single_paper(self):
        papers = [
            {
                "title": "Paper 1",
                "authors": ["Author 1"],
                "year": 2024,
                "source_url": "https://example.com/1",
            }
        ]
        result = run(papers)

        assert len(result) == 1
        assert "citation" in result[0]
        assert "apa" in result[0]["citation"]

    def test_run_multiple_papers(self):
        papers = [
            {
                "title": "Paper 1",
                "authors": ["Author 1"],
                "year": 2024,
                "source_url": "https://example.com/1",
            },
            {
                "title": "Paper 2",
                "authors": ["Author 2"],
                "year": 2023,
                "source_url": "https://example.com/2",
            },
        ]
        result = run(papers)

        assert len(result) == 2
        assert "citation" in result[0]
        assert "citation" in result[1]

    def test_run_empty_list(self):
        result = run([])
        assert result == []

    def test_run_preserves_paper_data(self):
        papers = [
            {
                "title": "Original Title",
                "authors": ["Author"],
                "year": 2024,
                "source_url": "https://example.com",
                "other_field": "preserved",
            }
        ]
        result = run(papers)
        assert result[0]["title"] == "Original Title"
        assert result[0]["other_field"] == "preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
