"""Background scheduler for research digests (APScheduler, in the app's event loop)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from agents import citation, summarizer
from agents.digest_scheduler import calculate_next_run, generate_digest_notification, run_digest
from database import get_db_context
from models import DigestRun, Paper, ScheduledDigest, Work
from models import Session as SessionModel
from services import persistence

logger = logging.getLogger(__name__)


def _job_id(digest_id: str) -> str:
    return f"digest_{digest_id}"


class DigestScheduler:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    @property
    def running(self) -> bool:
        return bool(self._scheduler and self._scheduler.running)

    def start(self) -> None:
        if self.running:
            return
        self._scheduler = AsyncIOScheduler(timezone=UTC)
        self._scheduler.start()
        self._load_active_digests()
        logger.info("Digest scheduler started")

    def stop(self) -> None:
        if self.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Digest scheduler stopped")
        self._scheduler = None

    def _load_active_digests(self) -> None:
        with get_db_context() as db:
            for digest in db.scalars(
                select(ScheduledDigest).where(ScheduledDigest.is_active.is_(True))
            ):
                now = datetime.now(UTC)
                next_run = digest.next_run_at or now
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=UTC)
                # Missed while the app was down → run shortly after startup.
                self.add_job(digest.id, max(next_run, now))

    def add_job(self, digest_id: str, next_run: datetime) -> None:
        if not self.running:
            return
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=UTC)
        self._scheduler.add_job(
            self._execute_digest,
            "date",
            run_date=next_run,
            id=_job_id(digest_id),
            args=[digest_id],
            replace_existing=True,
            misfire_grace_time=3600,
        )

    def remove_job(self, digest_id: str) -> None:
        if self.running and self._scheduler.get_job(_job_id(digest_id)):
            self._scheduler.remove_job(_job_id(digest_id))

    def trigger_manual_run(self, digest_id: str, run_id: str) -> None:
        """Run now in addition to — not instead of — the regular schedule."""
        if not self.running:
            return
        self._scheduler.add_job(
            self._execute_digest,
            "date",
            run_date=datetime.now(UTC),
            id=f"{_job_id(digest_id)}_manual_{uuid.uuid4().hex[:8]}",
            args=[digest_id, run_id, False],
        )

    async def _execute_digest(
        self, digest_id: str, run_id: str | None = None, reschedule: bool = True
    ) -> None:
        await execute_digest(digest_id, run_id)
        if reschedule:
            with get_db_context() as db:
                digest = db.get(ScheduledDigest, digest_id)
                if digest and digest.is_active and digest.next_run_at:
                    self.add_job(digest_id, digest.next_run_at)


def _prepare_run(digest_id: str, run_id: str | None) -> dict | None:
    with get_db_context() as db:
        digest = db.get(ScheduledDigest, digest_id)
        if digest is None or (run_id is None and not digest.is_active):
            return None
        run = db.get(DigestRun, run_id) if run_id else None
        if run is None:
            run = DigestRun(scheduled_digest_id=digest_id, query=digest.query, status="running")
            db.add(run)
            db.flush()
        known = db.scalars(
            select(Work.external_id)
            .join(Paper, Paper.work_id == Work.id)
            .join(SessionModel, Paper.session_id == SessionModel.id)
            # "Seen" = in any of the user's sessions, not only ones with this exact query.
            .where(SessionModel.user_id == digest.user_id)
            .distinct()
        ).all()
        return {
            "run_id": run.id,
            "query": digest.query,
            "name": digest.name,
            "user_id": digest.user_id,
            "frequency": digest.frequency,
            "last_run_at": digest.last_run_at,
            "notify_email": digest.notify_email,
            "known_ids": [k for k in known if k],
        }


async def execute_digest(digest_id: str, run_id: str | None = None) -> None:
    ctx = await run_in_threadpool(_prepare_run, digest_id, run_id)
    if ctx is None:
        logger.info("Digest %s missing or inactive; skipping", digest_id)
        return
    try:
        result = await run_digest(
            query=ctx["query"],
            last_run_at=ctx["last_run_at"],
            existing_external_ids=ctx["known_ids"],
            limit=50,
        )
        new_papers = result["new_papers"]
        for paper in new_papers:
            paper["id"] = str(uuid.uuid4())
        papers = citation.run(new_papers)
        summaries = await summarizer.summarize_all_papers(papers[:10])

        def save() -> None:
            with get_db_context() as db:
                run = db.get(DigestRun, ctx["run_id"])
                digest = db.get(ScheduledDigest, digest_id)
                if new_papers:
                    session = SessionModel(
                        name=f"{ctx['name']} — digest {datetime.now(UTC):%Y-%m-%d}",
                        query=ctx["query"],
                        user_id=ctx["user_id"],
                    )
                    db.add(session)
                    db.flush()
                    id_map = persistence.save_papers(db, session.id, papers)
                    persistence.save_summaries(db, summaries, id_map)
                    run.session_id = session.id
                run.new_papers_count = len(new_papers)
                run.new_paper_ids = [p.get("external_id") or "" for p in new_papers]
                run.status = "completed"
                if digest:
                    digest.last_run_at = datetime.now(UTC)
                    digest.next_run_at = calculate_next_run(digest.last_run_at, digest.frequency)

        await run_in_threadpool(save)
        if ctx["notify_email"]:
            # E-mail delivery is not wired up yet; log the rendered message.
            logger.info(
                "Digest e-mail for %s:\n%s",
                ctx["notify_email"],
                generate_digest_notification(
                    ctx["name"], ctx["query"], new_papers, ctx["frequency"]
                ),
            )
        logger.info("Digest %s completed with %d new papers", digest_id, len(new_papers))
    except Exception as exc:
        logger.exception("Digest %s failed", digest_id)
        error_message = f"{type(exc).__name__}: {exc}"[:2000]

        def mark_failed() -> None:
            with get_db_context() as db:
                run = db.get(DigestRun, ctx["run_id"])
                if run:
                    run.status = "failed"
                    run.error_message = error_message

        await run_in_threadpool(mark_failed)


scheduler = DigestScheduler()
