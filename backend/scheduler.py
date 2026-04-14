import asyncio
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session as DBSession
import logging

from database import get_db_context
from models import ScheduledDigest, DigestRun, Session as SessionModel, Paper
from agents.digest_scheduler import run_digest, generate_digest_notification
from agents import discovery, citation, summarizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DigestScheduler:
    _instance: Optional["DigestScheduler"] = None
    _scheduler: Optional[AsyncIOScheduler] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()
            self._running_jobs: Dict[str, str] = {}

    def start(self):
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Digest scheduler started")
            self._load_active_digests()

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Digest scheduler stopped")

    def _load_active_digests(self):
        with get_db_context() as db:
            try:
                active_digests = (
                    db.query(ScheduledDigest)
                    .filter(ScheduledDigest.is_active == True)
                    .all()
                )

                for digest in active_digests:
                    if digest.next_run_at:
                        self.add_job(str(digest.id), digest.query, digest.next_run_at)
                        logger.info(f"Loaded digest job: {digest.name} ({digest.id})")
            except Exception as e:
                logger.error(f"Error loading active digests: {e}")

    def add_job(self, digest_id: str, query: str, next_run: datetime):
        job_id = f"digest_{digest_id}"

        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        run_time = (
            next_run.replace(tzinfo=timezone.utc)
            if next_run.tzinfo is None
            else next_run
        )

        self._scheduler.add_job(
            self._execute_digest,
            "date",
            run_date=run_time,
            id=job_id,
            args=[digest_id],
            replace_existing=True,
        )

        logger.info(f"Scheduled digest job {job_id} for {run_time}")

    def remove_job(self, digest_id: str):
        job_id = f"digest_{digest_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed digest job: {job_id}")

    async def _execute_digest(self, digest_id: str):
        logger.info(f"Executing digest: {digest_id}")

        with get_db_context() as db:
            try:
                digest = (
                    db.query(ScheduledDigest)
                    .filter(ScheduledDigest.id == digest_id)
                    .first()
                )

                if not digest:
                    logger.warning(f"Digest {digest_id} not found")
                    return

                if not digest.is_active:
                    logger.info(f"Digest {digest_id} is inactive, skipping")
                    return

                run = DigestRun(
                    scheduled_digest_id=digest_id, query=digest.query, status="running"
                )
                db.add(run)
                db.commit()
                db.refresh(run)

                existing_papers = (
                    db.query(Paper)
                    .filter(
                        Paper.session_id.in_(
                            db.query(SessionModel.id)
                            .filter(SessionModel.query == digest.query)
                            .all()
                        )
                    )
                    .all()
                )

                existing_ids = [p.external_id for p in existing_papers if p.external_id]

                result = await run_digest(
                    query=digest.query,
                    last_run_at=digest.last_run_at,
                    existing_external_ids=existing_ids,
                    limit=50,
                )

                new_papers = result.get("new_papers", [])
                run.new_papers_count = len(new_papers)
                run.new_paper_ids = [p.get("external_id", "") for p in new_papers]
                run.status = "completed"

                if new_papers:
                    session = SessionModel(
                        name=f"{digest.name} - Digest {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                        query=digest.query,
                    )
                    db.add(session)
                    db.commit()
                    db.refresh(session)

                    run.session_id = session.id

                    for paper_data in new_papers:
                        paper = Paper(
                            session_id=session.id,
                            title=paper_data.get("title", ""),
                            authors=paper_data.get("authors", []),
                            year=paper_data.get("year"),
                            abstract=paper_data.get("abstract"),
                            source_url=paper_data.get("source_url"),
                            citation_count=paper_data.get("citation_count"),
                            external_id=paper_data.get("external_id"),
                            source=paper_data.get("source", "unknown"),
                        )
                        db.add(paper)

                    db.commit()

                    citation_results = citation.run(new_papers)
                    summary_results = await summarizer.summarize_all_papers(new_papers)

                    for paper_data, paper_citations in zip(
                        new_papers, citation_results
                    ):
                        from models import Citation

                        citation_obj = Citation(
                            paper_id=paper_data.get("id"),
                            apa=paper_citations.get("citation", {}).get("apa", ""),
                            mla=paper_citations.get("citation", {}).get("mla", ""),
                            ieee=paper_citations.get("citation", {}).get("ieee", ""),
                            chicago=paper_citations.get("citation", {}).get(
                                "chicago", ""
                            ),
                        )

                    db.commit()

                    if digest.notify_email:
                        notification = generate_digest_notification(
                            digest.name, digest.query, new_papers, digest.frequency
                        )
                        logger.info(f"Would send email to {digest.notify_email}")
                        logger.info(f"Email content:\n{notification}")

                digest.last_run_at = datetime.now(timezone.utc)

                from agents.digest_scheduler import calculate_next_run

                digest.next_run_at = calculate_next_run(
                    digest.last_run_at, digest.frequency
                )

                self.add_job(digest_id, digest.query, digest.next_run_at)

                db.commit()
                logger.info(
                    f"Digest {digest_id} completed. Found {len(new_papers)} new papers"
                )

            except Exception as e:
                logger.error(f"Error executing digest {digest_id}: {e}")
                run.status = "failed"
                run.error_message = str(e)
                db.commit()

    def trigger_manual_run(self, digest_id: str):
        job_id = f"digest_{digest_id}"

        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        self._scheduler.add_job(
            self._execute_digest,
            "date",
            id=f"{job_id}_manual",
            args=[digest_id],
            replace_existing=True,
        )
        logger.info(f"Triggered manual run for digest {digest_id}")


scheduler = DigestScheduler()
