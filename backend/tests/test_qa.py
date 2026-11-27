"""Question answering over a session's papers."""

import pytest

from services import fulltext, qa

LONG_TEXT = " ".join(
    f"Section {i}. Graph neural networks predict molecular toxicity with message passing. "
    f"The model reaches high accuracy on Tox21 in experiment {i}. "
    for i in range(80)
)


def test_clean_text_cuts_references_and_dehyphenates():
    raw = "Intro text " * 300 + "exam-\nple word.\n\nReferences\n[1] Someone. A paper."
    cleaned = fulltext.clean_text(raw)
    assert "example word" in cleaned and "Someone" not in cleaned


def test_chunks_are_sentence_aligned_with_overlap():
    chunks = fulltext.chunk_text(LONG_TEXT, size=400, overlap=80)
    assert len(chunks) > 10 and all(len(c) <= 480 for c in chunks)
    assert all(c[0].isupper() or c[0].isdigit() for c in chunks)


@pytest.fixture
def fake_fulltext(monkeypatch):
    calls = []

    async def fetch(client, arxiv_id):
        calls.append(arxiv_id)
        return LONG_TEXT

    monkeypatch.setattr(fulltext, "fetch_arxiv_text", fetch)
    return calls


def _session(client):
    sid = client.post("/sessions", json={"name": "q", "query": "graph neural"}).json()["id"]
    client.post(f"/sessions/{sid}/orchestrate")
    return sid


def test_extractive_answer_with_citations(client, fake_sources, fake_embedder, fake_fulltext):
    sid = _session(client)
    r = client.post(
        f"/sessions/{sid}/ask", json={"question": "How accurate is toxicity prediction?"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "extractive" and "[1]" in body["answer"]
    cov = body["coverage"]  # the 12 papers fit under QA_MAX_PAPERS; odd ones are arXiv
    assert cov == {"papers": 12, "fulltext": 6, "abstract_only": 6}
    assert len(body["passages"]) == 8 and body["passages"][0]["cited"]
    per_paper = {}
    for p in body["passages"]:
        per_paper[p["paper_id"]] = per_paper.get(p["paper_id"], 0) + 1
    assert max(per_paper.values()) <= 3


def test_passages_are_ingested_once(client, fake_sources, fake_embedder, fake_fulltext):
    sid = _session(client)
    client.post(f"/sessions/{sid}/ask", json={"question": "first question here"})
    first = len(fake_fulltext)
    client.post(f"/sessions/{sid}/ask", json={"question": "second question here"})
    assert len(fake_fulltext) == first  # nothing re-downloaded


def test_llm_answer_drops_invented_citations(
    client, fake_sources, fake_embedder, fake_fulltext, monkeypatch
):
    class Fake:
        enabled = True

        async def chat_json(self, system, user, **_):
            assert "[1]" in user and "Passages:" in user
            return {"answer": "Accuracy is high on Tox21 [1], see also [99]."}

    monkeypatch.setattr(qa, "get_llm", lambda: Fake())
    sid = _session(client)
    body = client.post(f"/sessions/{sid}/ask", json={"question": "accuracy on Tox21?"}).json()
    assert body["mode"] == "llm"
    assert body["answer"] == "Accuracy is high on Tox21 [1], see also."
    assert [p["n"] for p in body["passages"] if p["cited"]] == [1]


def test_ask_without_model_is_503(client, fake_sources):
    sid = _session(client)
    assert (
        client.post(f"/sessions/{sid}/ask", json={"question": "anything at all"}).status_code == 503
    )


def test_ask_is_private(client, fake_sources, fake_embedder, fake_fulltext):
    sid = _session(client)
    client.current_user["id"] = "user-b"
    try:
        assert (
            client.post(f"/sessions/{sid}/ask", json={"question": "who are you"}).status_code == 404
        )
    finally:
        client.current_user["id"] = "user-a"


@pytest.mark.asyncio
async def test_resolve_sources_prefers_arxiv_copy():
    import httpx
    import respx

    from config import get_settings

    with respx.mock:
        respx.get(get_settings().openalex_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "doi": "https://doi.org/10.1/a",
                            "best_oa_location": {"pdf_url": "https://pub.example/a.pdf"},
                            "locations": [
                                {
                                    "landing_page_url": "http://arxiv.org/abs/2012.05716v2",
                                    "pdf_url": None,
                                }
                            ],
                        },
                        {
                            "doi": "https://doi.org/10.1/b",
                            "best_oa_location": {"pdf_url": "https://pub.example/b.pdf"},
                            "locations": [
                                {"landing_page_url": "https://pub.example/b", "pdf_url": None}
                            ],
                        },
                        {
                            "doi": "https://doi.org/10.1/c",
                            "best_oa_location": None,
                            "locations": [],
                        },
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as client:
            found = await fulltext.resolve_sources(client, ["10.1/a", "10.1/b", "10.1/c"])
    assert found == {
        "10.1/a": ("arxiv", "2012.05716"),
        "10.1/b": ("url", "https://pub.example/b.pdf"),
    }


def test_qa_indexes_only_the_most_relevant_papers(
    client, fake_sources, fake_embedder, fake_fulltext, monkeypatch
):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "qa_max_papers", 4)
    sid = _session(client)
    body = client.post(f"/sessions/{sid}/ask", json={"question": "toxicity accuracy"}).json()
    assert body["coverage"]["papers"] == 4
    top4 = {p["id"] for p in client.get(f"/sessions/{sid}").json()["papers"][:4]}
    assert {p["paper_id"] for p in body["passages"]} <= top4
