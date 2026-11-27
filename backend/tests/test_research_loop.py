"""Deep research job: rounds, stopping rule, query choice."""

import zlib

import pytest

from tests.conftest import make_paper
from tests.test_jobs import read_events


@pytest.fixture
def per_query_sources(monkeypatch):
    """The main query yields papers 1-12; each follow-up yields 4 papers of its own;
    once ``exhausted`` is set, follow-ups only return papers already found."""
    from agents import discovery

    state = {"queries": [], "exhausted_after": 2}

    async def fetch(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
        state["queries"].append(query)
        if len(state["queries"]) == 1:
            return [make_paper(i) for i in range(1, 13)], {}
        if len(state["queries"]) > 1 + state["exhausted_after"]:
            return [make_paper(i) for i in range(1, 5)], {}
        base = 2000 + zlib.crc32(query.encode()) % 5000
        return [make_paper(base + i) for i in range(4)], {}

    monkeypatch.setattr(discovery, "fetch_all_sources", fetch)
    return state


def _run_deep(client):
    sid = client.post("/sessions", json={"name": "d", "query": "graph neural networks"}).json()[
        "id"
    ]
    r = client.post(f"/sessions/{sid}/jobs", json={"kind": "deep"})
    assert r.status_code == 202, r.text
    return sid, read_events(client, r.json()["id"], timeout=30)


def test_deep_research_rounds_and_stopping(client, per_query_sources):
    sid, events = _run_deep(client)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "done" and "papers" in kinds
    done = events[-1][1]
    rounds = [t for t in done["trace"] if t["agent"].startswith("Round")]
    # Round 1: 12 papers · Round 2: two follow-ups add 8 (+67%) · Round 3: nothing new → stop
    assert [r["agent"] for r in rounds] == ["Round 1", "Round 2", "Round 3"]
    assert "+8 new papers" in rounds[1]["result"] and "roadmap chose" in rounds[1]["result"]
    final = done["trace"][-1]
    assert final["agent"] == "Research loop" and "added under 10%" in final["result"]
    assert len(done["papers"]) == 20
    assert done["roadmap"]  # round 1's roadmap is kept
    live_labels = {t["agent"] for e, d in events if e == "trace" for t in d}
    assert any(label.startswith("Round 2 · ") for label in live_labels)  # rounds stream live
    assert len(client.get(f"/sessions/{sid}").json()["papers"]) == 20


def test_round_limit(client, per_query_sources, monkeypatch):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "deep_max_rounds", 1)
    _, events = _run_deep(client)
    trace = events[-1][1]["trace"]
    assert [t["agent"] for t in trace] == ["Round 1", "Research loop"]
    assert "round limit" in trace[-1]["result"]


@pytest.mark.asyncio
async def test_llm_chooses_new_queries(monkeypatch):
    from services import research_loop

    class Fake:
        enabled = True

        async def chat_json(self, system, user, **_):
            assert "Already searched" in user
            return {"queries": ["gnn toxicity benchmarks", "graph neural networks", "new one"]}

    monkeypatch.setattr(research_loop, "get_llm", lambda: Fake())
    queries, chooser = await research_loop.next_queries(
        "graph neural networks", {"papers": [], "roadmap": None}, {"graph neural networks"}, 2
    )
    assert chooser == "llm" and queries == ["gnn toxicity benchmarks", "new one"]
