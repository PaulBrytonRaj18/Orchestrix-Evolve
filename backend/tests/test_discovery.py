"""Discovery agent: parsing of each source, ranking, dedup and performance."""

import time

import httpx
import pytest
import respx

from agents import discovery
from config import get_settings

S = get_settings()

ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-03T00:00:00Z</published>
    <title>Graph Neural
      Networks for Drug Discovery</title>
    <summary>We study GNNs for molecules.</summary>
    <author><name>Ada Lovelace</name></author>
    <arxiv:doi>10.1000/XYZ.1</arxiv:doi>
  </entry>
</feed>"""


class TestParsing:
    def test_decode_inverted_index(self):
        idx = {"Graph": [0], "networks": [2], "neural": [1], "graph": [3]}
        assert discovery.decode_inverted_index(idx) == "Graph neural networks graph"
        assert discovery.decode_inverted_index(None) == ""

    def test_identifier_normalisation(self):
        assert discovery.normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
        assert discovery.normalize_arxiv_id("http://arxiv.org/abs/2401.01234v3") == "2401.01234"

    def test_arxiv_query_uses_and_terms_and_date(self):
        from datetime import date

        q = discovery._arxiv_search_query("graph neural networks", date(2025, 1, 2))
        assert q == (
            "(all:graph AND all:neural AND all:networks) "
            "AND submittedDate:[202501020000 TO 209912312359]"
        )


@pytest.mark.asyncio
class TestSources:
    @respx.mock
    async def test_openalex_uses_valid_fields_and_decodes_abstract(self):
        route = respx.get(S.openalex_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "https://openalex.org/W1",
                            "title": "A paper",
                            "authorships": [{"author": {"display_name": "Ann Smith"}}],
                            "publication_year": 2023,
                            "doi": "https://doi.org/10.1/ABC",
                            "cited_by_count": 7,
                            "primary_location": {"source": {"display_name": "NeurIPS"}},
                            "abstract_inverted_index": {"Hello": [0], "world": [1]},
                        }
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as c:
            papers = await discovery.query_openalex(c, "q", 0, 5)
        select = route.calls.last.request.url.params["select"]
        assert "host_venue" not in select and "primary_location" in select
        p = papers[0]
        assert p["abstract"] == "Hello world"
        assert p["venue"] == "NeurIPS"
        assert p["external_id"] == "10.1/abc"

    @respx.mock
    async def test_arxiv_parsing(self):
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        async with httpx.AsyncClient() as c:
            [p] = await discovery.query_arxiv(c, "gnn", 0, 5)
        assert p["title"] == "Graph Neural Networks for Drug Discovery"
        assert p["arxiv_id"] == "2401.01234" and p["doi"] == "10.1000/xyz.1"
        assert p["year"] == 2024

    @respx.mock
    async def test_semantic_scholar_retries_429_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        respx.get(S.semantic_scholar_url).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "1"}),
                httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "title": "T",
                                "authors": [{"name": "A B"}],
                                "year": 2020,
                                "externalIds": {"ArXiv": "2001.00001"},
                                "citationCount": 3,
                            }
                        ]
                    },
                ),
            ]
        )
        async with httpx.AsyncClient() as c:
            papers = await discovery.query_semantic_scholar(c, "q", 0, 5)
        assert papers[0]["external_id"] == "arxiv:2001.00001"

    @respx.mock
    async def test_failed_source_degrades_gracefully(self, monkeypatch):
        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(429))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(400, json={}))
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        papers, stats = await discovery.fetch_all_sources("gnn")
        assert stats == {"semantic_scholar": 0, "arxiv": 1, "openalex": 0}
        assert len(papers) == 1


async def _no_sleep(_):
    return None


class TestRanking:
    def test_dedup_merges_metadata_across_sources(self):
        a = {
            "title": "Deep Nets",
            "doi": "10.1/x",
            "citation_count": 5,
            "abstract": None,
            "source": "s2",
        }
        b = {
            "title": "Deep nets.",
            "doi": "10.1/x",
            "citation_count": 50,
            "abstract": "Text",
            "source": "oa",
        }
        [merged] = discovery.deduplicate_papers([a, b])
        assert merged["citation_count"] == 50 and merged["abstract"] == "Text"

    def test_dedup_matches_arxiv_versions(self):
        a = {"title": "Alpha", "arxiv_id": "2401.1", "citation_count": 0}
        b = {"title": "Alpha: extended", "arxiv_id": "2401.1", "citation_count": 1}
        assert len(discovery.deduplicate_papers([a, b])) == 1

    def test_relevance_prefers_on_topic_papers(self):
        papers = [
            {
                "title": "Graph neural networks for drug discovery",
                "abstract": "GNN molecules",
                "year": 2023,
                "citation_count": 5,
            },
            {
                "title": "Medieval poetry",
                "abstract": "Rhymes and verses",
                "year": 2023,
                "citation_count": 5,
            },
        ]
        ranked = discovery.rank_papers("graph neural networks drug discovery", papers, 10)
        assert ranked[0]["title"].startswith("Graph")
        assert all(0.0 <= p["relevance_score"] <= 1.0 for p in ranked)

    def test_similarity_is_fast(self):
        """Regression: the old TF-IDF took ~70 s for 60 papers (cubic)."""
        words = [f"w{i}" for i in range(2000)]
        papers = [
            {"title": " ".join(words[i : i + 12]), "abstract": " ".join(words[i * 3 : i * 3 + 250])}
            for i in range(300)
        ]
        started = time.perf_counter()
        discovery.compute_semantic_similarity("w1 w2 w3", papers)
        assert time.perf_counter() - started < 1.0
