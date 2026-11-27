"""Summarizer: batched LLM requests, per-item fallback, reuse of stored summaries."""

import json
import re
import uuid

import pytest

from agents import summarizer
from tests.conftest import make_paper


class FakeLLM:
    """Records prompts; answers batch prompts with one summary per [n], minus ``drop``."""

    enabled = True

    def __init__(self, drop: tuple[int, ...] = ()):
        self.calls: list[str] = []
        self.drop = drop

    async def chat_json(self, system, user, **_):
        self.calls.append(user)
        indices = [int(n) for n in re.findall(r"^\[(\d+)\] Title:", user, re.M)]
        item = {
            "abstract_compression": "LLM claim",
            "key_points": ["k1", "k2"],
            "methodology": "LLM method",
            "limitations": "LLM limits",
            "confidence_score": 0.9,
        }
        if indices:  # batch request
            return {"summaries": [{"index": i, **item} for i in indices if i not in self.drop]}
        return dict(item)  # single-paper request


@pytest.fixture
def papers():
    return [dict(make_paper(1000 + i), id=str(uuid.uuid4())) for i in range(6)]


@pytest.fixture
def fake_llm(monkeypatch):
    def install(**kw):
        llm = FakeLLM(**kw)
        monkeypatch.setattr(summarizer, "get_llm", lambda: llm)
        return llm

    return install


@pytest.mark.asyncio
async def test_papers_are_batched_into_few_requests(papers, fake_llm):
    llm = fake_llm()
    result = await summarizer.summarize_all_papers(papers)
    assert len(llm.calls) == 2  # 6 papers at 4 per request
    assert [r["paper_id"] for r in result] == [p["id"] for p in papers]  # order kept
    assert all(r["generated_by"] == "llm" and r["methodology"] == "LLM method" for r in result)
    assert result[0]["key_contributions"] == "• k1\n• k2"


@pytest.mark.asyncio
async def test_item_missing_from_batch_falls_back_to_single_request(papers, fake_llm):
    llm = fake_llm(drop=(2,))
    result = await summarizer.summarize_all_papers(papers[:4])
    assert len(llm.calls) == 2  # one batch + one retry for the dropped paper
    assert all(r["generated_by"] == "llm" for r in result)
    assert "[1] Title:" not in llm.calls[1]  # the retry is a single-paper prompt


@pytest.mark.asyncio
async def test_without_llm_summaries_are_extractive(papers, monkeypatch):
    class Off:
        enabled = False

    monkeypatch.setattr(summarizer, "get_llm", lambda: Off())
    result = await summarizer.summarize_all_papers(papers[:2])
    assert {r["generated_by"] for r in result} == {"extractive"}


@pytest.mark.asyncio
async def test_stored_summaries_are_reused_without_llm_calls(papers, fake_llm):
    from database import get_db_context
    from models import Session as SessionModel
    from services import persistence

    sid = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=sid, name="s", query="q", user_id="u"))
        db.flush()
        id_map = persistence.save_papers(db, sid, papers[:2])
        persistence.save_summaries(
            db,
            [
                {
                    "paper_id": papers[0]["id"],
                    "abstract_compression": "stored claim",
                    "methodology": "stored",
                    "generated_by": "llm",
                }
            ],
            id_map,
        )

    llm = fake_llm()
    again = [dict(p, id=str(uuid.uuid4())) for p in papers[:2]]  # same works, new session
    result = await summarizer.summarize_all_papers(again)
    assert result[0]["reused"] is True and result[0]["abstract_compression"] == "stored claim"
    assert result[0]["paper_id"] == again[0]["id"]
    assert len(llm.calls) == 1 and json.dumps(again[0]["title"])[1:-1] not in llm.calls[0]


def test_llm_summary_is_not_replaced_by_extractive(papers):
    from database import get_db_context
    from models import Paper, Summary
    from models import Session as SessionModel
    from services import persistence

    sid = str(uuid.uuid4())
    with get_db_context() as db:
        db.add(SessionModel(id=sid, name="s", query="q", user_id="u"))
        db.flush()
        id_map = persistence.save_papers(db, sid, papers[:1])
        pid = papers[0]["id"]
        persistence.save_summaries(
            db, [{"paper_id": pid, "abstract_compression": "good", "generated_by": "llm"}], id_map
        )
        persistence.save_summaries(
            db,
            [{"paper_id": pid, "abstract_compression": "weak", "generated_by": "extractive"}],
            id_map,
        )
        work_id = db.get(Paper, id_map[pid]).work_id
    with get_db_context() as db:
        from sqlalchemy import select

        assert (
            db.scalar(select(Summary.abstract_compression).where(Summary.work_id == work_id))
            == "good"
        )
