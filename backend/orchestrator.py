"""Multi-agent orchestration.

The agents form a small dependency graph::

    discovery ──┬── analysis ────┐
                ├── citation      ├── conflict_detector ── roadmap
                └── summarizer ──┘

Independent agents in the same stage run concurrently; every agent is isolated, so
one failing (e.g. the LLM being down) is recorded in the trace and the rest of the
graph still completes. A plan can come from a static policy (default: the full
graph, deterministic and free) or from the LLM Manager agent, whose output is
validated against the known agents and dependency-completed before it runs.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
import weakref
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from agents import analysis, citation, conflict_detector, discovery, roadmap, summarizer
from config import get_settings
from llm import get_llm

logger = logging.getLogger(__name__)

AGENT_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "discovery": (),
    "analysis": ("discovery",),
    "citation": ("discovery",),
    "summarizer": ("discovery",),
    "conflict_detector": ("analysis", "summarizer"),
    "roadmap": ("discovery",),
}
FULL_WORKFLOW = list(AGENT_DEPENDENCIES)
MIN_PAPERS_FOR_ANALYSIS = 3

_session_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _session_lock(session_id: str) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


def resolve_workflow(requested: list[str]) -> list[str]:
    """Keep known agents, add missing dependencies, return in topological order."""
    wanted: set[str] = set()

    def add(agent: str) -> None:
        if agent in AGENT_DEPENDENCIES and agent not in wanted:
            wanted.add(agent)
            for dep in AGENT_DEPENDENCIES[agent]:
                add(dep)

    for agent in requested:
        add(str(agent).strip().lower())
    return [a for a in FULL_WORKFLOW if a in wanted] or FULL_WORKFLOW


class Trace:
    """Ordered agent log, shaped for the UI's AgentTraceLog component."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def step(
        self, agent: str, fn: Callable[[], Awaitable[Any]], describe: Callable[[Any], str]
    ) -> Any:
        entry: dict[str, Any] = {"agent": agent, "status": "running", "timestamp": utcnow()}
        self.entries.append(entry)
        started = time.perf_counter()
        try:
            result = await fn()
        except Exception as exc:
            logger.exception("Agent %s failed", agent)
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
            result = None
        else:
            entry.update(status="done", result=describe(result))
        entry["duration_ms"] = int((time.perf_counter() - started) * 1000)
        return result

    def skip(self, agent: str, reason: str) -> None:
        self.entries.append(
            {"agent": agent, "status": "skipped", "reason": reason, "timestamp": utcnow()}
        )


async def plan_workflow(query: str, trace: Trace) -> list[str]:
    settings = get_settings()
    llm = get_llm()
    if settings.orchestrator_planner != "llm" or not llm.enabled:
        trace.entries.append(
            {
                "agent": "Manager",
                "status": "done",
                "result": "Static plan: " + " → ".join(FULL_WORKFLOW),
                "timestamp": utcnow(),
                "duration_ms": 0,
            }
        )
        return FULL_WORKFLOW

    async def ask() -> list[str]:
        data = await llm.chat_json(
            "You are the Manager agent of a research multi-agent system. Choose which agents "
            "to run for the user's query. Agents: discovery (find papers), analysis (trends, "
            "keywords, authors), citation (formatted references), summarizer (per-paper LLM "
            "summaries), conflict_detector (contradictions between analysis and summaries), "
            "roadmap (foundational papers, gaps, next queries). Default to all of them unless "
            'the query clearly needs less. Respond as JSON: {"agents": [..]}',
            f"User query: {query!r}",
            max_tokens=150,
            temperature=0.0,
        )
        return resolve_workflow((data or {}).get("agents") or FULL_WORKFLOW)

    workflow = await trace.step("Manager", ask, lambda w: "Plan: " + " → ".join(w))
    return workflow or FULL_WORKFLOW


def _empty_analysis() -> dict[str, list]:
    return {
        "publication_trend": [],
        "top_authors": [],
        "keyword_frequency": [],
        "citation_distribution": [],
        "emerging_topics": [],
    }


