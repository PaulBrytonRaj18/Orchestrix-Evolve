from datetime import datetime, timezone
from typing import Dict, List
import asyncio

from agents import discovery, analysis, citation, summarizer


def utcnow():
    return datetime.now(timezone.utc).isoformat()


async def orchestrate(query: str, session_id: str, page: int = 0) -> Dict:
    """
    Central orchestration layer that coordinates all agents and records trace log.
    """
    trace = []

    trace.append({"agent": "Discovery", "status": "running", "timestamp": utcnow()})

    papers = await discovery.run(query, page)

    trace[-1] = {**trace[-1], "status": "done", "result": f"{len(papers)} papers found"}

    analysis_result = None
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

    citation_task = citation.run(papers)
    summary_tasks = [summarizer.summarize_paper(p) for p in papers]

    citation_results, summary_results = await asyncio.gather(
        citation_task, asyncio.gather(*summary_tasks)
    )

    trace[-1] = {
        **trace[-1],
        "status": "done",
        "result": f"{len(citation_results)} citations, {len(summary_results)} summaries generated",
    }

    papers_with_citations = citation_results
    summaries_list = summary_results

    return {
        "papers": papers_with_citations,
        "analysis": analysis_result,
        "citations": [
            {"paper": p, "citation": p.get("citation", {})}
            for p in papers_with_citations
        ],
        "summaries": summaries_list,
        "trace": trace,
    }
