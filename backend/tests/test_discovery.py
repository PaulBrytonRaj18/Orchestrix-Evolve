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
    async def test_semantic_scholar_sends_api_key_when_configured(self, monkeypatch):
        from config import get_settings

        monkeypatch.setattr(get_settings(), "semantic_scholar_api_key", "k-123")
        route = respx.get(S.semantic_scholar_url).mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        async with httpx.AsyncClient() as c:
            assert await discovery.query_semantic_scholar(c, "q", 0, 5) == []
        assert route.calls.last.request.headers["x-api-key"] == "k-123"

    @respx.mock
    async def test_failed_source_degrades_gracefully(self, monkeypatch):
        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(429))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(400, json={}))
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        papers, stats = await discovery.fetch_all_sources("gnn")
        assert {k: v["status"] for k, v in stats.items()} == {
            "semantic_scholar": "error",
            "arxiv": "ok",
            "openalex": "error",
        }
        assert stats["arxiv"]["count"] == 1 and len(papers) == 1

    @respx.mock
    async def test_slow_source_is_cut_at_the_deadline(self, monkeypatch):
        import asyncio

        from config import get_settings

        monkeypatch.setattr(get_settings(), "discovery_deadline", 0.3)

        async def slow(request):
            await asyncio.sleep(5)
            return httpx.Response(200, json={"data": []})

        respx.get(S.semantic_scholar_url).mock(side_effect=slow)
        respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        loop = asyncio.get_running_loop()
        started = loop.time()
        papers, stats = await discovery.fetch_all_sources("gnn")
        assert loop.time() - started < 1.5
        assert stats["semantic_scholar"]["status"] == "timeout"
        assert stats["openalex"] == {"status": "ok", "count": 0, "ms": stats["openalex"]["ms"]}
        assert len(papers) == 1

    @respx.mock
    async def test_successful_responses_are_cached_failures_are_not(self, monkeypatch):
        from services.cache import source_cache

        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        s2 = respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(429))
        oa = respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        ax = respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))

        await discovery.fetch_all_sources("Graph  NETWORKS")
        first_s2_calls = s2.call_count
        papers, stats = await discovery.fetch_all_sources("graph networks")  # same, normalised
        assert stats["arxiv"]["status"] == "cached" and stats["openalex"]["status"] == "cached"
        # The failure was not cached; the source is now cooling down instead of retried.
        assert stats["semantic_scholar"]["status"] == "skipped"
        assert ax.call_count == 1 and oa.call_count == 1 and s2.call_count == first_s2_calls
        key = source_cache.make_key("semantic_scholar", "graph networks", 0, 50, None)
        assert await source_cache.get(key) is None
        # Cached copies are independent: mutating a result does not poison the cache.
        papers[0]["title"] = "mutated"
        again, _ = await discovery.fetch_all_sources("graph networks")
        assert again[0]["title"] != "mutated"
        assert source_cache.hits >= 4

    @respx.mock
    async def test_cache_is_shared_through_the_database(self):
        from services.cache import source_cache

        respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        ax = respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        await discovery.fetch_all_sources("gnn")
        source_cache.clear_memory()  # simulate another process: only the table remains
        _, stats = await discovery.fetch_all_sources("gnn")
        assert stats["arxiv"]["status"] == "cached" and ax.call_count == 1

    @respx.mock
    async def test_since_queries_have_their_own_cache_entries(self):
        from datetime import date

        respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        ax = respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        await discovery.fetch_all_sources("gnn")
        await discovery.fetch_all_sources("gnn", since=date(2026, 1, 1))
        assert ax.call_count == 2


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


@pytest.mark.asyncio
class TestCooldown:
    @respx.mock
    async def test_failed_source_is_skipped_until_cooldown_ends(self, monkeypatch):
        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        s2 = respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(429))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))

        _, first = await discovery.fetch_all_sources("q1")
        calls_after_failure = s2.call_count
        _, second = await discovery.fetch_all_sources("q2")  # different query: no cache help
        assert first["semantic_scholar"]["status"] == "error"
        assert second["semantic_scholar"]["status"] == "skipped"
        assert s2.call_count == calls_after_failure  # no network call while cooling down

        # Cooldown over → the source is tried again, and success clears the state.
        discovery._cooldown_until["semantic_scholar"] = 0.0
        s2.mock(return_value=httpx.Response(200, json={"data": []}))
        _, third = await discovery.fetch_all_sources("q3")
        assert third["semantic_scholar"]["status"] == "ok"
        assert "semantic_scholar" not in discovery._cooldown_until

    @respx.mock
    async def test_cooldown_can_be_disabled(self, monkeypatch):
        monkeypatch.setattr(discovery.asyncio, "sleep", _no_sleep)
        monkeypatch.setattr(S, "source_failure_cooldown_seconds", 0)
        respx.get(S.semantic_scholar_url).mock(return_value=httpx.Response(429))
        respx.get(S.openalex_url).mock(return_value=httpx.Response(200, json={"results": []}))
        respx.get(S.arxiv_url).mock(return_value=httpx.Response(200, text=ARXIV_FEED))
        await discovery.fetch_all_sources("q1")
        _, again = await discovery.fetch_all_sources("q2")
        assert again["semantic_scholar"]["status"] == "error"