async def orchestrate(query: str, session_id: str, page: int = 0) -> dict[str, Any]:
    """Run the agent graph for ``query``. Pure computation: persistence is the caller's job.

    Every returned paper has a provisional ``id`` that summaries and the roadmap refer
    to; the persistence layer maps it onto the stored row id.
    """
    settings = get_settings()
    async with _session_lock(session_id):
        trace = Trace()
        workflow = await plan_workflow(query, trace)

        papers: list[dict[str, Any]] = (
            await trace.step(
                "Discovery",
                lambda: discovery.run(query, page),
                lambda r: f"{len(r)} papers found",
            )
            or []
        )
        for paper in papers:
            paper["id"] = str(uuid.uuid4())

        # ── Stage 2: independent agents, concurrently ───────────────────────
        async def run_analysis() -> dict | None:
            if "analysis" not in workflow:
                return None
            if len(papers) < MIN_PAPERS_FOR_ANALYSIS:
                trace.skip("Analysis", f"needs at least {MIN_PAPERS_FOR_ANALYSIS} papers")
                return None
            return await trace.step(
                "Analysis", lambda: analysis.run(papers), lambda _: "Trends, authors & keywords"
            )

        async def run_citations() -> list[dict] | None:
            if "citation" not in workflow or not papers:
                return None

            async def gen() -> list[dict]:
                return citation.run(papers)

            return await trace.step("Citation", gen, lambda r: f"{len(r)} citations generated")

        async def run_summaries() -> list[dict]:
            if "summarizer" not in workflow or not papers:
                return []
            subset = papers[: settings.summarize_top_n]
            return (
                await trace.step(
                    "Summarizer",
                    lambda: summarizer.summarize_all_papers(subset),
                    lambda r: (
                        f"{len(r)} summaries ("
                        + (
                            "LLM"
                            if any(s.get("generated_by") == "llm" for s in r)
                            else "extractive"
                        )
                        + ")"
                    ),
                )
                or []
            )

        analysis_result, cited, summaries = await asyncio.gather(
            run_analysis(), run_citations(), run_summaries()
        )
        if cited:
            citation_by_id = {p["id"]: p["citation"] for p in cited}
            for paper in papers:
                paper["citation"] = citation_by_id.get(paper["id"])

        # ── Stage 3: conflict detection ─────────────────────────────────────
        conflict_result: dict[str, Any] | None = None
        if "conflict_detector" in workflow:
            if analysis_result and summaries:
                conflict_result = await trace.step(
                    "Conflict Detection",
                    lambda: conflict_detector.detect_conflicts(papers, analysis_result, summaries),
                    lambda r: (
                        f"{len(r['conflicts'])} conflicts detected"
                        if r["conflicts"]
                        else "No conflicts detected"
                    ),
                )
            else:
                trace.skip("Conflict Detection", "requires both analysis and summaries")
        conflicts = (conflict_result or {}).get("conflicts", [])

        # ── Stage 4: roadmap ────────────────────────────────────────────────
        roadmap_result = None
        if "roadmap" in workflow:
            if papers:
                roadmap_result = await trace.step(
                    "Roadmap",
                    lambda: roadmap.run(
                        papers=papers,
                        analysis_trend_data=analysis_result or _empty_analysis(),
                        summaries=summaries,
                        notes=[],
                        conflicts=conflicts,
                        session_id=session_id,
                        query=query,
                    ),
                    lambda r: (
                        f"{len(r['foundational_papers'])} key papers, "
                        f"{len(r['gap_areas'])} gaps, {len(r['next_query_suggestions'])} next queries"
                    ),
                )
            else:
                trace.skip("Roadmap", "no papers available")

    return {
        "papers": papers,
        "analysis": analysis_result,
        "summaries": summaries,
        "trace": trace.entries,
        "conflicts": conflicts,
        "conflict_summary": (conflict_result or {}).get("summary", "No conflicts detected"),
        "roadmap": roadmap_result,
    }
