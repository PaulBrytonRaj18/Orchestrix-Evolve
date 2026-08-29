import asyncio
import json
import logging
import os
from datetime import UTC, datetime

from groq import AsyncGroq
from dotenv import load_dotenv

from agents import analysis, citation, conflict_detector, discovery, roadmap, summarizer

load_dotenv()

logger = logging.getLogger(__name__)

_session_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


def utcnow():
    return datetime.now(UTC).isoformat()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


async def manager_agent_decide_workflow(query: str, trace: list) -> list:
    """
    A Manager Agent that decides which sub-agents to invoke based on the query.
    For this codebase, we have specific capabilities. We prompt the LLM to give us a plan.
    """
    trace.append({"agent": "Manager", "status": "running", "timestamp": utcnow()})

    # We define the available tools/agents
    system_prompt = """You are a Research Manager Agent in a Multi-Agent System.
Your job is to receive a user's research query and decide which agents need to be invoked to fulfill the request.

Available Agents:
- discovery: Finds academic papers related to the query.
- analysis: Analyzes trends, keywords, citations, and authors in the papers. (Requires discovery)
- summarizer: Generates summaries for the papers. (Requires discovery)
- citation: Generates formatted citations for the papers. (Requires discovery)
- conflict_detector: Detects contradictions between analysis and summaries. (Requires analysis and summarizer)
- roadmap: Generates a research roadmap. (Requires discovery, optionally analysis, summarizer, conflict_detector)

For a comprehensive research workflow, you should typically invoke all of them in this order:
["discovery", "analysis", "citation", "summarizer", "conflict_detector", "roadmap"]

Return ONLY a JSON list of strings representing the agents to invoke, in the correct execution order.
Do not wrap it in markdown or add any other text.
"""

    user_prompt = f"User query: '{query}'\nDetermine the workflow."

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("No GROQ_API_KEY found, falling back to default workflow.")
        trace[-1] = {
            **trace[-1],
            "status": "done",
            "result": "Default workflow selected (No API Key)"
        }
        return ["discovery", "analysis", "citation", "summarizer", "conflict_detector", "roadmap"]

    try:
        client = AsyncGroq(api_key=api_key)
        res = await asyncio.wait_for(
            client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=200,
            ),
            timeout=10.0,
        )

        content = res.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].strip()
            if content.startswith("json"):
                content = content[4:].strip()

        workflow = json.loads(content)

        # Ensure discovery is first if anything else is requested
        if workflow and "discovery" not in workflow:
            workflow.insert(0, "discovery")

        trace[-1] = {
            **trace[-1],
            "status": "done",
            "result": f"Decided workflow: {', '.join(workflow)}"
        }
        return workflow
    except Exception as e:
        logger.error(f"Manager Agent error: {e}")
        trace[-1] = {
            **trace[-1],
            "status": "done",
            "result": f"Default workflow selected (Error: {str(e)})"
        }
        return ["discovery", "analysis", "citation", "summarizer", "conflict_detector", "roadmap"]


async def orchestrate(query: str, session_id: str, page: int = 0) -> dict:
    """
    Central orchestration layer using a True Multi-Agent architecture.
    A Manager Agent decides the workflow, and then delegates to the respective Sub-Agents.
    Uses per-session lock to prevent concurrent orchestration of same session.
    """
    lock = await _get_session_lock(session_id)

    if lock.locked():
        logger.warning(f"Session {session_id} already being orchestrated, waiting...")

    async with lock:
        trace = []

        # True MAS: LLM Manager decides the plan
        workflow = await manager_agent_decide_workflow(query, trace)

        papers = []
        papers_with_citations = []
        analysis_result = None
        conflicts = []
        conflict_result = None
        summaries_list = []
        roadmap_result = None

        if "discovery" in workflow:
            trace.append({"agent": "Discovery", "status": "running", "timestamp": utcnow()})
            papers = await discovery.run(query, page)
            trace[-1] = {**trace[-1], "status": "done", "result": f"{len(papers)} papers found"}
            papers_with_citations = papers  # Fallback if citation not run

        if "analysis" in workflow:
            if len(papers) > 5:
                trace.append({"agent": "Analysis", "status": "running", "timestamp": utcnow()})
                analysis_result = await analysis.run(papers)
                trace[-1] = {**trace[-1], "status": "done", "result": "Analysis complete"}
            else:
                trace.append({
                    "agent": "Analysis",
                    "status": "skipped",
                    "reason": "fewer than 5 papers returned",
                    "timestamp": utcnow(),
                })

        if "citation" in workflow or "summarizer" in workflow:
            trace.append({"agent": "Citations & Summaries", "status": "running", "timestamp": utcnow()})

            # We can run these concurrently in a true MAS
            citation_task = citation.run(papers) if "citation" in workflow else papers

            if "summarizer" in workflow:
                summaries_list = await summarizer.summarize_all_papers(papers)

            if "citation" in workflow:
                # citation.run is synchronous
                papers_with_citations = citation_task

            trace[-1] = {
                **trace[-1],
                "status": "done",
                "result": f"{len(papers_with_citations) if 'citation' in workflow else 0} citations, {len(summaries_list)} summaries generated",
            }

        if "conflict_detector" in workflow:
            if analysis_result and summaries_list and len(summaries_list) > 0:
                trace.append({"agent": "Conflict Detection", "status": "running", "timestamp": utcnow()})

                conflict_result = await conflict_detector.detect_conflicts(
                    papers, analysis_result, summaries_list
                )

                conflicts = conflict_result.get("conflicts", [])
                if conflicts:
                    conflict_result.get("summary", f"Detected {len(conflicts)} conflicts")
                    trace[-1] = {
                        **trace[-1],
                        "status": "done",
                        "result": f"{len(conflicts)} conflicts detected - review in conflicts panel",
                    }
                else:
                    trace[-1] = {**trace[-1], "status": "done", "result": "No conflicts detected"}
            else:
                trace.append({
                    "agent": "Conflict Detection",
                    "status": "skipped",
                    "reason": "Insufficient data for conflict detection",
                    "timestamp": utcnow(),
                })

        if "roadmap" in workflow:
            if papers and len(papers) > 0:
                trace.append({"agent": "Roadmap", "status": "running", "timestamp": utcnow()})

                analysis_data = analysis_result if analysis_result else {
                    "publication_trend": [],
                    "top_authors": [],
                    "keyword_frequency": [],
                    "citation_distribution": [],
                    "emerging_topics": [],
                }

                roadmap_result = await roadmap.run(
                    papers=papers,
                    analysis_trend_data=analysis_data,
                    summaries=summaries_list if summaries_list else [],
                    notes=[],
                    conflicts=conflicts if conflicts else [],
                    session_id=session_id,
                )

                trace[-1] = {
                    **trace[-1],
                    "status": "done",
                    "result": (
                        f"Roadmap generated: {len(roadmap_result['foundational_papers'])} papers, "
                        f"{len(roadmap_result['gap_areas'])} gaps, "
                        f"{len(roadmap_result['next_query_suggestions'])} queries"
                    ),
                }
            else:
                trace.append({
                    "agent": "Roadmap",
                    "status": "skipped",
                    "reason": "No papers available for roadmap generation",
                    "timestamp": utcnow(),
                })

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
