"""Orchestrator: planning, dependency resolution and failure isolation."""

import asyncio

import pytest

import orchestrator
from agents import summarizer
from llm import _RateLimiter, get_llm


class TestResolveWorkflow:
    def test_adds_missing_dependencies_in_order(self):
        assert orchestrator.resolve_workflow(["conflict_detector"]) == [
            "discovery",
            "conflict_detector",
        ]
        assert orchestrator.resolve_workflow(["roadmap", "analysis"]) == [
            "discovery",
            "analysis",
            "roadmap",
        ]

    def test_ignores_unknown_agents(self):
        assert orchestrator.resolve_workflow(["citation", "rm -rf"]) == ["discovery", "citation"]

    def test_empty_plan_falls_back_to_full(self):
        assert orchestrator.resolve_workflow([]) == orchestrator.FULL_WORKFLOW


@pytest.mark.asyncio
async def test_agent_failure_is_isolated(fake_sources, monkeypatch):
    async def boom(_papers):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(summarizer, "summarize_all_papers", boom)
    result = await orchestrator.orchestrate("graph neural networks", "s-iso")
    status = {t["agent"]: t["status"] for t in result["trace"]}
    assert status["Summarizer"] == "error"
    assert status["Citation"] == "done" and status["Analysis"] == "done"
    # Claim-based conflict detection no longer depends on the summarizer.
    assert status["Conflict Detection"] == "done"
    assert status["Roadmap"] == "done"
    assert len(result["papers"]) == 12
    assert all(
        t.get("duration_ms") is not None for t in result["trace"] if t["status"] != "skipped"
    )


@pytest.mark.asyncio
async def test_stage_two_runs_concurrently(fake_sources, monkeypatch):
    async def slow_summaries(papers):
        await asyncio.sleep(0.3)
        return []

    from agents import analysis

    real_analysis = analysis.run

    async def slow_analysis(papers):
        await asyncio.sleep(0.3)
        return await real_analysis(papers)

    monkeypatch.setattr(summarizer, "summarize_all_papers", slow_summaries)
    monkeypatch.setattr(analysis, "run", slow_analysis)
    loop = asyncio.get_running_loop()
    started = loop.time()
    await orchestrator.orchestrate("q", "s-conc")
    assert loop.time() - started < 0.55  # ~0.3 s, not 0.6 s


@pytest.mark.asyncio
async def test_without_llm_summaries_are_extractive(fake_sources):
    assert not get_llm().enabled
    result = await orchestrator.orchestrate("gnn", "s-ext")
    assert result["summaries"]
    assert all(s["generated_by"] == "extractive" for s in result["summaries"])
    assert all(s["paper_id"] for s in result["summaries"])


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_budget(monkeypatch):
    limiter = _RateLimiter(rpm=2)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        limiter._calls.clear()  # pretend the window passed

    monkeypatch.setattr("llm.asyncio.sleep", fake_sleep)
    for _ in range(3):
        await limiter.acquire()
    assert len(slept) == 1 and slept[0] > 0
