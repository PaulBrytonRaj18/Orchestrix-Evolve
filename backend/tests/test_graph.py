"""Citation graph: PageRank, clusters, missing key papers, OpenAlex fetching."""

import httpx
import pytest
import respx

from config import get_settings
from services import graph


def test_pagerank_favours_the_cited_paper():
    ranks = graph.pagerank(["a", "b", "c"], [("a", "c"), ("b", "c")])
    assert ranks["c"] > ranks["a"] == pytest.approx(ranks["b"])
    assert sum(ranks.values()) == pytest.approx(1.0)


def test_clusters_split_disconnected_groups():
    groups = graph.clusters(["a", "b", "c", "d", "e"], [("a", "b"), ("c", "d")])
    assert sorted(map(sorted, groups)) == [["a", "b"], ["c", "d"], ["e"]]


class _W:
    def __init__(self, oa, refs):
        self.openalex_id, self.references = oa, refs


class _P:
    def __init__(self, pid, oa, refs):
        self.id, self.title, self.year, self.citation_count = pid, f"Paper {pid}", 2020, 1
        self.work = _W(oa, refs)


def test_build_graph_edges_foundational_and_missing():
    papers = [
        _P("p1", "W1", ["W3", "W9"]),
        _P("p2", "W2", ["W3", "W9"]),
        _P("p3", "W3", []),
        _P("p4", "W4", ["W5"]),
        _P("p5", "W5", []),
    ]
    g = graph.build_graph(papers)
    assert {(e["source"], e["target"]) for e in g["edges"]} == {
        ("p1", "p3"),
        ("p2", "p3"),
        ("p4", "p5"),
    }
    assert g["foundational"][0]["paper_id"] == "p3"
    assert g["missing_key_papers"] == [{"openalex_id": "W9", "cited_by_session_papers": 2}]
    assert len(g["disconnected_clusters"]) == 2  # {p1,p2,p3} and {p4,p5} never cite each other


@respx.mock
def test_graph_endpoint_fetches_references_once(client, fake_sources):
    s = get_settings()
    sid = client.post("/sessions", json={"name": "g", "query": "graph"}).json()["id"]
    papers = client.post(f"/sessions/{sid}/orchestrate").json()["papers"]
    # make_paper(i): even i have DOI 10.1000/test.i, odd i are arXiv 2401.(1000+i)
    p2 = next(p for p in papers if p["external_id"] == "10.1000/test.2")
    p4 = next(p for p in papers if p["external_id"] == "10.1000/test.4")

    def openalex(request):
        flt = request.url.params.get("filter", "")
        if flt.startswith("doi:"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "https://openalex.org/W2",
                            "doi": "https://doi.org/10.1000/test.2",
                            "referenced_works": [
                                "https://openalex.org/W4",
                                "https://openalex.org/W99",
                            ],
                        },
                        {
                            "id": "https://openalex.org/W4",
                            "doi": "https://doi.org/10.1000/test.4",
                            "referenced_works": [],
                        },
                        {
                            "id": "https://openalex.org/W6",
                            "doi": "https://doi.org/10.1000/test.6",
                            "referenced_works": [
                                "https://openalex.org/W4",
                                "https://openalex.org/W99",
                            ],
                        },
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W99",
                        "title": "The missing classic",
                        "publication_year": 2012,
                        "cited_by_count": 5000,
                        "doi": None,
                        "authorships": [],
                    }
                ]
            },
        )

    route = respx.get(s.openalex_url).mock(side_effect=openalex)
    body = client.get(f"/sessions/{sid}/graph").json()
    edges = {(e["source"], e["target"]) for e in body["edges"]}
    assert (p2["id"], p4["id"]) in edges
    assert body["foundational"][0]["paper_id"] == p4["id"]
    assert body["missing_key_papers"][0]["title"] == "The missing classic"
    assert body["missing_key_papers"][0]["cited_by_session_papers"] == 2
    dois_requested = [
        c.request.url.params["filter"]
        for c in route.calls
        if "doi:" in c.request.url.params["filter"]
    ]
    assert "10.48550/arxiv.2401.1001" in dois_requested[0]  # arXiv papers resolved via arXiv DOIs

    calls = route.call_count
    client.get(f"/sessions/{sid}/graph")
    doi_calls_after = [c for c in route.calls[calls:] if "doi:" in c.request.url.params["filter"]]
    assert doi_calls_after == []  # reference lists are stored on the works, not re-fetched


def test_graph_is_private(client, fake_sources):
    sid = client.post("/sessions", json={"name": "g", "query": "graph"}).json()["id"]
    client.current_user["id"] = "user-b"
    try:
        assert client.get(f"/sessions/{sid}/graph").status_code == 404
    finally:
        client.current_user["id"] = "user-a"
