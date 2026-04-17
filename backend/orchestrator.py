from datetime import datetime, timezone
from typing import Dict, List
import asyncio
import logging

from agents import discovery, analysis, citation, summarizer, conflict_detector, roadmap

logger = logging.getLogger(__name__)

_session_locks: Dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


async def orchestrate(query: str, session_id: str, page: int = 0) -> Dict:
    """
    Central orchestration layer that coordinates all agents and records trace log.
    Includes conflict detection between Analysis and Summarization agents.
    Uses per-session lock to prevent concurrent orchestration of same session.
    """
    lock = await _get_session_lock(session_id)

    if lock.locked():
        logger.warning(f"Session {session_id} already being orchestrated, waiting...")

    async with lock:
        trace = []

        trace.append({"agent": "Discovery", "status": "running", "timestamp": utcnow()})

        papers = await discovery.run(query, page)

        trace[-1] = {
            **trace[-1],
            "status": "done",
            "result": f"{len(papers)} papers found",
        }

    analysis_result = None
    conflicts = []
    conflict_result = None

    if len(papers) > 5:
        trace.append({"agent": "Analysis", "status": "running", "timestamp": utcnow()})

        analysis_result = await analysis.run(papers)

        trace[-1] = {**trace[-1], "status": "done", "result": "Analysis complete"}
    else:
        trace.append(
            {
                "agent": "Analysis",
                "status": "skipped",
                "reason": "fewer than 5 papers returned",
                "timestamp": utcnow(),
            }
        )

    trace.append(
        {"agent": "Citations & Summaries", "status": "running", "timestamp": utcnow()}
    )

    citation_results = citation.run(papers)
    summary_results = await summarizer.summarize_all_papers(papers)

    trace[-1] = {
        **trace[-1],
        "status": "done",
        "result": f"{len(citation_results)} citations, {len(summary_results)} summaries generated",
    }

    papers_with_citations = citation_results
    summaries_list = summary_results

    if analysis_result and summaries_list and len(summaries_list) > 0:
        trace.append(
            {"agent": "Conflict Detection", "status": "running", "timestamp": utcnow()}
        )

        conflict_result = await conflict_detector.detect_conflicts(
            papers, analysis_result, summaries_list
        )

        conflicts = conflict_result.get("conflicts", [])

        if conflicts:
            conflict_summary = conflict_result.get(
                "summary", f"Detected {len(conflicts)} conflicts"
            )
            trace[-1] = {
                **trace[-1],
                "status": "done",
                "result": f"{len(conflicts)} conflicts detected - review in conflicts panel",
            }
        else:
            trace[-1] = {
                **trace[-1],
                "status": "done",
                "result": "No conflicts detected",
            }
    else:
        trace.append(
            {
                "agent": "Conflict Detection",
                "status": "skipped",
                "reason": "Insufficient data for conflict detection",
                "timestamp": utcnow(),
            }
        )

    roadmap_result = None
    if papers and len(papers) > 0:
        trace.append({"agent": "Roadmap", "status": "running", "timestamp": utcnow()})

        analysis_data = (
            analysis_result
            if analysis_result
            else {
                "publication_trend": [],
                "top_authors": [],
                "keyword_frequency": [],
                "citation_distribution": [],
                "emerging_topics": [],
            }
        )

        roadmap_result = await roadmap.run(
            papers=papers,
            analysis_trend_data=analysis_data,
            summaries=summary_results if summary_results else [],
            notes=[],
            conflicts=conflicts if conflicts else [],
            session_id=session_id,
        )

        trace[-1] = {
            **trace[-1],
            "status": "done",
            "result": f"Roadmap generated: {len(roadmap_result['foundational_papers'])} foundational papers, "
            f"{len(roadmap_result['gap_areas'])} gaps, "
            f"{len(roadmap_result['next_query_suggestions'])} query suggestions",
        }
    else:
        trace.append(
            {
                "agent": "Roadmap",
                "status": "skipped",
                "reason": "No papers available for roadmap generation",
                "timestamp": utcnow(),
            }
        )

    return {
        "papers": papers_with_citations,
        "analysis": analysis_result,
        "citations": [
            {"paper": p, "citation": p.get("citation", {})}
            for p in papers_with_citations
        ],
        "summaries": summaries_list,
        "trace": trace,
        "conflicts": conflicts,
        "conflict_summary": conflict_result.get("summary", "No conflicts detected")
        if conflict_result
        else "No conflicts detected",
        "roadmap": roadmap_result,
    }
