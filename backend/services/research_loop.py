"""Deep research: search → read → refine, until coverage stops improving.

Round 1 is a normal full search of the session's query. Each later round runs up to
``DEEP_QUERIES_PER_ROUND`` follow-up searches into the same session. The LLM chooses
them from what was found (titles, gaps, the question), falling back to the roadmap's
suggestions. The loop stops when a round adds fewer than ``DEEP_MIN_GAIN`` (10%) new
papers, when ``DEEP_MAX_ROUNDS`` is reached, or when no unused query is left.
Every round is persisted, so a stopped loop keeps what it found.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi.concurrency import run_in_threadpool

from config import get_settings
from llm import get_llm
from orchestrator import orchestrate, utcnow
from schemas import OrchestrateResponse
from services import persistence

logger = logging.getLogger(__name__)


async def next_queries(
    question: str, view: dict[str, Any], used: set[str], n: int
) -> tuple[list[str], str]:
    """Follow-up queries not yet run, and who chose them ("llm" or "roadmap")."""
    roadmap = view.get("roadmap") or {}
    suggestions = [q["query"] for q in (roadmap.get("next_query_suggestions") or [])]
    llm = get_llm()
    if llm.enabled:
        titles = "\n".join(f"- {p['title']}" for p in (view.get("papers") or [])[:25])
        gaps = "\n".join(f"- {g['question']}" for g in (roadmap.get("gap_areas") or []))
        data = await llm.chat_json(
            "You plan literature searches. Given a research question and what has been "
            "found so far, propose search queries that would find important papers that are "
            "still missing. Respond with JSON only.",
            f"Question: {question}\n\nFound so far:\n{titles}\n\nKnown gaps:\n{gaps}\n\n"
            f"Already searched: {sorted(used)}\n\n"
            f'Return {{"queries": [up to {n} short search queries]}}.',
            max_tokens=200,
            temperature=0.3,
        )
        proposed = [str(q).strip() for q in (data or {}).get("queries") or [] if str(q).strip()]
        fresh = [q for q in proposed if q.lower() not in used][:n]
        if fresh:
            return fresh, "llm"
    return [q for q in suggestions if q.lower() not in used][:n], "roadmap"


async def run(
    session_id: str,
    user_id: str,
    question: str,
    emit: Callable[[str, Any], None],
) -> dict[str, Any]:
    """Run the loop; ``emit`` receives the same events as a normal job (trace, papers)."""
    s = get_settings()
    rounds: list[dict[str, Any]] = []  # collapsed trace entries of finished rounds
    used = {question.lower()}

    def listener_for(label: str):
        def listener(event: str, data: Any) -> None:
            if event == "trace":
                live = [dict(e, agent=f"{label} · {e['agent']}") for e in data]
                emit("trace", rounds + live)
            elif event == "papers" and not rounds:
                emit("papers", data)  # first round's ranked papers, as a normal search

        return listener

    result = await orchestrate(question, session_id, listener=listener_for("Round 1"))
    view = await run_in_threadpool(persistence.persist_and_view, session_id, user_id, result)
    count = len(view["papers"])
    rounds.append(
        {
            "agent": "Round 1",
            "status": "done",
            "timestamp": utcnow(),
            "result": f"'{question}' → {count} papers",
        }
    )
    emit("trace", list(rounds))
    stop_reason = "reached the round limit"

    for number in range(2, s.deep_max_rounds + 1):
        plain = OrchestrateResponse.model_validate(view).model_dump(mode="json")
        queries, chooser = await next_queries(question, plain, used, s.deep_queries_per_round)
        if not queries:
            stop_reason = "no new queries to try"
            break
        before = count
        for q in queries:
            used.add(q.lower())
            sub = await orchestrate(q, session_id, listener=listener_for(f"Round {number}"))
            sub["roadmap"] = None  # keep the roadmap tied to the main question
            view = await run_in_threadpool(persistence.persist_and_view, session_id, user_id, sub)
        count = len(view["papers"])
        gain = (count - before) / max(before, 1)
        rounds.append(
            {
                "agent": f"Round {number}",
                "status": "done",
                "timestamp": utcnow(),
                "result": f"{chooser} chose {queries} → +{count - before} new papers ({gain:.0%})",
            }
        )
        emit("trace", list(rounds))
        if gain < s.deep_min_gain:
            stop_reason = f"round {number} added under {s.deep_min_gain:.0%} new papers"
            break

    rounds.append(
        {
            "agent": "Research loop",
            "status": "done",
            "timestamp": utcnow(),
            "result": f"Stopped: {stop_reason}. {count} papers in {len(rounds)} round(s).",
        }
    )
    view["trace"] = list(rounds)
    view["conflict_summary"] = result.get("conflict_summary")
    return {"view": view, "trace": list(rounds), "conflict_summary": result.get("conflict_summary")}
