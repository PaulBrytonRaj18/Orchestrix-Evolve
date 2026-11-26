"""Contract checks against the real academic APIs.

Skipped by default. Run with ``RUN_LIVE=1 pytest -m live`` (needs outbound access to
api.semanticscholar.org, export.arxiv.org and api.openalex.org). These catch upstream
API changes such as OpenAlex removing ``host_venue``, which silently zeroed a source.
"""

import os

import httpx
import pytest

from agents import discovery

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE"), reason="set RUN_LIVE=1 to hit real APIs"),
]

QUERY = "graph neural networks drug discovery"


@pytest.mark.asyncio
async def test_arxiv_live():
    async with httpx.AsyncClient(timeout=20) as c:
        papers = await discovery.query_arxiv(c, QUERY, 0, 5)
    assert papers and all(p["arxiv_id"] for p in papers)


@pytest.mark.asyncio
async def test_openalex_live():
    async with httpx.AsyncClient(timeout=20) as c:
        papers = await discovery.query_openalex(c, QUERY, 0, 10)
    assert papers, "OpenAlex returned nothing — check the select= fields"
    assert sum(1 for p in papers if p["abstract"]) >= 3


@pytest.mark.asyncio
async def test_semantic_scholar_live():
    async with httpx.AsyncClient(timeout=20) as c:
        papers = await discovery.query_semantic_scholar(c, QUERY, 0, 5)
    if not papers:
        pytest.skip("Semantic Scholar rate-limited (set SEMANTIC_SCHOLAR_API_KEY)")
    assert papers[0]["title"]


@pytest.mark.asyncio
async def test_discovery_end_to_end_is_fast():
    import time

    started = time.perf_counter()
    papers = await discovery.run(QUERY)
    assert papers
    assert time.perf_counter() - started < 30
