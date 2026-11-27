"""Embedding-based ranking, vector reuse, related papers, and the evaluation harness."""

import uuid

import pytest

from agents import discovery
from tests.conftest import USER_B, make_paper

ON_TOPIC = {
    "title": "Graph neural networks for drug discovery",
    "abstract": "graph neural molecules drug",
}
OFF_TOPIC = {"title": "Medieval poetry and rhyme", "abstract": "verses rhymes troubadours"}


def test_dense_ranking_sets_scores_and_vectors(fake_embedder):
    papers = [
        dict(OFF_TOPIC, citation_count=5, year=2020),
        dict(ON_TOPIC, citation_count=5, year=2020),
    ]
    ranked = discovery.rank_papers("graph neural drug discovery", papers, 10)
    assert ranked[0]["title"].startswith("Graph")
    assert all(p["embedding_model"] == "fake/bow-64" and len(p["embedding"]) == 64 for p in ranked)
    assert ranked[0]["semantic_score"] == 1.0  # min-max scaled within the pool


def test_without_embedder_tfidf_is_used(monkeypatch):
    from services import embeddings

    monkeypatch.setattr(embeddings, "get_embedder", lambda: None)
    ranked = discovery.rank_papers("graph neural drug", [dict(ON_TOPIC), dict(OFF_TOPIC)], 10)
    assert ranked[0]["title"].startswith("Graph") and "embedding" not in ranked[0]


def test_failed_model_falls_back(monkeypatch):
    from services import embeddings

    class Broken:
        available = True
        model_name = "x"

        def embed_documents(self, texts):
            raise RuntimeError("onnx exploded")

    monkeypatch.setattr(embeddings, "get_embedder", lambda: Broken())
    ranked = discovery.rank_papers("graph neural drug", [dict(ON_TOPIC), dict(OFF_TOPIC)], 10)
    assert ranked[0]["title"].startswith("Graph")


def test_stored_vectors_are_reused(fake_embedder, monkeypatch):
    from database import get_db_context
    from models import Session as SessionModel
    from services import persistence

    paper = make_paper(7001)
    first = discovery.rank_papers("graph neural networks", [dict(paper)], 5)[0]
    sid = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=sid, name="s", query="q", user_id="u"))
        db.flush()
        persistence.save_papers(db, sid, [dict(first, id=str(uuid.uuid4()))])

    seen = []
    real = fake_embedder.embed_documents
    monkeypatch.setattr(
        fake_embedder, "embed_documents", lambda texts: seen.extend(texts) or real(texts)
    )
    again = discovery.rank_papers("graph neural networks", [dict(paper), make_paper(7002)], 5)
    assert len(seen) == 1  # only the new paper was embedded; 7001's vector came from the DB
    stored = next(p for p in again if p["external_id"] == paper["external_id"])
    assert stored["embedding"] == pytest.approx(first["embedding"], abs=1e-6)


class TestRelatedPapers:
    def _search(self, client, fake_sources):
        sid = client.post("/sessions", json={"name": "s", "query": "graph neural networks"}).json()[
            "id"
        ]
        papers = client.post(f"/sessions/{sid}/orchestrate").json()["papers"]
        return sid, papers

    def test_related_returns_nearest_works(self, client, fake_sources, fake_embedder):
        sid, papers = self._search(client, fake_sources)
        r = client.get(f"/papers/{papers[0]['id']}/related", params={"limit": 5})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["available"] and body["model"] == "fake/bow-64"
        sims = [x["similarity"] for x in body["related"]]
        assert len(sims) == 5 and sims == sorted(sims, reverse=True)
        assert all(x["work_id"] != papers[0]["id"] for x in body["related"])
        assert any(x["in_session"] for x in body["related"])

    def test_related_is_private(self, client, fake_sources, fake_embedder):
        _, papers = self._search(client, fake_sources)
        client.current_user["id"] = USER_B
        try:
            assert client.get(f"/papers/{papers[0]['id']}/related").status_code == 404
        finally:
            client.current_user["id"] = "user-a"

    def test_related_without_model_reports_unavailable(self, client, fake_sources):
        _, papers = self._search(client, fake_sources)
        body = client.get(f"/papers/{papers[0]['id']}/related").json()
        assert body == {
            "paper_id": papers[0]["id"],
            "available": False,
            "model": None,
            "related": [],
        }


class TestEvaluationHarness:
    def test_metrics(self):
        from evaluation.run import mrr, ndcg_at_k, recall_at_k

        assert ndcg_at_k([True, False, False]) == 1.0
        assert ndcg_at_k([False, True]) == pytest.approx(1 / 1.5849625, rel=1e-6)
        assert recall_at_k([False] * 25 + [True], k=20) == 0.0
        assert mrr([False, False, True]) == pytest.approx(1 / 3)

    def test_frozen_dataset_and_baselines(self):
        """Regression guard: the dataset loads and TF-IDF ranking beats random order."""
        import numpy as np

        from agents.discovery import RankWeights
        from evaluation.run import evaluate, features_for, load_queries, rank_with

        queries = load_queries()
        assert len(queries) >= 20
        assert all(any(p["relevant"] for p in q["pool"]) for q in queries)
        tfidf = evaluate(rank_with(queries, features_for(queries, None), RankWeights()))
        rng = np.random.default_rng(0)
        rand = evaluate(
            [list(rng.permutation([p["relevant"] for p in q["pool"]])) for q in queries]
        )
        assert tfidf["ndcg@20"] > rand["ndcg@20"] + 0.05


@pytest.mark.asyncio
class TestLlmRerank:
    async def _run(self, monkeypatch, answer):
        import llm as llm_module

        class Fake:
            enabled = True

            async def chat_json(self, system, user, **_):
                return answer

        monkeypatch.setattr(llm_module, "get_llm", lambda: Fake())
        papers = [{"title": f"p{i}", "relevance_score": s} for i, s in enumerate((0.9, 0.8, 0.7))]
        return await discovery.llm_rerank("q", papers, top_k=3)

    async def test_llm_scores_are_blended(self, monkeypatch):
        out = await self._run(
            monkeypatch,
            {
                "scores": [
                    {"index": 1, "relevance": 0},
                    {"index": 2, "relevance": 10},
                    {"index": 3, "relevance": 5},
                ]
            },
        )
        assert [p["title"] for p in out] == ["p1", "p2", "p0"]
        assert out[0]["relevance_score"] == pytest.approx(0.9)

    async def test_garbage_answer_keeps_order(self, monkeypatch):
        out = await self._run(monkeypatch, {"nope": 1})
        assert [p["title"] for p in out] == ["p0", "p1", "p2"]
