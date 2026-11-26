"""Scheduled research digests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import digest_scheduler
from auth import get_current_user
from database import get_db, get_db_context
from models import DigestRun, Paper, ScheduledDigest
from models import Session as SessionModel
from scheduler import scheduler
from schemas import (
    DigestRunResponse,
    ScheduledDigestCreate,
    ScheduledDigestResponse,
    ScheduledDigestWithRuns,
)

router = APIRouter(prefix="/digests", tags=["Digests"])


def get_owned_digest(db: Session, digest_id: str, user_id: str) -> ScheduledDigest:
    digest = db.get(ScheduledDigest, digest_id)
    if digest is None or digest.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Digest not found")
    return digest


@router.post("", response_model=ScheduledDigestResponse, status_code=status.HTTP_201_CREATED)
def create_digest(
    body: ScheduledDigestCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> ScheduledDigest:
    next_run = digest_scheduler.calculate_next_run(datetime.now(UTC), body.frequency)
    digest = ScheduledDigest(
        user_id=user_id,
        name=body.name,
        query=body.query,
        frequency=body.frequency,
        notify_email=body.notify_email,
        next_run_at=next_run,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    scheduler.add_job(digest.id, next_run)
    return digest


@router.get("", response_model=list[ScheduledDigestResponse])
def list_digests(
    db: Session = Depends(get_db), user_id: str = Depends(get_current_user)
) -> list[ScheduledDigest]:
    return list(
        db.scalars(
            select(ScheduledDigest)
            .where(ScheduledDigest.user_id == user_id)
            .order_by(ScheduledDigest.created_at.desc())
        )
    )


@router.get("/{digest_id}", response_model=ScheduledDigestWithRuns)
def get_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> ScheduledDigestWithRuns:
    digest = get_owned_digest(db, digest_id, user_id)
    runs = db.scalars(
        select(DigestRun)
        .where(DigestRun.scheduled_digest_id == digest_id)
        .order_by(DigestRun.created_at.desc())
        .limit(50)
    ).all()
    return ScheduledDigestWithRuns(
        **ScheduledDigestResponse.model_validate(digest).model_dump(),
        runs=[DigestRunResponse.model_validate(r) for r in runs],
    )


@router.delete("/{digest_id}")
def delete_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    digest = get_owned_digest(db, digest_id, user_id)
    scheduler.remove_job(digest_id)
    db.delete(digest)
    db.commit()
    return {"message": "Digest deleted"}


@router.patch("/{digest_id}/toggle", response_model=ScheduledDigestResponse)
def toggle_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> ScheduledDigest:
    digest = get_owned_digest(db, digest_id, user_id)
    digest.is_active = not digest.is_active
    if digest.is_active:
        digest.next_run_at = digest_scheduler.calculate_next_run(
            datetime.now(UTC), digest.frequency
        )
    db.commit()
    db.refresh(digest)
    if digest.is_active:
        scheduler.add_job(digest_id, digest.next_run_at)
    else:
        scheduler.remove_job(digest_id)
    return digest


@router.post("/{digest_id}/run", response_model=DigestRunResponse, status_code=202)
def run_digest_now(
    digest_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> DigestRun:
    """Queue an immediate run. Poll ``GET /digests/{id}`` for its status."""
    digest = get_owned_digest(db, digest_id, user_id)
    if not scheduler.running:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scheduler is disabled")
    run = DigestRun(scheduled_digest_id=digest_id, query=digest.query, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    scheduler.trigger_manual_run(digest_id, run.id)
    return run


@router.get("/{digest_id}/preview")
async def preview_digest(
    digest_id: str, user_id: str = Depends(get_current_user)
) -> dict[str, Any]:
    def load() -> tuple[str, datetime | None, list[str]]:
        with get_db_context() as db:
            digest = get_owned_digest(db, digest_id, user_id)
            known = db.scalars(
                select(Paper.external_id)
                .join(SessionModel, Paper.session_id == SessionModel.id)
                .where(SessionModel.user_id == user_id, SessionModel.query == digest.query)
            ).all()
            return digest.query, digest.last_run_at, [k for k in known if k]

    query, last_run_at, known = await run_in_threadpool(load)
    result = await digest_scheduler.run_digest(query, last_run_at, known, limit=20)
    return {
        "query": query,
        "threshold_date": result["threshold_date"],
        "new_papers_preview": result["new_papers"][:5],
        "total_new_count": result["total_new"],
        "is_first_run": result["is_first_run"],
        "source_stats": result["source_stats"],
    }
