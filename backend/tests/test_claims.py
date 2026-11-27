"""Claim extraction and paper-vs-paper contradiction detection."""

import re
import uuid

import pytest

from agents import claims

A = {
    "id": "a",
    "title": "Dropout study",
    "abstract": "We study regularisation. Our results show that dropout improves BLEU of the "
    "transformer on WMT14 by 1.2 points. Code is released.",
}
B = {
    "id": "b",
    "title": "Revisiting dropout",
    "abstract": "We revisit regularisation. We find that dropout does not improve BLEU of the "
    "transformer on WMT14 at any scale.",
}
C = {
    "id": "c",
    "title": "Poetry",
    "abstract": "We show that medieval troubadours used rhyme schemes widely in songs.",
}


def test_heuristic_extraction_reads_direction_and_keeps_quote():
    [claim] = claims.heuristic_claims(A)
    assert claim["direction"] == "increase" and claim["metric"] == "bleu"
    assert claim["evidence"] in A["abstract"] and claim["generated_by"] == "heuristic"
    assert claims.heuristic_claims(B)[0]["direction"] == "no_effect"


def test_direction_cues_need_whole_words():
    assert claims.claim_direction("Adding dropout improves accuracy.") == "increase"
    assert claims.claim_direction("Accuracy drops sharply without pretraining.") == "decrease"


def test_pairs_only_across_papers_and_only_related():
    extracted = {p["id"]: claims.heuristic_claims(p) for p in (A, B, C)}
    pairs = claims.candidate_pairs(extracted)
    assert pairs and all(a["paper_id"] != b["paper_id"] for a, b, _ in pairs)
    assert {frozenset((a["paper_id"], b["paper_id"])) for a, b, _ in pairs} == {frozenset("ab")}


@pytest.mark.asyncio
async def test_heuristic_pipeline_finds_the_contradiction(monkeypatch):
    class Off:
        enabled = False

    monkeypatch.setattr(claims, "get_llm", lambda: Off())
    monkeypatch.setattr("services.works.stored_claims", lambda papers: {})
    result = await claims.detect_conflicts([A, B, C])
    [conflict] = result["conflicts"]
    assert {conflict["paper_a_id"], conflict["paper_b_id"]} == {"a", "b"}
    assert conflict["evidence_a"] in A["abstract"] + B["abstract"]
    assert conflict["detected_by"] == "heuristic" and conflict["confidence"] <= 0.6
    assert result["stats"]["pairs_checked"] == 1


class FakeLLM:
    enabled = True

    def __init__(self):
        self.calls = []

    async def chat_json(self, system, user, **_):
        self.calls.append(user)
        if '"papers"' in user:  # extraction batch
            idx = [int(n) for n in re.findall(r"^\[(\d+)\] Title:", user, re.M)]
            return {
                "papers": [
                    {
                        "index": i,
                        "claims": [
                            {
                                "text": f"claim {i}",
                                "subject": "dropout",
                                "outcome": "BLEU",
                                "direction": "increase" if i == 1 else "no_effect",
                                "evidence": "this sentence is not in the abstract",
                            }
                        ],
                    }
                    for i in idx
                ]
            }
        idx = [int(n) for n in re.findall(r"^\[(\d+)\] A:", user, re.M)]
        return {
            "pairs": [
                {
                    "index": i,
                    "relation": "contradiction",
                    "confidence": 0.85,
                    "explanation": "Opposite findings on BLEU.",
                }
                for i in idx
            ]
        }


@pytest.mark.asyncio
async def test_llm_pipeline_batches_and_rejects_invented_quotes(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(claims, "get_llm", lambda: fake)
    monkeypatch.setattr("services.works.stored_claims", lambda papers: {})
    result = await claims.detect_conflicts([A, B])
    assert len(fake.calls) == 2  # one extraction batch + one judging batch
    assert all(c["evidence"] is None for cs in result["claims"].values() for c in cs)
    [conflict] = result["conflicts"]
    assert conflict["severity"] == "high" and conflict["detected_by"] == "llm"
    assert conflict["description"] == "Opposite findings on BLEU."


def test_labelled_pairs_regression_for_heuristic_judge():
    """Guard: the offline fallback keeps F1 ≥ 0.8 on the hand-labelled pairs."""
    import json

    from evaluation.claims_eval import DATA, _as_claim, score

    pairs = json.loads(DATA.read_text())["pairs"]
    predicted = [
        claims.heuristic_judgement(_as_claim(p["a"]), _as_claim(p["b"]), 0.9)["relation"]
        == "contradiction"
        for p in pairs
    ]
    m = score(predicted, [p["label"] == "contradiction" for p in pairs])
    assert m["f1"] >= 0.8 and m["precision"] >= 0.85


def test_orchestrated_conflicts_are_stored_with_evidence(client, monkeypatch):
    from agents import discovery

    async def fetch(query, page=0, limit=None, since=None, sources=discovery.SOURCES):
        papers = []
        for p in (A, B, C):
            papers.append(
                {
                    **{k: v for k, v in p.items() if k != "id"},
                    "authors": ["X Y"],
                    "year": 2024,
                    "source": "arxiv",
                    "external_id": f"arxiv:{uuid.uuid4().hex[:8]}",
                    "citation_count": 1,
                }
            )
        return papers, {}

    monkeypatch.setattr(discovery, "fetch_all_sources", fetch)
    sid = client.post("/sessions", json={"name": "s", "query": "dropout bleu"}).json()["id"]
    body = client.post(f"/sessions/{sid}/orchestrate").json()
    [conflict] = body["conflicts"]
    ids = {p["id"] for p in body["papers"]}
    assert {conflict["paper_a_id"], conflict["paper_b_id"]} <= ids
    assert conflict["evidence_a"] and conflict["confidence"] > 0
    trace = {t["agent"]: t for t in body["trace"]}
    assert "1 contradicting claim pairs" in trace["Conflict Detection"]["result"]
    # Claims were stored on the shared works and are reused by re-detection.
    redetect = client.post(f"/sessions/{sid}/detect-conflicts").json()
    assert len(redetect["conflicts"]) == 1 and redetect["conflicts"][0]["evidence_b"]
