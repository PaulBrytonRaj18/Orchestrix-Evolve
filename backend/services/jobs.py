"""Background orchestration jobs with live event fan-out.

A job runs ``orchestrate`` → persistence as an asyncio task in the API process, so
the HTTP request that started it returns immediately (202) and the run survives the
client disconnecting. Progress goes to:

* the ``orchestration_jobs`` row (status, trace, heartbeat) — the source of truth
  that any process can read, written at most every ``_TRACE_FLUSH`` seconds;
* in-memory subscribers (SSE streams) of *this* process, which get every event.

Events: ``status`` {status}, ``trace`` [entries], ``papers`` [provisional papers,
right after discovery], ``done`` {OrchestrateResponse}, ``error`` {message}.

Limits: at most ``JOB_MAX_CONCURRENCY`` jobs run at once per process (the rest wait
as ``queued``) and a user may have ``JOB_MAX_ACTIVE_PER_USER`` active jobs.
A heartbeat lets a restarted process fail only jobs nobody is running any more.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update

from config import get_settings
from database import get_db_context
from models import OrchestrationJob
from schemas import OrchestrateResponse
from services import persistence

logger = logging.getLogger(__name__)

ACTIVE = ("queued", "running")
TERMINAL = ("completed", "failed")
_TRACE_FLUSH = 0.5  # seconds between trace writes to the DB
_LINGER = 120.0  # keep a finished job's live state for late subscribers


@dataclass
class LiveJob:
    id: str
    session_id: str
    user_id: str
    status: str = "queued"
    trace: list[dict[str, Any]] = field(default_factory=list)
    papers: list[dict[str, Any]] | None = None
    final: tuple[str, Any] | None = None  # ("done", view) | ("error", {...})
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None
    flush_pending: bool = False

    def snapshot(self) -> list[tuple[str, Any]]:
        events: list[tuple[str, Any]] = [("status", {"status": self.status})]
        if self.trace:
            events.append(("trace", self.trace))
        if self.papers is not None and self.final is None:
            events.append(("papers", self.papers))
        if self.final is not None:
            events.append(self.final)
        return events


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class JobManager:
    def __init__(self) -> None:
        self._live: dict[str, LiveJob] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._background: set[asyncio.Task] = set()

    # ── lifecycle ──────────────────────────────────────────────────────────
    def _sem(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(get_settings().job_max_concurrency)
        return self._semaphore

    async def start(self) -> None:
        """Fail jobs orphaned by a crashed or restarted process."""
        failed = await run_in_threadpool(fail_stale_jobs)
        if failed:
            logger.warning("Marked %d orphaned job(s) as failed", failed)

    async def shutdown(self) -> None:
        tasks = [j.task for j in self._live.values() if j.task and not j.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for task in list(self._background):
            task.cancel()
        self._live.clear()
        self._semaphore = None

    def live(self, job_id: str) -> LiveJob | None:
        return self._live.get(job_id)

    # ── submission ─────────────────────────────────────────────────────────
    def launch(self, job: OrchestrationJob) -> None:
        live = LiveJob(id=job.id, session_id=job.session_id, user_id=job.user_id)
        self._live[job.id] = live
        live.task = asyncio.create_task(
            self._run(live, job.query, job.kind, job.page), name=f"job-{job.id}"
        )

    # ── events ─────────────────────────────────────────────────────────────
    def subscribe(self, live: LiveJob) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        for event in live.snapshot():
            queue.put_nowait(event)
        live.subscribers.add(queue)
        return queue

    @staticmethod
    def unsubscribe(live: LiveJob, queue: asyncio.Queue) -> None:
        live.subscribers.discard(queue)

    def _publish(self, live: LiveJob, event: str, data: Any) -> None:
        for queue in list(live.subscribers):
            queue.put_nowait((event, data))

    def _on_event(self, live: LiveJob, event: str, data: Any) -> None:
        if event == "trace":
            live.trace = data
            self._schedule_flush(live)
        elif event == "papers":
            live.papers = data
        self._publish(live, event, data)

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def _schedule_flush(self, live: LiveJob) -> None:
        if live.flush_pending:
            return
        live.flush_pending = True

        async def flush() -> None:
            await asyncio.sleep(_TRACE_FLUSH)
            live.flush_pending = False
            await run_in_threadpool(_write, live.id, trace=list(live.trace), heartbeat_at=_now())

        self._spawn(flush())

    # ── execution ──────────────────────────────────────────────────────────
    async def _heartbeat(self, live: LiveJob) -> None:
        interval = get_settings().job_heartbeat_seconds
        while True:
            await asyncio.sleep(interval)
            await run_in_threadpool(_write, live.id, heartbeat_at=_now())

    async def _run(self, live: LiveJob, query: str, kind: str, page: int) -> None:
        from orchestrator import orchestrate  # late import: orchestrator imports agents

        # Beat while queued too, so a job waiting for a slot never looks orphaned.
        heartbeat = asyncio.create_task(self._heartbeat(live))
        try:
            async with self._sem():
                live.status = "running"
                await run_in_threadpool(
                    _write, live.id, status="running", started_at=_now(), heartbeat_at=_now()
                )
                self._publish(live, "status", {"status": "running"})

                result = await orchestrate(
                    query,
                    live.session_id,
                    page=page,
                    listener=lambda event, data: self._on_event(live, event, data),
                )
                if kind == "followup":
                    result["roadmap"] = None  # the roadmap stays tied to the session's query
                view = await run_in_threadpool(
                    persistence.persist_and_view, live.session_id, live.user_id, result
                )
                payload = OrchestrateResponse.model_validate(view).model_dump(mode="json")

            live.trace = payload["trace"]
            live.status = "completed"
            live.final = ("done", payload)
            await run_in_threadpool(
                _write,
                live.id,
                status="completed",
                trace=live.trace,
                conflict_summary=result.get("conflict_summary"),
                finished_at=_now(),
            )
            self._publish(live, "status", {"status": "completed"})
            self._publish(live, "done", payload)
        except asyncio.CancelledError:
            await self._fail(live, "Cancelled: the server shut down while this job was running")
            raise
        except Exception as exc:
            logger.exception("Job %s failed", live.id)
            await self._fail(live, f"{type(exc).__name__}: {exc}")
        finally:
            heartbeat.cancel()
            self._spawn(self._forget_later(live.id))

    async def _fail(self, live: LiveJob, message: str) -> None:
        live.status = "failed"
        live.final = ("error", {"message": message})
        with contextlib.suppress(Exception):
            await asyncio.shield(
                run_in_threadpool(
                    _write,
                    live.id,
                    status="failed",
                    error=message[:2000],
                    trace=list(live.trace),
                    finished_at=_now(),
                )
            )
        self._publish(live, "status", {"status": "failed"})
        self._publish(live, "error", {"message": message})

    async def _forget_later(self, job_id: str) -> None:
        await asyncio.sleep(_LINGER)
        live = self._live.get(job_id)
        if live is not None and not live.subscribers:
            self._live.pop(job_id, None)


# ─── DB helpers (run in the threadpool) ──────────────────────────────────────


def _write(job_id: str, **values: Any) -> None:
    with get_db_context() as db:
        db.execute(update(OrchestrationJob).where(OrchestrationJob.id == job_id).values(**values))


def fail_stale_jobs() -> int:
    """Active jobs whose heartbeat stopped (their process died) become failed."""
    cutoff = _now() - timedelta(seconds=get_settings().job_stale_after_seconds)
    with get_db_context() as db:
        stale = db.scalars(
            select(OrchestrationJob).where(OrchestrationJob.status.in_(ACTIVE))
        ).all()
        count = 0
        for job in stale:
            beat = _aware(job.heartbeat_at) or _aware(job.created_at)
            if beat is not None and beat < cutoff:
                job.status = "failed"
                job.error = "Interrupted: the server restarted before this job finished"
                job.finished_at = _now()
                count += 1
        return count


def is_orphaned(job: OrchestrationJob) -> bool:
    cutoff = _now() - timedelta(seconds=get_settings().job_stale_after_seconds)
    beat = _aware(job.heartbeat_at) or _aware(job.created_at)
    return job.status in ACTIVE and beat is not None and beat < cutoff


job_manager = JobManager()
