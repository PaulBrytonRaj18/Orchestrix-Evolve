"""Background orchestration jobs and their live event stream (Server-Sent Events).

    POST /sessions/{id}/jobs     → 202 JobResponse (an identical active job is reused)
    GET  /sessions/{id}/jobs     → recent jobs, newest first (resume after a reload)
    GET  /jobs/{id}              → status + trace (polling fallback)
    GET  /jobs/{id}/events       → text/event-stream: status, trace, papers, done | error

The stream sends a snapshot first, so reconnecting at any time is safe. Jobs owned
by another process (or already finished) are streamed from the database.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from auth import get_current_user
from config import get_settings
from database import get_db_context
from models import OrchestrationJob
from routers.sessions import get_owned_session
from schemas import JobCreate, JobResponse, OrchestrateResponse
from services import persistence
from services.jobs import ACTIVE, is_orphaned, job_manager

router = APIRouter(tags=["Jobs"])


def _owned_job(db, job_id: str, user_id: str) -> OrchestrationJob:
    job = db.get(OrchestrationJob, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def _create_job(session_id: str, user_id: str, body: JobCreate) -> tuple[OrchestrationJob, bool]:
    s = get_settings()
    with get_db_context() as db:
        session = get_owned_session(db, session_id, user_id)
        query = (body.query or session.query).strip()
        existing = db.scalar(
            select(OrchestrationJob)
            .where(
                OrchestrationJob.session_id == session_id,
                OrchestrationJob.status.in_(ACTIVE),
                OrchestrationJob.kind == body.kind,
                OrchestrationJob.query == query,
                OrchestrationJob.page == body.page,
            )
            .order_by(OrchestrationJob.created_at.desc())
        )
        if existing is not None and not is_orphaned(existing):
            db.expunge(existing)
            return existing, False  # idempotent: a double-click reuses the running job
        active = db.scalar(
            select(func.count())
            .select_from(OrchestrationJob)
            .where(OrchestrationJob.user_id == user_id, OrchestrationJob.status.in_(ACTIVE))
        )
        if active >= s.job_max_active_per_user:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"You already have {active} searches running; wait for one to finish.",
            )
        job = OrchestrationJob(
            session_id=session_id,
            user_id=user_id,
            kind=body.kind,
            query=query,
            page=body.page,
            status="queued",
            trace=[],
            heartbeat_at=datetime.now(UTC),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        db.expunge(job)
        return job, True


@router.post(
    "/sessions/{session_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_job(
    session_id: str,
    response: Response,
    body: JobCreate | None = None,
    user_id: str = Depends(get_current_user),
) -> OrchestrationJob:
    job, created = await run_in_threadpool(_create_job, session_id, user_id, body or JobCreate())
    if created:
        job_manager.launch(job)
    response.headers["Location"] = f"/jobs/{job.id}"
    return job


@router.get("/sessions/{session_id}/jobs", response_model=list[JobResponse])
def list_session_jobs(
    session_id: str,
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user),
) -> list[OrchestrationJob]:
    with get_db_context() as db:
        get_owned_session(db, session_id, user_id)
        jobs = db.scalars(
            select(OrchestrationJob)
            .where(OrchestrationJob.session_id == session_id)
            .order_by(OrchestrationJob.created_at.desc())
            .limit(limit)
        ).all()
        for job in jobs:
            db.expunge(job)
        return list(jobs)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, user_id: str = Depends(get_current_user)) -> OrchestrationJob:
    with get_db_context() as db:
        job = _owned_job(db, job_id, user_id)
        db.expunge(job)
        return job


# ─── Server-Sent Events ──────────────────────────────────────────────────────


def _sse(seq: int, event: str, data: Any) -> str:
    return f"id: {seq}\nevent: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _db_state(job_id: str, user_id: str) -> dict[str, Any]:
    """A job's state from the database; for completed jobs also the final session view."""
    with get_db_context() as db:
        job = _owned_job(db, job_id, user_id)
        state: dict[str, Any] = {
            "status": job.status,
            "trace": job.trace or [],
            "error": job.error,
            "orphaned": is_orphaned(job),
        }
        if job.status == "completed":
            view = persistence.build_orchestrate_response(
                db,
                job.session_id,
                {"trace": job.trace or [], "conflict_summary": job.conflict_summary},
            )
            state["view"] = OrchestrateResponse.model_validate(view).model_dump(mode="json")
        return state


async def _stream_live(live, request: Request) -> AsyncIterator[str]:
    keepalive = get_settings().sse_keepalive_seconds
    queue = job_manager.subscribe(live)
    seq = 0
    try:
        while True:
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=keepalive)
            except TimeoutError:
                if await request.is_disconnected():
                    return
                yield ": keepalive\n\n"
                continue
            seq += 1
            yield _sse(seq, event, data)
            if event in ("done", "error"):
                return
    finally:
        job_manager.unsubscribe(live, queue)


async def _stream_from_db(job_id: str, user_id: str, request: Request) -> AsyncIterator[str]:
    """For finished jobs, or jobs running in another process: follow the DB row."""
    keepalive = get_settings().sse_keepalive_seconds
    seq, last_trace, last_status, idle = 0, None, None, 0.0
    while True:
        state = await run_in_threadpool(_db_state, job_id, user_id)
        if state["status"] != last_status:
            last_status = state["status"]
            seq += 1
            yield _sse(seq, "status", {"status": last_status})
        if state["trace"] != last_trace:
            last_trace = state["trace"]
            seq += 1
            yield _sse(seq, "trace", last_trace)
            idle = 0.0
        if state["status"] == "completed":
            seq += 1
            yield _sse(seq, "done", state["view"])
            return
        if state["status"] == "failed" or state["orphaned"]:
            seq += 1
            message = state["error"] or "The server running this job stopped responding"
            yield _sse(seq, "error", {"message": message})
            return
        if await request.is_disconnected():
            return
        await asyncio.sleep(1.0)
        idle += 1.0
        if idle >= keepalive:
            idle = 0.0
            yield ": keepalive\n\n"


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str, request: Request, user_id: str = Depends(get_current_user)
) -> StreamingResponse:
    live = job_manager.live(job_id)
    if live is not None:
        if live.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        body = _stream_live(live, request)
    else:
        await run_in_threadpool(_db_state, job_id, user_id)  # 404 before streaming starts
        body = _stream_from_db(job_id, user_id, request)
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: do not buffer the stream
            "Connection": "keep-alive",
        },
    )
